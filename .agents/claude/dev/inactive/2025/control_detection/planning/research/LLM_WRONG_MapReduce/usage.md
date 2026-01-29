To run the full LLM_WRONG (false-negatives) MapReduce flow:

  uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run \
    --mode false-negatives \
    --all \
    -n 3

  Options explained:

  | Flag                   | Description                                                   |
  |------------------------|---------------------------------------------------------------|
  | --mode false-negatives | Use false-negative analysis mode (analyzes LLM_WRONG entries) |
  | --all                  | Run full aggregation until convergence                        |
  | -n 3                   | Process 3 pairs in parallel (adjust based on API rate limits) |

  Optional flags:

  # Limit rounds (useful for testing)
  --max-rounds 2

  # Set random seed for reproducible ordering
  --seed 42

  # Dry run to preview without calling LLM
  --dry-run

  Output location:

  ai_services/scripts/experiments/control_detection/files/experiments/template_policies/failure_patterns/
  ├── round_1/           # Round 1 outputs
  ├── round_2/           # Round 2 outputs
  ├── ...
  ├── final_output.json  # Complete JSON
  ├── universal_rules.md # Merged/common failure patterns
  └── rare_rules.md      # Unique edge-case patterns

  Quick test (single round):

  uv run python -m ai_services.scripts.experiments.control_detection.reason_aggregator.run \
    --mode false-negatives \
    --all \
    --max-rounds 1 \
    -n 1