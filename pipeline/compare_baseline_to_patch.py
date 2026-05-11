#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_baseline_class_method(baseline_method: str) -> tuple[str, str] | tuple[None, None]:
    s = (baseline_method or "").strip()
    if not s:
        return None, None
    # Drop any trailing signature like "foo.Bar.baz(int,String)".
    s = s.split("(", 1)[0]
    parts = [p for p in s.split(".") if p]
    if len(parts) < 2:
        return None, None
    cls = parts[-2]
    m = parts[-1]
    return cls, m


def _class_variants(cls: str) -> list[str]:
    """Return class-name variants for inner classes.

    Example: "CacheLIRS$Segment" -> ["CacheLIRS$Segment", "CacheLIRS", "Segment"]
    """

    c = (cls or "").strip()
    if not c:
        return []
    out = [c]
    if "$" in c:
        outer, inner = c.split("$", 1)[0], c.rsplit("$", 1)[-1]
        if outer and outer not in out:
            out.append(outer)
        if inner and inner not in out:
            out.append(inner)
    return out


def _parse_patch_nodes(nodes: str) -> list[str]:
    # Patch["Nodes"] looks like: "Class.method" or "A.m, B.n".
    raw = (nodes or "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _class_method_from_patch_node(node: str) -> tuple[str, str] | tuple[None, None]:
    s = (node or "").strip()
    if not s:
        return None, None
    s = s.split("(", 1)[0]
    parts = [p for p in s.split(".") if p]
    if len(parts) < 2:
        return None, None
    return parts[-2], parts[-1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare ExceptionChain baseline_method to Patch.Nodes")
    ap.add_argument(
        "--json",
        default="/home/dschiese/Projekte/10_research/Towards-Functional-Fault-Localization-in-Large-Scale-Distributed-Web-Systems-via-LLMs/data/sheet_smart_with_failure_with_exception_chain.json",
        help="Input JSON (list of objects)",
    )
    ap.add_argument("--out", default=None, help="Output JSON path (default: alongside input with suffix)")
    args = ap.parse_args(argv)

    in_path = Path(args.json)
    data = json.loads(in_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Input JSON must be a list of objects")

    out_path = Path(args.out) if args.out else in_path.with_name(in_path.stem + "_with_baseline_patch_check" + in_path.suffix)

    for row in data:
        if not isinstance(row, dict):
            continue

        patch = row.get("Patch") if isinstance(row.get("Patch"), dict) else {}
        ec = row.get("ExceptionChain") if isinstance(row.get("ExceptionChain"), dict) else {}

        patch_nodes = _parse_patch_nodes(str(patch.get("Nodes", "") or ""))
        baseline_method = str(ec.get("baseline_method", "") or "")

        cls, m = _parse_baseline_class_method(baseline_method)
        if not cls or not m:
            row["BaselinePatchCheck"] = {
                "class": False,
                "method": False,
                "baseline": "",
                "error": "missing/invalid ExceptionChain.baseline_method",
            }
            continue

        baseline_simple = f"{cls}.{m}"
        baseline_candidates = [f"{c}.{m}" for c in _class_variants(cls)]

        patch_pairs = [_class_method_from_patch_node(n) for n in patch_nodes]
        patch_pairs = [(c, mm) for (c, mm) in patch_pairs if c and mm]
        patch_simple = {f"{c}.{mm}" for (c, mm) in patch_pairs}
        patch_classes = {c for (c, _mm) in patch_pairs}
        patch_methods = {mm for (_c, mm) in patch_pairs}

        exact = any(c in patch_simple for c in baseline_candidates)
        class_ok = True if exact else any(c in patch_classes for c in _class_variants(cls))
        method_ok = True if exact else (m in patch_methods)

        row["BaselinePatchCheck"] = {
            "class": bool(class_ok),
            "method": bool(method_ok),
            "baseline": baseline_simple,
        }

    out_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(out_path), "rows": len(data)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
