This is a great pivot. You discovered that **Evidence Uniqueness** is a feature, not a bug—the LLM is indeed citing specific text from each document.

However, your finding that `(control_id, IR_rule)` offers a **2.2x reduction** is the key. This is actually the **correct level of abstraction for Prompt Engineering**. You don't need to fix the prompt for "Control X + Policy Y's specific sentence"; you need to fix the prompt for "Control X + Rule Z's interpretation."

Here is my recommendation on how to handle the 1,878 patterns efficiently:

### 1. Refine the "Representative" Selection
Since you are grouping ~2.2 FPs into one "Pattern," you have to choose **one** instance to show the Judge. Don't pick randomly.

**Pick the "Most Confident" Error.**
If the LLM was 95% confident that IR-3 applied to DCF-13, but only 40% confident in another instance, the 95% instance is the "purest" example of the logic failure.

*   **Algorithm:**
    1.  Group FPs by `(control_id, IR_rule)`.
    2.  Sort the FPs in that group by `llm_confidence` (descending).
    3.  Select the top one as the `RepresentativeFalsePositive`.
    4.  (Optional) Store the count of the group (e.g., `frequency=23`) in the representative object so the Judge knows the magnitude of the error.

### 2. The Sampling Strategy (Tweaked)
Your proposed sampling buckets are good, but I suggest a slight modification to ensure you capture the "worst" logic, not just the most frequent.

**Proposed Sampling for Split 4 (~500 items):**

*   **Bucket A: High-Impact Patterns (Frequency ≥ 5)**
    *   *Action:* Keep **ALL** (approx. 130-150 patterns).
    *   *Reasoning:* These are systemic failures where a specific rule is consistently breaking a specific control. These are your highest ROI fixes.

*   **Bucket B: High-Confidence "One-Offs" (Frequency < 5)**
    *   *Action:* Sort the remaining patterns by **Confidence Score**. Take the top **250**.
    *   *Reasoning:* A logic error where the model is "99% sure" is dangerous, even if it only happened once *so far*. We want to squash high-confidence hallucinations.

*   **Bucket C: The "Semantic Equivalence" (IR-3) Audit**
    *   *Action:* Randomly sample **100** patterns where `IR_rule == "IR-3"` (that weren't picked in A or B).
    *   *Reasoning:* Your data shows IR-3 causes 32.8% of errors. We need to over-sample this specific rule to understand *how* it's being abused (e.g., is it synonym matching? fuzzy logic?).

### 3. Execution Plan
You don't need to overhaul your architecture. Just update the collector/deduplicator logic:

1.  **Modify `deduplicate_fps.py`**:
    *   Group by `(control_id, IR_rule)`.
    *   Instead of keeping the *first* FP, keep the one with **max(confidence)**.
    *   Add a field `group_frequency` to the `FalsePositive` object (or a wrapper).

2.  **Run the Judge on the ~500 Sample**:
    *   Pass the `group_frequency` to the Judge context.
    *   *Prompt Addition:* "This specific logic pattern caused **{N}** false positives across the dataset. Analyze the logic carefully."

### 4. Cost vs. Effort Note
If you are using a model like **Gemini 1.5 Flash** or **GPT-4o-mini** as your Judge:
*   **Just run all 1,878 patterns.**
*   The cost difference is negligible (~$1.00 vs $0.25).
*   Sampling is only necessary if you are using expensive models (GPT-4o/Claude 3.5 Sonnet) or if human review is the bottleneck.

**Recommendation:** If automated (LLM-as-Judge), run **all 1,878**. If you plan to manually review the outputs, use the **Bucket A/B/C** strategy to limit it to 500.

### Summary
The `(control_id, IR_rule)` grouping is the correct signal. The fact that evidence text varies doesn't matter for *rule* tuning. Use **Max Confidence** to pick the representative example, and if budget permits, judge all 1,878 patterns to get a complete picture of your rule failures.