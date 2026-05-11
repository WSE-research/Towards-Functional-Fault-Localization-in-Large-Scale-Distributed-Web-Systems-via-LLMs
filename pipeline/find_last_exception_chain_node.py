#!/usr/bin/env python3
from __future__ import annotations

"""Find the last node in an exception-propagation chain.

Per graph: build edges + (rdf:type,rdf:value) per node, start at the tested-method node,
and walk down only through exception-throwing nodes until the deepest leaf.
"""

import argparse, json, re, sys, time
from dataclasses import dataclass
from pathlib import Path

from SPARQLWrapper import SPARQLWrapper, JSON


EX = "http://example.org/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def _quote_graph_iri(graph_uri: str) -> str:
    g = (graph_uri or "").strip()
    if not g:
        return ""
    if g.startswith("<") and g.endswith(">"):
        return g
    if g.startswith("urn:") or g.startswith("http://") or g.startswith("https://"):
        return f"<{g}>"
    if re.fullmatch(r"[0-9a-fA-F-]{16,}", g):
        return f"<urn:graph:{g}>"
    return f"<{g}>"


def _method_regex_for_tested_method(tested_method: str) -> str:
    tm = (tested_method or "").strip()
    if not tm:
        return ""
    esc = re.escape(tm)
    if "." in tm:
        return rf"{esc}$"
    return rf"(^|[.]){esc}$"


def _is_exception_throwing(res_type: str, res_value: str) -> bool:
    def local_name(s: str) -> str:
        t = (s or "").strip()
        for sep in ("#", "/", ":"):
            if sep in t:
                t = t.rsplit(sep, 1)[-1]
        return t

    rt = (res_type or "").strip().lower()
    # Our RDF export uses the "exception:" namespace for thrown exceptions.
    if rt.startswith("exception:"):
        return True

    n = local_name(res_type).lower()
    if n:
        if n.endswith("exception") or n.endswith("error") or "exception" in n or n in {"assertionerror", "assertionfailederror"}:
            return True
    v = (res_value or "").strip().lower()
    return bool(v) and ("exception" in v or "error" in v)


def _sparql_select(endpoint: str, query: str) -> list[dict[str, dict[str, str]]]:
    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)
    sparql.setQuery(query)
    res = sparql.query().convert()
    return list(res.get("results", {}).get("bindings", []))


@dataclass(frozen=True)
class ChainResult:
    start_uuid: str
    exception_type: str
    exception_value: str
    last_uuid: str
    last_method: str
    baseline_uuid: str
    baseline_method: str
    nodes_in_chain: int
    reachable_nodes_in_chain: int
    path_edges: int
    baseline_path_edges: int
    branching_nodes: int
    error: str | None = None


def _pick_test_method_start(
    bindings: list[dict[str, dict[str, str]]],
) -> tuple[str, str, str] | tuple[None, None, None]:
    """Pick the start invocation among tested-method matches.

    Heuristic:
    - Prefer root node (`uuid == callee`) if present.
    - Prefer rows with an exception marker.
    """

    cand: list[tuple[str, str, str, str, str]] = []
    for b in bindings:
        g = lambda k: (b.get(k, {}) or {}).get("value") or ""
        uuid = g("uuid")
        if uuid:
            cand.append((str(uuid), str(g("callee")), str(g("name")), str(g("resType")), str(g("resValue"))))
    if not cand:
        return None, None, None

    def score(c: tuple[str, str, str, str, str]) -> tuple[int, int, str]:
        uuid, callee, _name, res_type, res_val = c
        return (1 if uuid and callee and uuid == callee else 0, 1 if _is_exception_throwing(res_type, res_val) else 0, uuid)

    uuid, _callee, _name, res_type, res_val = sorted(cand, key=score, reverse=True)[0]
    return uuid, res_type or "", res_val or ""


def find_last_exception_chain_node(
    *,
    endpoint: str,
    graph_uri: str,
    tested_method: str,
) -> ChainResult:
    graph = _quote_graph_iri(graph_uri)
    if not graph:
        return ChainResult("", "", "", "", "", "", "", 0, 0, 0, 0, 0, error="missing graph uri")

    rx = _method_regex_for_tested_method(tested_method)
    if not rx:
        return ChainResult("", "", "", "", "", "", "", 0, 0, 0, 0, 0, error="missing tested method")

    prefix = f"PREFIX ex: <{EX}>\nPREFIX rdf: <{RDF}>\n"
    q = (
        prefix
        + "SELECT ?uuid ?callee ?name ?resType ?resValue WHERE {\n"
        + f"  GRAPH {graph} {{\n"
        + "    ?uuid ex:method ?name ; ex:callee ?callee .\n"
        + "    OPTIONAL { ?uuid ex:result ?resNode . OPTIONAL { ?resNode rdf:type ?resType } OPTIONAL { ?resNode rdf:value ?resValue } }\n"
        + "  }\n"
        + "}\n"
    )
    try:
        all_bindings = _sparql_select(endpoint, q)
    except Exception as e:
        return ChainResult("", "", "", "", "", "", "", 0, 0, 0, 0, 0, error=f"sparql graph query failed: {e}")

    try:
        name_rx = re.compile(rx)
    except re.error as e:
        return ChainResult("", "", "", "", "", "", "", 0, 0, 0, 0, 0, error=f"invalid tested-method regex: {e}")

    start_uuid, exc_type, exc_val = _pick_test_method_start(
        [b for b in all_bindings if name_rx.search(str(((b.get("name", {}) or {}).get("value") or "")))]
    )
    if not start_uuid:
        return ChainResult("", "", "", "", "", "", "", 0, 0, 0, 0, 0, error="no test-method invocation node matched")

    # Build full call tree and per-node result signature.
    callee_of: dict[str, str] = {}
    name_of: dict[str, str] = {}
    res_type_of: dict[str, str] = {}
    res_value_of: dict[str, str] = {}
    children_of: dict[str, list[str]] = {}

    for b in all_bindings:
        g = lambda k: (b.get(k, {}) or {}).get("value") or ""
        uuid = g("uuid")
        if not uuid:
            continue
        u, p = str(uuid), str(g("callee"))
        callee_of[u] = p
        if u not in name_of and g("name"):
            name_of[u] = str(g("name"))
        if u not in res_type_of and g("resType"):
            res_type_of[u] = str(g("resType"))
        if u not in res_value_of and g("resValue"):
            res_value_of[u] = str(g("resValue"))
        if p and u != p:
            children_of.setdefault(p, []).append(u)

    for k, v in list(children_of.items()):
        children_of[k] = sorted(set(v))

    if start_uuid not in callee_of:
        return ChainResult(start_uuid, exc_type, exc_val, "", "", "", "", 0, 0, 0, 0, 0, error="tested-method uuid not present in graph")

    start_res_type = res_type_of.get(start_uuid, exc_type)
    start_res_val = res_value_of.get(start_uuid, exc_val)
    if not _is_exception_throwing(start_res_type, start_res_val):
        return ChainResult(
            start_uuid,
            start_res_type or "",
            start_res_val or "",
            "",
            "",
            "",
            "",
            0,
            0,
            0,
            0,
            error="tested-method node does not look exception-throwing (missing/unknown result)",
        )

    start_method = name_of.get(start_uuid, "")

    memo: dict[str, tuple[str, int]] = {}

    def deepest(u: str, visiting: set[str]) -> tuple[str, int]:
        if u in memo:
            return memo[u]
        if u in visiting:
            memo[u] = (u, 0)
            return memo[u]
        visiting.add(u)
        best_last = u
        best_depth = 0
        for c in children_of.get(u, []):
            if not _is_exception_throwing(res_type_of.get(c, ""), res_value_of.get(c, "")):
                continue
            last, d = deepest(c, visiting)
            if (d + 1 > best_depth) or (d + 1 == best_depth and last and (not best_last or last < best_last)):
                best_last, best_depth = last, d + 1
        visiting.remove(u)
        memo[u] = (best_last, best_depth)
        return memo[u]

    last_uuid, depth_edges = deepest(start_uuid, set())
    last_method = name_of.get(last_uuid, "")

    # Baseline for "root cause" comparisons: skip nodes that are just duplicates of the tested method.
    baseline_uuid = last_uuid
    while baseline_uuid and baseline_uuid != start_uuid and name_of.get(baseline_uuid, "") == start_method:
        baseline_uuid = callee_of.get(baseline_uuid, "")
    if not baseline_uuid:
        baseline_uuid = last_uuid
    baseline_method = name_of.get(baseline_uuid, "")

    baseline_path_edges = 0
    u = baseline_uuid
    while u and u != start_uuid:
        u = callee_of.get(u, "")
        if not u:
            break
        baseline_path_edges += 1
    branching_nodes = sum(
        1
        for u, cs in children_of.items()
        if u in callee_of
        and sum(1 for c in cs if _is_exception_throwing(res_type_of.get(c, ""), res_value_of.get(c, ""))) > 1
    )
    nodes_in_chain = sum(1 for u in callee_of if _is_exception_throwing(res_type_of.get(u, ""), res_value_of.get(u, "")))

    # How many exception-nodes are actually reachable from the tested-method node
    # following only exception-throwing edges.
    reachable: set[str] = set()
    stack = [start_uuid]
    while stack:
        u = stack.pop()
        if u in reachable:
            continue
        reachable.add(u)
        for c in children_of.get(u, []):
            if _is_exception_throwing(res_type_of.get(c, ""), res_value_of.get(c, "")):
                stack.append(c)
    reachable_nodes_in_chain = len(reachable)

    return ChainResult(
        start_uuid=start_uuid,
        exception_type=start_res_type or "",
        exception_value=start_res_val or "",
        last_uuid=last_uuid,
        last_method=last_method,
        baseline_uuid=baseline_uuid,
        baseline_method=baseline_method,
        nodes_in_chain=nodes_in_chain,
        reachable_nodes_in_chain=reachable_nodes_in_chain,
        path_edges=int(depth_edges),
        baseline_path_edges=int(baseline_path_edges),
        branching_nodes=branching_nodes,
        error=None,
    )
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--json",
        default="/home/dschiese/Projekte/10_research/Towards-Functional-Fault-Localization-in-Large-Scale-Distributed-Web-Systems-via-LLMs/data/sheet_smart_with_failure.json",
        help="Input JSON (smart sheet export)",
    )
    ap.add_argument("--endpoint", default="http://localhost:8890/sparql", help="SPARQL endpoint")
    ap.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: alongside input with suffix)",
    )
    ap.add_argument("--limit", type=int, default=0, help="Only process first N exception rows (0 = all)")
    ap.add_argument("--sleep-ms", type=int, default=0, help="Sleep between graphs")
    args = ap.parse_args(argv)

    in_path = Path(args.json)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Input JSON must be a list of objects")

    out_path = (
        Path(args.out)
        if args.out
        else in_path.with_name(in_path.stem + "_with_exception_chain" + in_path.suffix)
    )

    processed = 0
    errors = 0
    missing = 0

    for row in data:
        if not isinstance(row, dict) or not row.get("terminated_by_exception"):
            continue
        graph_uri = str(row.get("Graph", "") or "").strip()
        t = row.get("Test")
        tested_method = str(t.get("Method", "") or "").strip() if isinstance(t, dict) else ""
        if not graph_uri or not tested_method:
            missing += 1
            continue

        res = find_last_exception_chain_node(
            endpoint=str(args.endpoint),
            graph_uri=graph_uri,
            tested_method=tested_method,
        )

        row["ExceptionChain"] = {
            "start_uuid": res.start_uuid,
            "exception_type": res.exception_type,
            "exception_value": res.exception_value,
            "last_uuid": res.last_uuid,
            "last_method": res.last_method,
            "baseline_uuid": res.baseline_uuid,
            "baseline_method": res.baseline_method,
            "nodes_in_chain": res.nodes_in_chain,
            "reachable_nodes_in_chain": res.reachable_nodes_in_chain,
            "path_edges": res.path_edges,
            "baseline_path_edges": res.baseline_path_edges,
            "branching_nodes": res.branching_nodes,
        }
        if res.error:
            row["ExceptionChain"]["error"] = res.error
            errors += 1

        processed += 1
        if args.sleep_ms > 0:
            time.sleep(float(args.sleep_ms) / 1000.0)
        if args.limit > 0 and processed >= args.limit:
            break
        if processed % 10 == 0:
            print(f"processed={processed} errors={errors} missing={missing}", file=sys.stderr)

    out_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"processed": processed, "errors": errors, "missing": missing, "out": str(out_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
