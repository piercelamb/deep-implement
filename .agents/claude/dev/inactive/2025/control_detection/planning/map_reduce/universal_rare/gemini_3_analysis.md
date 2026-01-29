This is a well-structured and logical plan that directly addresses the "pattern proliferation" and "token waste" issues of the current implementation. The "Universal vs. Rare" separation is the correct architectural pivot.

However, there is **one significant "footgun" (risk)** regarding **Text Drift** and **Token Efficiency** for *already* universal patterns, and a semantic adjustment needed for Round 1.

Here is the analysis of your plan with specific recommendations:

### 1. The "Text Drift" Footgun (Critical)

**The Issue:** Your plan handles `rare` patterns by index (preserving them perfectly), but implies that `universal` patterns must be regenerated in the `universal_patterns` list every round.

*   **Scenario:** Pattern `U_A` (Universal) enters Round 3. It does *not* merge with anything in the other branch.
*   **Current Plan:** The LLM must re-write `U_A` into the `universal_patterns` JSON output.
*   **Risk:**
    1.  **Text Drift:** In a map-reduce tree of depth ~5, a universal pattern found early will be re-written 4-5 times. This is like a game of "telephone"—the specific wording (crucial for auditors) may degrade or hallucinate details.
    2.  **Token Waste:** You are paying to generate text for patterns that haven't changed.

**Recommendation:**
Update the response schema to allow **preserving Universal patterns by index**, just like Rare ones.

**Revised Schema:**
```json
{
  "new_merged_patterns": [
    {
      "name": "...",
      "description": "...",
      "derived_from": ["U1_0", "R2_1"] // Created from a merge
    }
  ],
  "unchanged_universal": ["U1_1", "U2_0"], // Pass-through Universals (NO text gen)
  "still_rare": ["R1_0"] // Pass-through Rares
}
```
*Note: This requires a slightly more complex reconstruction logic in Python (fetching objects for `unchanged_universal` and `still_rare`), but guarantees zero text drift and maximum speed.*

### 2. Round 1 Semantics

**The Issue:** The plan states: *"All patterns from Round 1 start as 'universal' (they'll be classified in Round 2+)."*
Semantically, this is the opposite of reality. A pattern from a single policy is, by definition, **Rare** (Source Count = 1).

**Recommendation:**
In Round 1, place all extracted patterns into `rare_patterns` and leave `universal_patterns` empty.
*   **Round 2 Logic:**
    *   `Rare` + `Rare` (match) -> `Universal`
    *   `Rare` (no match) -> `Rare`
*   **Round 3 Logic:**
    *   `Univ` + `Univ` (match) -> `Univ`
    *   `Univ` + `Rare` (match) -> `Univ`
    *   `Univ` (no match) -> `Univ` (via `unchanged_universal` index)

This makes the logic consistent: "Universal" strictly means "Evidence found in >1 source".

### 3. Provenance Resolution (Implementation Detail)

**The Issue:** The plan mentions `derived_from` storing indices. You need to ensure the aggregator **eagerly resolves** `source_policy_ids`.

**Recommendation:**
When processing `derived_from` indices in `aggregator.py`:
1.  Look up the input objects (e.g., `InputObj_A`, `InputObj_B`).
2.  Calculate `new_source_ids = set(InputObj_A.source_policy_ids) | set(InputObj_B.source_policy_ids)`.
3.  Store `new_source_ids` in the new pattern object immediately.
Don't rely on recursively traversing `derived_from` at the end of the process, as the indices (`U1_0`) are ephemeral per round.

### 4. Hallucinated Indices

**The Issue:** The LLM might output `still_rare: ["R1_99"]` where `R1_99` does not exist.

**Recommendation:**
In `aggregator.py`, add a strict validation step. If an index is returned that wasn't in the input map:
*   **Log a warning.**
*   **Drop the index** (safest) or treat it as an error.
*   Do *not* crash the whole aggregation process.

### Summary of Changes to Plan

1.  **Modify Schema:** Add `unchanged_universal` (list of strings) to `consolidate_patterns` response schema to prevent text drift.
2.  **Update Round 1:** Initialize patterns as `rare_patterns`, not universal.
3.  **Update Logic:** Ensure `aggregator.py` handles the three distinct output lists: `new_merged` (create new), `unchanged_universal` (lookup & copy), `still_rare` (lookup & copy).

Everything else looks solid. The Two-Phase approach is the right move.