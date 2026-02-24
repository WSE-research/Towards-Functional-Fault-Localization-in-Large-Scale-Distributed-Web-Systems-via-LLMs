# Online Appendix: Towards Functional Fault Localization in Large-Scale Distributed Web Systems through LLMs

**Paper:** Dennis Schiese and Andreas Both. "Towards Functional Fault Localization in Large-Scale Distributed Web Systems through LLMs." ICWE 2026.

**Authors:** Web & Software Engineering (WSE) Research Group, Leipzig University of Applied Sciences (HTWK Leipzig)

---

## Overview

This repository serves as the online appendix for the paper. It contains all scripts, prompts, data, and results required to reproduce and understand the experiments. The approach uses LLM-driven fault localization in distributed systems by analyzing call trees of failing test processes, without access to source code.

The evaluation covers **53 real-world bug instances** from the [bugs-dot-jar](https://github.com/bugs-dot-jar/bugs-dot-jar) dataset across 6 Java projects, with call traces ranging from 4 to 10,000 calls.

---

## Repository Structure

```
.
├── README.md                  # This file
│
├── setup/                     # Step 3: Environment setup guide (JDK 6, Maven, AspectJ)
│   ├── methodaspect/          # Local Maven repository: methodaspect-0.1.0 tracing agent
│   ├── templates/             # pom.xml snippets (dependency + Surefire plugin)
│   └── maven3.2.5-jdk6/       # Git submodule: Docker image with JDK 6 + Maven 2.5.3
├── jdk/                       # Step 3: Script to batch-compile branches under JDK 6 via Docker
├── pipeline/                  # Steps 1–2, 4–6: Data collection and analysis pipeline
├── prompts/                   # LLM prompt templates used in the pipeline and SPARQL query templates
├── data/                      # Input datasets and experiment reference data
├── outputs/                   # Per-bug analysis artifacts (analysis.json, patches, test logs)
├── evaluation/                # Evaluation scripts and notebooks (distances, consistency checks)
└── results/                   # Experiment results data, visualizations, and notebooks
└── scripts/                   # Subset of checked-out bug branch source trees from the bugs-dot-jar dataset
```

---

## Experimental Pipeline (6 Steps from the Paper)

The analysis and preparation of the bugs-dot-jar dataset follows six steps described in Section 4 of the paper:

| Step | Description | Location |
|------|-------------|----------|
| **Step 1** – Branch analysis | Fetch patches and test results from GitHub; extract patched classes and failing test classes using an LLM | [`pipeline/fetch_and_analyze.py`](pipeline/fetch_and_analyze.py) |
| **Step 2** – Filter suitable tests | Remove tests that directly test the patched class (i.e., FooTest for Foo) | [`pipeline/check_test_equi.py`](pipeline/check_test_equi.py), [`pipeline/enrich_analysis_with_non_equi_tests.py`](pipeline/enrich_analysis_with_non_equi_tests.py) |
| **Step 3** – Environment setup | Compile all branches using JDK 6 + Maven 2.5.3; configure AspectJ tracing agent | [`setup/`](setup/), [`jdk/`](jdk/) |
| **Step 4** – Execute tests and store call graph | Run each suitable test under the AspectJ tracing agent; store the full call tree in a Virtuoso RDF knowledge graph | [`pipeline/evaluate_calltree.py`](pipeline/evaluate_calltree.py) |
| **Step 5** – Consistency check | Verify that the patched class and method appear in each recorded call graph | [`evaluation/check_if_patched_in_calltree.py`](evaluation/check_if_patched_in_calltree.py) |
| **Step 6** – Call threshold filtering | Exclude call graphs exceeding the LLM context window limit (~10,000 calls / 1,000,000 tokens) | [`evaluation/check_if_patched_in_calltree.py`](evaluation/check_if_patched_in_calltree.py) |

---

## LLM Usage per Experiment

As referenced in Figure 4 of the paper, the data file [`data/experiments.xlsx`](data/experiments.xlsx) contains per-experiment details including:
- The LLM selected for each experiment (GPT-5, Gemini-3-flash-preview, or Grok-4.1-fast)
- The number of calls in the call tree
- The predicted and patched class/method
- Correctness of the prediction (super-component and sub-component level)

---

## Requirements

- **Python 3.x** with: `requests`, `jsonschema`, `SPARQLWrapper`, `pandas`, `scipy`, `tiktoken`
- **Virtuoso** RDF triple store (for call graph storage): `docker run openlink/virtuoso-opensource-7`
- **JDK 6** (TLS 1.2 compatible build) + **Maven 2.5.3** (for Step 3 – see [`setup/`](setup/))
- **OpenRouter API key** (for LLM calls in Steps 1 and 4)

---

## Dataset

The [bugs-dot-jar](https://github.com/bugs-dot-jar/bugs-dot-jar) dataset provides one branch per bug, each containing:
- `developer-patch.diff` – the ground-truth fix
- A failing JUnit test case

All per-branch analysis artifacts produced by this pipeline are stored in [`outputs/`](outputs/) organized by project and branch name.
