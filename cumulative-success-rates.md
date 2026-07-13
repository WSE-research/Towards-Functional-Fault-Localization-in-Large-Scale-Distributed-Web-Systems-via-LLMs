# Cumulative Success Rates per Call-Trace Size

Raw data underlying the success-rate visualization (Fig. 3b in the paper):
cumulative success rate for service and module localization across all 53
evaluated experiments, aggregated in 1,000-call thresholds. Each row reports
the results for all experiments whose call trace contains fewer calls than the
threshold (cumulative, not per-bin).

- **Calls I** — upper bound on the number of calls (edges) in the recorded call trace.
- **Occurrences** — number of experiments below the threshold.
- **Service correct / success rate** — predictions naming the correct faulty service (class).
- **Module correct / success rate** — predictions naming the correct faulty module (method).

| Calls I  | Occurrences | Service correct | Service success rate | Module correct | Module success rate |
|----------|-------------|-----------------|----------------------|----------------|---------------------|
| < 1,000  | 31          | 29              | 93.55%               | 28             | 90.32% (max)        |
| < 2,000  | 39          | 37              | 94.87% (max)         | 33             | 84.62%              |
| < 3,000  | 42          | 37              | 88.10%               | 33             | 78.57%              |
| < 4,000  | 47          | 40              | 85.11%               | 35             | 74.47% (min)        |
| < 5,000  | 48          | 41              | 85.42%               | 36             | 75.00%              |
| < 6,000  | 48          | 41              | 85.42%               | 36             | 75.00%              |
| < 7,000  | 49          | 41              | 83.67%               | 37             | 75.51%              |
| < 8,000  | 51          | 42              | 82.35%               | 39             | 76.47%              |
| < 9,000  | 52          | 42              | 80.77%               | 40             | 76.92%              |
| ≤ 10,000 | 53          | 42              | 79.25% (min)         | 40             | 75.47%              |

Notes:

- The last row covers all 53 experiments and matches the overall accuracy
  reported in the paper (79.25% service, 75.47% module).
- (max)/(min) mark the highest and lowest cumulative success rate per column.
- The service success rate peaks at < 2,000 calls (94.87%) and declines with
  increasing trace size; the module success rate peaks below 1,000 calls
  (90.32%), drops to its minimum at < 4,000 calls (74.47%), and then plateaus
  around 75%.
