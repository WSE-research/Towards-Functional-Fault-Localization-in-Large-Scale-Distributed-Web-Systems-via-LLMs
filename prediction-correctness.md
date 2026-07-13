# Prediction Correctness per Project

Per-project breakdown of the fault-localization correctness across all 53 evaluated
experiments (cf. the paper's Evaluation section). Each experiment corresponds to one
bugs-dot-jar bug: a failing test execution whose recorded call trace was given to the
LLM pipeline, which returned one predicted fault location (service and module).

- **Sample size n** — number of experiments derived from the project.
- **Service correct** — predictions naming the correct faulty service (class).
- **Module correct** — predictions naming the correct faulty module (method).

| Project  | Sample size n | Service correct | Service correct ratio | Module correct | Module correct ratio |
|----------|---------------|-----------------|-----------------------|----------------|----------------------|
| MATH     | 18            | 14              | 77.78%                | 11             | 61.11%               |
| WICKET   | 16            | 13              | 81.25%                | 15             | 93.75%               |
| OAK      | 10            | 8               | 80.00%                | 7              | 70.00%               |
| LOG4J2   | 7             | 6               | 85.71%                | 5              | 71.43%               |
| ACCUMULO | 1             | 1               | 100.00%               | 1              | 100.00%              |
| MNG      | 1             | 0               | 0.00%                 | 1              | 100.00%              |
| **Total** | **53**       | **42**          | **79.25%**            | **40**         | **75.47%**           |

Notes:

- The totals match the overall accuracy reported in the paper (79.25% service,
  75.47% module across all 53 experiments); the absolute counts are derived from
  the per-project ratios and sample sizes.
- WICKET and LOG4J2 yield the best correctness ratios among projects with more
  than one sample.
- ACCUMULO and MNG contribute one experiment each; their 0%/100% ratios are
  anecdotal and should not be interpreted as project-level trends.
- Project keys refer to the bugs-dot-jar projects: Apache Commons Math (MATH),
  Apache Wicket (WICKET), Apache Jackrabbit Oak (OAK), Apache Log4j2 (LOG4J2),
  Apache Accumulo (ACCUMULO), and Apache Maven (MNG).
