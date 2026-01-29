This is a comprehensive and well-structured plan. It correctly identifies the core problem (distinguishing between model error and data error) and proposes a logical architecture (Judge LLM) to solve it.

However, there are a few **critical "footguns"** (potential pitfalls) and **missing scope items** that could undermine the results if not addressed before implementation.

### 1. The "Partial" Trap (Logic Flaw)
**The Problem:** Your logic handles `NO_MATCH` clearly, but `PARTIAL` is ambiguous.
*   **Scenario:** GT says `MAPPED`. Original LLM says `PARTIAL`.
*   **Judge's Dilemma:** If the Judge agrees the policy *partially* addresses the control, what is the verdict?
    *   If `LLM_WRONG`: You imply the policy *fully* addresses it (ignoring the gaps).
    *   If `GT_WRONG`: You imply the control shouldn't be mapped at all (removing it from GT).
*   **The Risk:** In GRC, a "Partial" match is usually sufficient to keep a control mapped (it acts as a placeholder for remediation). If the Judge marks these as `GT_WRONG`, you might accidentally purge valid (but imperfect) policy mappings.
*   **Fix:** Explicitly define the threshold for `GT_WRONG`. It should likely mean "The policy is **irrelevant** to this control." If it is relevant but incomplete, the GT is usually "Correct enough."
    *   *Add to Prompt:* "If the policy addresses the core intent of the control, even with minor gaps, rule `LLM_WRONG` (meaning: keep the GT label)."

### 2. The Missing "Found" Controls (Scope Gap)
**The Problem:** You are validating **False Negatives** (GT has it, LLM missed it), but you are ignoring **Potential False Positives** in the GT (LLM found a mapping, but GT doesn't have it).
*   **Why it matters:** If the goal is a "Perfect Ground Truth," you are currently only cleaning up half the errors. If the LLM confidently finds a match that isn't in `eval.csv`, that is likely a missing label in your dataset.
*   **Recommendation:** Add a parallel collection phase for **High-Confidence Extras**:
    *   `Original Decision == MAPPED` AND `Control NOT in GT`.
    *   Judge these cases: "Is this a valid mapping that the human annotator missed?"

### 3. PDF Cache Lifecycle (Implementation Detail)
**The Problem:** The `run_experiment.py` (Phase 1) creates a Gemini Cache and likely lets it expire or deletes it at the end of the script. The Validator (Phase 3) cannot access that cache object unless the cache name resource ID is saved.
*   **Impact:** You will be re-uploading PDFs for every validation run.
*   **Fix:**
    1.  Accept that re-uploading is the robust path (PDFs are small, cost is negligible compared to complexity of sharing state).
    2.  Ensure `JudgeDecider` manages its own cache lifecycle (create -> use -> delete) to avoid cluttering the GCP project with orphaned caches.

### 4. Concurrency & Rate Limits (Performance)
**The Problem:** The plan implies sequential processing (`judge_control` then `judge_document`). A single document might have 20 disputes. Running 20 serial LLM calls will take 60-100 seconds per document.
*   **Fix:** Use `asyncio.gather` in `judge_document`.
*   **Constraint:** Vertex AI has a "Requests Per Minute" (RPM) quota. If you blast 50 judge requests instantly, you will 429 error.
*   **Code Addition:** Ensure your `JudgeDecider` uses a `asyncio.Semaphore(5)` (or similar) to limit parallel judge calls.

---

### Additions to the Plan

#### A. Updated `JudgeResult` Model
Add a field to capture the *nuance* of the decision, specifically for the "Partial" cases.

```python
class Verdict(StrEnum):
    LLM_WRONG = "LLM_WRONG"  # GT is effectively correct (keep label)
    GT_WRONG = "GT_WRONG"    # Policy is irrelevant (remove label)
    UNCERTAIN = "UNCERTAIN"  # Needs human

# Add this to JudgeResult
class MatchQuality(StrEnum):
    FULL_MATCH = "FULL_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    IRRELEVANT = "IRRELEVANT"
```

#### B. Updated User Prompt (Addressing the "Strictness" Issue)
The prompt needs to explicitly guide the Judge on *how strict* to be.

```markdown
...
<instructions>
Determine if the Ground Truth (GT) label is valid.

Definitions:
- **Valid GT**: The policy addresses the core intent of the control. Gaps may exist, but the policy is clearly the correct place for this control.
- **Invalid GT**: The policy mentions the topic only in passing, or not at all. The control does not belong here.

Your Verdicts:
1. **LLM_WRONG**: The GT is VALID. The original LLM was either too strict or missed the text.
2. **GT_WRONG**: The GT is INVALID. The policy does not support this control.
3. **UNCERTAIN**: ambiguous.

</instructions>
```

#### C. Added CSV Output for "Missing Labels" (Optional but Recommended)
If you decide to handle the "LLM found it, GT didn't" case:
*   File: `grc_review_missing_gt.csv`
*   Columns: `Policy, Control, LLM_Confidence, Evidence_Quote, Suggested_Action (Add to GT)`

### Refined Implementation Order

1.  **Project Structure**: Setup folders/init.
2.  **Models**: Define `JudgeResult` and strict `Verdict` enums.
3.  **Judge Prompt**: Write prompt *and test it manually in Vertex AI Studio* against 3 hard examples (1 partial, 1 miss, 1 hallucination). **Don't skip manual testing.**
4.  **GT Collector**: Implement the logic to extract disagreements.
5.  **Decider w/ Concurrency**: Implement `JudgeDecider` with `asyncio.Semaphore`.
6.  **CLI**: Stitch it together.
7.  **Dry Run**: Run with `--max-rows 1` and `--limit-judges 5` (new flag) to prevent accidental bill shock during debug.

### Summary
The plan is solid 8/10. With the **Partial Trap** fix and **Concurrency** implementation, it becomes 10/10. The prompt engineering in Step 3 is where the success of this project lives or dies.