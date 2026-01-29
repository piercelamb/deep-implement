This is a highly robust and well-reasoned technical plan. It directly addresses the root cause of low precision (context overwhelm) without sacrificing the architectural benefits of the current setup (caching).

The hypothesis that **Gemini Flash shifts from "search mode" (finding matches) to "audit mode" (rejecting matches)** when the context is narrowed to a single control is sound. This is a classic "Generator-Verifier" pattern that often yields significant precision gains.

Here are my recommendations to ensure the implementation succeeds, focusing on edge cases and prompt robustness.

### 1. Critical Recommendation: The "Hallucination Loop" Check

**Risk:** Stage 2 sometimes creates "perfect" evidence by slightly hallucinating or stitching together sentences that don't belong together. If you feed this hallucinated quote to Stage 3, and Stage 3 only evaluates the *logic* of the quote against the control, it might VERIFY a mapping based on text that doesn't exist.

**Recommendation:** Your Stage 3 prompt must explicitly force the model to **re-locate** the quote in the cached document.

*   **Modify `prompts/control_verifier/user`:**
    Add a specific check for quote veracity.

    ```markdown
    ### Rejection Criteria
    REJECT if ANY of these apply:
    □ The Evidence Quote does not exist verbatim (or with negligible differences) in the document.
    □ Evidence was assembled... (existing items)
    ```

### 2. Architectural Safety: The "Mass Hallucination" Circuit Breaker

**Risk:** Occasionally, LLMs fail catastrophically and map *everything*. If Stage 2 returns 50+ MAPPED controls (which is statistically unlikely for a single policy), spawning 50 concurrent Stage 3 tasks is wasteful and might hit rate limits.

**Recommendation:** Implement a "sanity cap" in `ThreeStageDecider`.

*   **Logic:**
    ```python
    # In ThreeStageDecider
    mapped_controls = [r for r in stage2_results if r.addresses_control]

    if len(mapped_controls) > 50:
        logger.warning(f"Stage 2 returned {len(mapped_controls)} matches. This suggests a prompt breakdown. Capping Stage 3 verification to top 50.")
        # Optional: Sort by confidence or score if available, otherwise truncate
        mapped_controls = mapped_controls[:50]
    ```

### 3. Prompt Refinement: Leveraging "Chain of Thought" for Verification

**Risk:** In your `response.json`, you ask for `verdict` then `reasoning`. Gemini often performs better if it reasons *before* the verdict.

**Recommendation:** Flip the order in the prompt instructions, even if the JSON structure stays the same (standard CoT), OR enforce the JSON order.

*   **Update `prompts/control_verifier/user`:**
    ```markdown
    ### Instructions
    1. First, locate the evidence in the text.
    2. Second, think step-by-step about whether this satisfies the specific guardrails.
    3. Finally, determine the verdict.
    ```

*   **Update `prompts/control_verifier/response.json`:**
    Move `reasoning` to the top of the properties list (LLMs generate JSON sequentially).

    ```json
    {
      "properties": {
        "control_id": { ... },
        "reasoning": {
          "type": "string",
          "description": "Step-by-step analysis of why the mapping is valid or invalid."
        },
        "verdict": { ... }
        ...
    ```

### 4. Implementation Detail: Asyncio Semaphore

**Observation:** You mentioned "concurrent execution" for the experiment. Even for experiments, you need a Semaphore. Gemini Flash has a requests-per-minute (RPM) limit. If you spawn 30 tasks instantly, `asyncio.gather` or `as_completed` will fire them all at once.

**Recommendation:** Wrap the verify call in a semaphore.

```python
# In ThreeStageDecider.__init__
self.sem = asyncio.Semaphore(15)  # Conservative limit for experiment

# In _verify_control
async def _verify_control(self, ...):
    async with self.sem:
        return await self._call_gemini(...)
```

### 5. Data Capture: "Why did we reject?"

**Opportunity:** The most valuable output of this experiment is understanding *why* Stage 2 failed.

**Recommendation:** In your `VerificationResult` dataclass and output CSVs, ensure you explicitly log the `guardrail_violated` field.
*   If Stage 3 rejects 20 controls, and 15 of them are due to `G-15` (Scope Mismatch), you know exactly how to fix the Stage 2 system prompt (or Stage 1 retrieval) for the next iteration.

### Summary of Recommended Changes to Plan

1.  **Prompt:** Add "Verify quote existence" to Stage 3 user prompt.
2.  **Schema:** Move `reasoning` before `verdict` in the JSON schema.
3.  **Code:** Add `asyncio.Semaphore` to `ThreeStageDecider`.
4.  **Code:** Add a safety cap (max ~50) to prevents runaway Stage 3 calls.

This plan is ready to execute. The distinction between "Discovery" (Stage 2) and "Audit" (Stage 3) is the correct architectural pattern for this problem.