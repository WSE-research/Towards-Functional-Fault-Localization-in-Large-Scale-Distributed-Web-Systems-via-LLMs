# Correlation Matrix: Calls vs. Distinct Services and Modules

Raw data for the correlation analysis referenced in the paper's Evaluation
section: Pearson correlations between the number of calls (edges in the call
trace), the number of distinct services (classes), and the number of distinct
modules (methods), computed over all 115 traced experiments (not limited to
the 53 experiments suitable for service and module prediction).

| Pair                  | < 10,000 calls (n=69) | ≥ 10,000 calls (n=46) | All (n=115) |
|-----------------------|-----------------------|-----------------------|-------------|
| Calls ↔ services      | 0.6171                | 0.9737                | 0.9734      |
| Calls ↔ modules       | 0.6472                | 0.9750                | 0.9750      |
| Services ↔ modules    | 0.9787                | 0.9998                | 0.9997      |

Notes:

- Within the < 10,000-call subset the calls↔services/modules correlations are
  weaker (≈ 0.62–0.65) than in the ≥ 10,000-call subset, but over all
  experiments the relationship is almost linear (≥ 0.97).
- The near-perfect services↔modules correlation (> 0.99 overall) may indicate
  a comparable separation of concerns across the projects: classes exhibit
  similar levels of complexity.
- Consequence for the paper's analysis: since the number of calls strongly
  correlates with both the number of distinct services and modules, the number
  of calls suffices as the single complexity axis; no separate accuracy
  breakdown per distinct-service/module counts is required.
