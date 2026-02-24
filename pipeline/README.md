# Pipeline: Data Collection and Analysis

This directory contains all Python scripts and notebooks that implement the six-step data preparation pipeline described in Section 4 of the paper.

## Scripts

### Step 1 – Branch Analysis

**`fetch_and_analyze.py`**
Iterates over all branches of the bugs-dot-jar GitHub organization across 8 projects. For each branch, it fetches the `developer-patch.diff` and `test-results.txt` via the GitHub API, then sends them to an LLM (via the `analysis_prompt.txt` template) to extract:
- The fully-qualified patched class names (`patched`)
- The failing test class names (`test`)

Results are written to `outputs/<project>/<branch>/analysis.json`.

### Step 2 – Filtering Suitable Tests

**`check_test_equi.py`**
Identifies branches where all failing tests directly test the patched class (e.g., `FooTest` tests `Foo`). These are excluded because they represent unit tests, not distributed integration traces.

**`enrich_analysis_with_non_equi_tests.py`**
Enriches each `analysis.json` with a `suitable_tests` field containing only test classes whose names do not match the patched class name. This implements the filter from Step 2.

**`find_method_for_suitable_testclasses.py`**
For each suitable test class, calls an LLM (using `test_method_prompt.txt`) to identify the specific failing test method from the `test-results.txt` log. Adds a `suitable_test_methods` field to `analysis.json`.

**`extract_source_package.py`**
Parses `test-results.txt` to extract the Maven source module/package. Adds `sourcePackage` to `analysis.json`.

**`check_working_jdk_and_suitable_projects.py`**
Validates which projects compiled successfully and have at least one suitable test. Generates `data/working-examples-jdk6-with-suitable-tests.txt`. Prerequisite to this is the working-examples-jdk6.txt (data/working-examples-jdk6.txt), which contains all projects that compiled successfully using the JDK6 approach explained in the setup directory. As stated in the paper, 186 compiled successfully.

### Step 4 – Execute Tests and Store Call Graph

**`evaluate_calltree.py`**
For a given experiment (identified by a Virtuoso graph URI), retrieves the call tree XML via `build_hierarchy.py`, injects it into the evaluation prompt (`prompts/evaluation_prompt.txt`), and submits it to the LLM for fault localization. Dynamically selects the model based on token count:
- GPT-5 for ≤ 400,000 tokens
- Gemini-3-flash-preview for ≤ 1,000,000 tokens
- Grok-4.1-fast for ≤ 2,000,000 tokens

**`build_hierarchy.py`**
Queries the local Virtuoso SPARQL endpoint to reconstruct the call tree as an XML string. Traverses the `ex:called` predicate to serialize the full caller–callee hierarchy with method arguments and return values.

## Config
In the following, the required environment variables are listed and need to be set to reproduce this workflow.

Key variables:

| Variable | Used by | Description |
|----------|---------|-------------|
| `GITHUB_PAT` | `fetch_and_analyze.py` | GitHub Personal Access Token |
| `OPENROUTER_API_KEY` | `evaluate_calltree.py` | OpenRouter API key (https://openrouter.ai/) |
| `ANALYSIS_API_BASE` | `helper.py` | Base URL for the analysis LLM |
| `ANALYSIS_API_KEY` | `helper.py` | API key for the analysis LLM |
| `ANALYSIS_MODEL` | `helper.py` | Model name for the analysis LLM |
| `SPARQL_ENDPOINT` | `build_hierarchy.py` | Virtuoso SPARQL endpoint URL |

## Running the Pipeline

```bash
# Step 1: fetch and LLM-analyze all branches
python pipeline/fetch_and_analyze.py

# Step 2: filter suitable tests
python pipeline/check_test_equi.py
python pipeline/enrich_analysis_with_non_equi_tests.py
python pipeline/find_method_for_suitable_testclasses.py
python pipeline/extract_source_package.py

# Step 4 (after environment setup and compilation – see setup/):
python pipeline/evaluate_calltree.py --graph <GRAPH_URI>
```