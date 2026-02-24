import json
import os

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "http://localhost:8890/sparql")
EXPERIMENTS_FILE = os.getenv("EXPERIMENTS_FILE", "data/experiments.xlsx")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "data/experiments_updated.xlsx")


def run_consistency_check():
    """Check whether LLM-predicted class/method names exist in the call trees.

    Reads experiment data from Excel, queries the Virtuoso SPARQL endpoint for
    each prediction, and writes the hallucination-check results back to Excel.
    Results are used in Section 5.2 of the paper.
    """
    df = pd.read_excel(EXPERIMENTS_FILE, header=1)

    with open("prompts/ask_if_llm_in_calltree.txt", "r") as f:
        template = f.read()

    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setReturnFormat(JSON)

    for _, row in df.iterrows():
        print("----------------------------------------")
        nr = row["Nr"]
        graph = row["Graph"]
        raw_llm_response = row["LLM response"]

        try:
            llm_response = json.loads(raw_llm_response)
            if not llm_response.get("class") or not llm_response.get("method"):
                print(f"Skipping Nr {nr}: missing class or method in LLM response")
                continue
        except Exception as e:
            print(f"Skipping Nr {nr}: error parsing LLM response - {e}")
            continue

        pred_class = llm_response["class"]
        pred_method = llm_response["method"]

        # Check if the predicted class appears anywhere in the call tree
        sparql.setQuery(template.replace("{{TARGET}}", pred_class).replace("{{GRAPH}}", graph))
        class_is_in_calltree = sparql.query().convert()["boolean"]

        # Check if the predicted method name appears anywhere in the call tree
        sparql.setQuery(template.replace("{{TARGET}}", pred_method).replace("{{GRAPH}}", graph))
        method_is_in_calltree = sparql.query().convert()["boolean"]

        # Check if the fully-qualified "class.method" combination appears in the call tree
        sparql.setQuery(template.replace("{{TARGET}}", f"{pred_class}.{pred_method}").replace("{{GRAPH}}", graph))
        complete_is_in_calltree = sparql.query().convert()["boolean"]

        print(f"Nr {nr}: class_exists={class_is_in_calltree}, method_exists={method_is_in_calltree}, complete_exists={complete_is_in_calltree}")

        df.loc[df["Nr"] == nr, "Class Exist"] = class_is_in_calltree
        df.loc[df["Nr"] == nr, "Method Exist"] = method_is_in_calltree
        df.loc[df["Nr"] == nr, "Complete Exist"] = complete_is_in_calltree

    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    run_consistency_check()
