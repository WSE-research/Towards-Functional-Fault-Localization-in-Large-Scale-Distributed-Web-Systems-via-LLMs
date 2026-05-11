import json
import os
import gspread
from google.oauth2.service_account import Credentials

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

SPARQL_ENDPOINT = os.getenv("SPARQL_ENDPOINT", "http://localhost:8890/sparql")
EXPERIMENTS_FILE = os.getenv("EXPERIMENTS_FILE", "https://docs.google.com/spreadsheets/d/1WYs9NuY2V4mdaYyD1a7c9ffCQEq67qFwK_9aUvGfUnk/export?format=xlsx")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def run_consistency_check():
    """Check whether LLM-predicted class/method names exist in the call trees.

    Reads experiment data from Excel, queries the Virtuoso SPARQL endpoint for
    each prediction, and writes the hallucination-check results back to Excel.
    Results are used in Section 5.2 of the paper.
    """
    creds = Credentials.from_service_account_file("pipeline/credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet_url = EXPERIMENTS_FILE.replace("/export?format=xlsx", "/edit?usp=sharing")
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.sheet1
    headers = [str(h).strip() for h in worksheet.row_values(2)]

    df = pd.read_excel(EXPERIMENTS_FILE, header=1)

    with open("prompts/ask_if_llm_in_calltree.txt", "r") as f:
        template = f.read()

    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setReturnFormat(JSON)

    for index, row in df.iterrows():
        print("----------------------------------------")
        sheet_row = index + 3
        nr = row["Nr"]
            
        graph = row["Graph"]
        raw_llm_response = row["Result for google/gemini-3-flash-preview"]

        if pd.isna(raw_llm_response):
            print(f"Skipping Nr {nr}: no LLM response")
            continue

        # Clean JSON block
        if isinstance(raw_llm_response, str):
            raw_llm_response = raw_llm_response.strip()
            if raw_llm_response.startswith("```json"):
                raw_llm_response = raw_llm_response[len("```json"):].strip()
            if raw_llm_response.endswith("```"):
                raw_llm_response = raw_llm_response[:-3].strip()

        try:
            llm_response = json.loads(raw_llm_response)
            if not llm_response.get("class") or not llm_response.get("method"):
                print(f"Skipping Nr {nr}: missing class or method in LLM response")
                continue
        except Exception as e:
            print(f"Skipping Nr {nr}: error parsing LLM response - {e}")
            continue

        pred_class = llm_response["class"] if str(row.get("Class Correct GE")).strip().upper() == "F" else ""
        pred_method = llm_response["method"] if str(row.get("Method Correct GE")).strip().upper() == "F" else ""
        
        print(f"Nr {nr}: Parsed JSON -> class='{pred_class}', method='{pred_method}'")

        class_is_in_calltree = ""
        method_is_in_calltree = ""
        complete_is_in_calltree = ""

        if pred_class:
            # Check if the predicted class appears anywhere in the call tree
            sparql.setQuery(template.replace("{{TARGET}}", pred_class).replace("{{GRAPH}}", graph))
            class_is_in_calltree = bool(sparql.query().convert()["boolean"])

        if pred_method:
            # Check if the predicted method name appears anywhere in the call tree
            sparql.setQuery(template.replace("{{TARGET}}", pred_method).replace("{{GRAPH}}", graph))
            method_is_in_calltree = bool(sparql.query().convert()["boolean"])

        if pred_class and pred_method:
            # Check if the fully-qualified "class.method" combination appears in the call tree
            sparql.setQuery(template.replace("{{TARGET}}", f"{pred_class}.{pred_method}").replace("{{GRAPH}}", graph))
            complete_is_in_calltree = bool(sparql.query().convert()["boolean"])

        print(f"Nr {nr}: class_exists={class_is_in_calltree}, method_exists={method_is_in_calltree}, complete_exists={complete_is_in_calltree}")

        if "Class Exist GE" in headers:
            worksheet.update_cell(sheet_row, headers.index("Class Exist GE") + 1, class_is_in_calltree)
        if "Method Exist GE" in headers:
            worksheet.update_cell(sheet_row, headers.index("Method Exist GE") + 1, method_is_in_calltree)

    print(f"Results written to Google Sheets at {sheet_url}")


if __name__ == "__main__":
    run_consistency_check()
