# Evaluation Scripts

This directory contains scripts and notebooks for evaluating the fault localization results against the ground truth (Steps 5–6 of the pipeline) and computing the metrics reported in Section 5 of the paper.

## Scripts

### Consistency Check (Step 5)

**`check_if_patched_in_calltree.py`**
For each experiment, verifies that the patched class and method appear somewhere in the recorded call graph (via SPARQL ASK queries against the Virtuoso endpoint). Experiments where the fault location is absent from the call graph are excluded. Also computes the Patch–Prediction distance `D(c_pred, c_patched)` and the Test–Patch distance `D(c_entry, c_patched)` using shortest-path analysis.

**`dijkstra_kg.py`**
Queries the SPARQL endpoint to build an undirected adjacency matrix from the `ex:called` triples, then computes shortest paths between any two nodes using sparse-matrix Floyd-Warshall (scipy). Used by `check_if_patched_in_calltree.py` for distance calculations.

**`llm_consistency_check.py`**
Secondary consistency check (referenced in Section 5.2 of the paper as "hallucination check"): verifies whether the LLM-predicted class/method actually exists anywhere in the call tree. Identifies hallucinated predictions that would result in infinite distances.

**`query_graph_metadata.py`**
Returns statistics for a given Virtuoso graph:
- Total number of method calls (edges)
- Distinct method calls
- Distinct class calls

Useful for understanding the structural properties summarized in Table 1 of the paper.

## Configuration

All scripts read credentials and endpoints from environment variables. Copy `.env.example` from the repository root and fill in your values:

```bash
cp .env.example .env
# edit .env
```

| Variable | Description |
|----------|-------------|
| `SPARQL_ENDPOINT` | Virtuoso SPARQL endpoint URL (default: `http://localhost:8890/sparql`) |
| `EXPERIMENTS_FILE` | Path to the experiments spreadsheet (default: `data/experiments.xlsx`) |
| `OUTPUT_FILE` | Output path for `llm_consistency_check.py` (default: `data/experiments_updated.xlsx`) |

To start Virtuoso via Docker:
```bash
docker run -p 8890:8890 openlink/virtuoso-opensource-7
```
