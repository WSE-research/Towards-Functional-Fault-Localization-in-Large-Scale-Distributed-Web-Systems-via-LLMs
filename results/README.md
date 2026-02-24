# Results

This directory contains the final experiment results, evaluation data, and visualizations produced by the pipeline.

## Files

### Experiment Data

**`experiments.xlsx`** (see [`../data/experiments.xlsx`](../data/experiments.xlsx))
The primary results spreadsheet. For each of the 53 evaluated experiments, it records:
- Bug identifier (project + branch)
- Number of calls in the call tree
- Distinct super-components (classes) and sub-components (methods)
- LLM used (GPT-5, Gemini-3-flash-preview, or Grok-4.1-fast)
- LLM-predicted class and method
- Ground-truth patched class and method
- Correctness at super-component level (class)
- Correctness at sub-component level (method)
- Patch–Prediction distance `D(c_pred, c_patched)`
- Test–Patch distance `D(c_entry, c_patched)`

### Notebooks

**`vis_eval.ipynb`**
Primary visualization and evaluation notebook.

**`visualize_call_graph.ipynb`**
Notebook for rendering individual call graphs. Loads a call tree from the Virtuoso SPARQL endpoint and produces a visual graph representation useful for manual inspection of specific experiments.

### Images

The `images/` directory contains all figures used in the paper.
