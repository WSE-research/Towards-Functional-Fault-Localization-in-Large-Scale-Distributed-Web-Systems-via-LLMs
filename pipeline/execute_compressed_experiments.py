#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests


DEFAULT_RESEARCHKIT_ROOT = "/home/dschiese/Projekte/30_tools/researchkit"

logger = logging.getLogger("execute_compressed_experiments")

# Make `import researchkit` work even when not installed editable.
try:
    import researchkit  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    rk_src = str(Path(DEFAULT_RESEARCHKIT_ROOT) / "src")
    if rk_src not in sys.path:
        sys.path.insert(0, rk_src)

from researchkit.callgraph_contract import prune_intraclass_runs  # type: ignore[import-not-found]
from researchkit.callgraph_fetch import fetch_invocation_graph  # type: ignore[import-not-found]


MODEL_TIERS: tuple[tuple[int, str], ...] = (
    (400_000, "openai/gpt-5"),
    (1_000_000, "google/gemini-3-flash-preview"),
    (2_000_000, "x-ai/grok-4.1-fast"),
)


def _indent(elem: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def _openrouter(prompt: str, *, model: str, timeout_s: float = 60.0) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "reasoning": {"enabled": True},
    }

    res = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=float(timeout_s),
    )
    res.raise_for_status()
    data = res.json()
    return str(data["choices"][0]["message"]["content"])


def _num_tokens(prompt: str) -> int | None:
    try:
        import tiktoken  # type: ignore
    except Exception:
        return None

    enc = tiktoken.encoding_for_model("gpt-4o")
    return int(len(enc.encode(prompt)))


def _select_model(prompt_tokens: int) -> str:
    for threshold, model in MODEL_TIERS:
        if prompt_tokens <= threshold:
            return model
    raise ValueError(f"Prompt exceeds maximum supported context window ({prompt_tokens} tokens).")


def _compressed_calltree_xml(*, endpoint: str, graph_uri: str) -> tuple[str, dict[str, object]]:
    logger.info("Fetching graph: %s", graph_uri)
    inv = fetch_invocation_graph(endpoint=endpoint, graph_uri=graph_uri)
    logger.info("Fetched invocation graph: nodes=%d edges=%d", len(inv.method_of), len(inv.edges))

    logger.info("Pruning intraclass runs (no label aggregation)")
    pruned, stats = prune_intraclass_runs(inv)
    logger.info(
        "Pruned: nodes %d->%d (%.1f%%), edges %d->%d (%.1f%%)",
        stats.original_nodes,
        stats.contracted_nodes,
        stats.node_reduction_pct,
        stats.original_edges,
        stats.contracted_edges,
        stats.edge_reduction_pct,
    )

    # Derive a calltree-like parent pointer from the pruned graph edges.
    parent_of: dict[str, str] = {}
    for caller, callee in pruned.edges:
        # Call tree: a node should have at most one parent; keep first deterministically.
        parent_of.setdefault(callee, caller)
    for u in pruned.method_of.keys():
        parent_of.setdefault(u, u)

    root_uuid = next((u for u, p in parent_of.items() if u == p), None)
    if root_uuid is None:
        root_uuid = sorted(pruned.method_of.keys())[0]
    parent_of[root_uuid] = root_uuid

    children: dict[str, list[str]] = {u: [] for u in pruned.method_of.keys()}
    for u, p in parent_of.items():
        if u != p:
            children.setdefault(p, []).append(u)
    for k in list(children.keys()):
        children[k] = sorted(children[k])

    methods: dict[str, dict[str, object]] = {
        u: {"id": u, "name": pruned.method_of[u], "children": children.get(u, [])}
        for u in pruned.method_of.keys()
    }

    def build_xml_node(method_id: str, visited: set[str] | None = None) -> ET.Element:
        if visited is None:
            visited = set()
        if method_id in visited:
            return ET.Element("methodRef", attrib={"id": method_id})
        visited.add(method_id)

        m = methods[method_id]
        elem = ET.Element("method", attrib={"id": str(m["id"])})
        if m.get("name"):
            elem.set("name", str(m["name"]))

        methods_elem = ET.SubElement(elem, "methods")
        for child_id in list(m.get("children") or []):
            methods_elem.append(build_xml_node(str(child_id), visited.copy()))
        return elem

    root = build_xml_node(root_uuid)
    _indent(root)
    xml = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
    logger.info("Built compressed calltree XML: %d bytes", len(xml.encode("utf-8")))

    meta = {
        "graph": graph_uri,
        "root_uuid": root_uuid,
        "original_nodes": stats.original_nodes,
        "original_edges": stats.original_edges,
        "contracted_nodes": stats.contracted_nodes,
        "contracted_edges": stats.contracted_edges,
        "node_reduction_pct": stats.node_reduction_pct,
        "edge_reduction_pct": stats.edge_reduction_pct,
    }
    return xml, meta


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run the existing calltree experiment on an intraclass-compressed graph (stdout only)."
    )
    ap.add_argument("--graph", action="append", required=True, help="Named graph URI (repeatable)")
    ap.add_argument("--endpoint", default="http://localhost:8890/sparql", help="SPARQL endpoint URL")
    ap.add_argument("--model", default=None, help="Force OpenRouter model (else: same tiered selection)")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Build XML, count tokens, select model, but do not call OpenRouter.",
    )
    ap.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), help="Logging level")
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    logger.info("Endpoint: %s", args.endpoint)

    repo_root = Path(__file__).resolve().parents[1]
    prompt_template = (repo_root / "prompts" / "evaluation_prompt.txt").read_text(encoding="utf-8")

    for graph_uri in [g.strip() for g in args.graph if g.strip()]:
        logger.info("Starting: %s", graph_uri)
        xml, stats = _compressed_calltree_xml(endpoint=args.endpoint, graph_uri=graph_uri)
        prompt = prompt_template.replace("{calltree_xml}", xml)

        model = (args.model or "").strip() or None
        if model is None:
            tokens = _num_tokens(prompt)
            if tokens is None:
                logger.info("No tiktoken available; defaulting model=%s", MODEL_TIERS[0][1])
                model = MODEL_TIERS[0][1]
            else:
                logger.info("Prompt tokens=%d", tokens)
                model = _select_model(tokens)
        logger.info("Using model=%s", model)

        if args.dry_run:
            # Output format: minimal and stable for piping.
            sys.stdout.write(f"{model}\n")
            continue

        t0 = time.time()
        result = _openrouter(prompt, model=model)
        logger.info("OpenRouter done in %.2fs (response chars=%d)", time.time() - t0, len(result))

        # Output only what the user asked for: model + response.
        sys.stdout.write(f"{model}\n")
        sys.stdout.write(result)
        if not result.endswith("\n"):
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
