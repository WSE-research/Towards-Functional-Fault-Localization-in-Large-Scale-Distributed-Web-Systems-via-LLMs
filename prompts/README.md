# LLM Prompt Templates

This directory contains all prompt templates used when calling LLMs in the pipeline and evaluation.

## Templates

### `analysis_prompt.txt`
**Used in:** `pipeline/fetch_and_analyze.py` (Step 1)

Instructs the LLM to analyze a patch file and test log to extract:
- `patched`: list of fully-qualified class names modified by the fix
- `test`: list of failing test class names

Input placeholders: `{patch}`, `{test_results}`

### `evaluation_prompt.txt`
**Used in:** `pipeline/evaluate_calltree.py` (Step 4)

The main fault localization prompt shown as Figure 3 in the paper. Instructs the LLM to identify the faulty class and method from an XML-serialized call tree. Explicitly asks the model to reason beyond just the exception-throwing site.

Input placeholder: `{calltree_xml}`

Output: `{"class": "<CLASS_NAME>", "method": "<METHOD_NAME>"}`

The model is selected dynamically based on token count (GPT-5 ≤ 400k, Gemini ≤ 1M, Grok ≤ 2M tokens).

### `test_method_prompt.txt`
**Used in:** `pipeline/find_method_for_suitable_testclasses.py` (Step 2)

Extracts the specific failing test method for a given test class from the Maven test log.

Output: `{"failingTests": [{"failingTestClass": "...", "failingTestMethod": "..."}]}`

### `ask_if_patched_in_calltree.txt`
**Used in:** `evaluation/check_if_patched_in_calltree.py` (Step 5)

SPARQL ASK query template that checks whether the patched class appears in a given call graph (identified by its Virtuoso graph URI).

### `ask_if_llm_in_calltree.txt`
**Used in:** `evaluation/llm_consistency_check.py`

SPARQL ASK query template that checks whether the LLM-predicted class/method appears in the call graph. Used for the hallucination check described in Section 5.2 of the paper.
