import argparse
import itertools
import json
import os

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
from dijkstra_kg import shortest_path

SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "http://localhost:8890/sparql")
EXPERIMENTS_FILE = os.getenv("EXPERIMENTS_FILE", "data/experiments.xlsx")

LIMIT_CALLS = 5000

# SPARQL ASK query: checks if an arbitrary pattern occurs in the call tree
CC1_QUERY = """
ASK
FROM <{{GRAPH}}>
WHERE {
  ?s ?p ?o .
  FILTER(REGEX(STR(?o), "{{PATTERN}}"))
}

"""


def calculate_method_hops(nr, graph, patched_classes, patched_methods, llm_result,
                          llm_method_exist_in_calltree, patch_exist_in_calltree, project):
    """Calculate shortest distance D(c_pred, c_patched) between LLM prediction and patched method."""
    if not llm_result:
        print(f"Nr {nr}: No LLM result provided.")
        return
    if llm_method_exist_in_calltree and patch_exist_in_calltree:
        current_shortest_distance = None
        for combo in itertools.product(patched_classes, patched_methods):
            distance, _, _, _ = shortest_path(
                graph_uri=graph,
                src=combo[0],
                dst=llm_result["class"],
            )
            if distance is not None:
                if current_shortest_distance is None or distance < current_shortest_distance:
                    current_shortest_distance = distance
        print(f"Nr {nr}: D(c_pred, c_patched) = {current_shortest_distance} (project: {project})")
    else:
        print(f"Nr {nr}: Cannot calculate distance — patched method or LLM prediction not in call tree.")


def calculate_tested_hops(nr, graph, patched_classes, patched_methods, tested_class,
                          tested_method, patch_exist_in_calltree, project):
    """Calculate shortest distance D(c_entry, c_patched) between test entry and patched method."""
    if patch_exist_in_calltree:
        current_shortest_distance = None
        for combo in itertools.product(patched_classes, patched_methods):
            distance, _, _, _ = shortest_path(
                graph_uri=graph,
                src=combo[0] + "." + combo[1],
                dst=tested_class + "." + tested_method,
            )
            if distance is not None:
                if current_shortest_distance is None or distance < current_shortest_distance:
                    current_shortest_distance = distance
        print(f"Nr {nr}: D(c_entry, c_patched) = {current_shortest_distance} (project: {project})")
    else:
        print(f"Nr {nr}: Patched method not in call tree, cannot calculate distance.")


def calculate_tested_llm_hops(nr, graph, tested_class, tested_method, llm_result, method_exist, project):
    """Calculate shortest distance between test entry and LLM-predicted method."""
    if not llm_result:
        print(f"Nr {nr}: No LLM result provided.")
        return
    if method_exist:
        distance, _, _, _ = shortest_path(
            graph_uri=graph,
            src=tested_class + "." + tested_method,
            dst=llm_result["class"] + "." + llm_result["method"],
        )
        print(f"Nr {nr}: D(c_entry, c_pred) = {distance} (project: {project})")
    else:
        print(f"Nr {nr}: LLM-predicted method not in call tree, cannot calculate distance.")


def consistency_check_1(patched_classes, patched_methods, graph, nr):
    """Check if any combination of patched class and method appears in the call tree (Step 5)."""
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setReturnFormat(JSON)
    for combo in itertools.product(patched_classes, patched_methods):
        query = CC1_QUERY.replace("{{GRAPH}}", graph).replace(
            "{{PATTERN}}", combo[0] + "(\\\\$.*)?\\\\." + combo[1]
        )
        sparql.setQuery(query)
        results = sparql.query().convert()
        if results["boolean"]:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Calculate graph distances between call tree nodes.")
    parser.add_argument("--method-hops", action="store_true",
                        help="Calculate D(c_pred, c_patched): LLM prediction vs. patched method.")
    parser.add_argument("--tested-hops", action="store_true",
                        help="Calculate D(c_entry, c_patched): test entry vs. patched method.")
    parser.add_argument("--tested-llm-hops", action="store_true",
                        help="Calculate D(c_entry, c_pred): test entry vs. LLM prediction.")
    parser.add_argument("--cc1", action="store_true",
                        help="Run consistency check: verify patched methods appear in call tree.")
    parser.add_argument("--all", dest="all_checks", action="store_true",
                        help="Run all checks (default when no flag is given).")
    args = parser.parse_args()

    # Default: run all checks when no specific flag is provided
    run_all = args.all_checks or not (args.method_hops or args.tested_hops or args.tested_llm_hops or args.cc1)

    df = pd.read_excel(EXPERIMENTS_FILE, header=1)

    for _, row in df.iterrows():
        nr = row["Nr"]
        graph = row["Graph"]
        project = row["Repository"]
        patched_classes = str(row["Patched class"]).split(",")
        patched_methods = str(row["Patched method"]).split(",")
        tested_class = row["Tested Class"]
        tested_method = row["Tested Method"]
        patch_exist_in_calltree = row["Included (patch exists within calltree)"]
        method_exist_val = row["Method Exist"]
        llm_method_exist_in_calltree = (method_exist_val == 1.0) or pd.isna(method_exist_val)

        llm_result_str = row["LLM result"]
        llm_result = None if pd.isna(llm_result_str) else json.loads(llm_result_str)

        if run_all or args.method_hops:
            calculate_method_hops(nr, graph, patched_classes, patched_methods, llm_result,
                                  llm_method_exist_in_calltree, patch_exist_in_calltree, project)

        if run_all or args.tested_hops:
            calculate_tested_hops(nr, graph, patched_classes, patched_methods, tested_class,
                                  tested_method, patch_exist_in_calltree, project)

        if run_all or args.tested_llm_hops:
            calculate_tested_llm_hops(nr, graph, tested_class, tested_method, llm_result,
                                      llm_method_exist_in_calltree, project)

        if run_all or args.cc1:
            exists = consistency_check_1(patched_classes, patched_methods, graph, nr)
            print(f"Nr {nr}: Consistency check — patched method in call tree: {exists}")


if __name__ == "__main__":
    main()
