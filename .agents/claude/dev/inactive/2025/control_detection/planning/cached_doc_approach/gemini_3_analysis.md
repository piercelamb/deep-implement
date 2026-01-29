This is a strong pivot. Moving from **Page-Centric (Local Context)** to **Control-Centric (Global Context)** directly addresses the primary weakness identified in your report: the "split context" problem where a control's topic is on one page but the binding mandate is on another, or where specific details are scattered.

However, after reviewing `implementation_plan.md`, I have identified several "footguns" (risks), architectural inefficiencies, and prompt vulnerabilities.

Here is an analysis of the plan with specific recommendations.

### 1. The "Diverse Batching" Hypothesis (Major Architectural Risk)

**The Plan:** You proposed **Diverse Control Batching** (selecting 5-10 *dissimilar* controls per batch).
**The Logic:** Likely to prevent the LLM from conflating similar controls (e.g., "Password Length" vs. "Password Complexity").
**The Risk:** This maximizes cognitive load and context switching for the LLM.
If you give an LLM a 50-page document and ask for:
1. Fire Extinguishers (Page 45)
2. SQL Injection (Page 12)
3. HR Background Checks (Page 3)
...the LLM must "scan" the entire document vector space for 10 completely distinct concepts simultaneously.

**Counter-Proposal: Coherent (Semantic) Batching**
It is often better to batch **similar** controls (e.g., all 10 "Access Control" candidates).
*   **Why:** The LLM focuses attention on one section of the text (e.g., the Access Control Policy chapter).
*   **Differentiation:** Modern LLMs (Gemini 1.5 Pro/Flash) are excellent at *differentiation* when similar concepts are presented side-by-side. It allows the model to say: *"Paragraph 3 matches Control A (Requires MFA), but does NOT match Control B (MFA for remote access only) because it lacks the specific scoping qualifier."*

**Recommendation:**
In `control_centric_decider.py`, add a toggle for batching strategy. Start with **Coherent Batching** (clustering controls and sending the whole cluster in one batch) rather than Diverse Batching. It is more aligned with how humans review policies.

### 2. The "Page Number" Hallucination Trap

**The Plan:** The prompt requires the LLM to returning `page_numbers`.
**The Reality:** When you upload a PDF to Gemini 1.5 (Multimodal), it "sees" the pages, but it does not inherently know that "the 3rd image in the PDF stream" is "Page 3" in the footer, nor "Page 1" of the intro.
**The Risk:** The LLM will hallucinate page numbers (e.g., guessing based on array index) or simply fail to provide them, causing JSON parsing errors or misleading evidence.

**Recommendation:**
1.  **Accept "Textual" Page Numbers:** If the PDF text contains `Page 1 of 50` in the footer, the LLM *might* catch it.
2.  **Relax the Requirement:** Change the schema to ask for `quote_location_description` (e.g., "Section 4.1 under Access Control") rather than a strict integer page number.
3.  **Fallback:** If you strictly need page numbers, you must insert visual or textual markers into the PDF before uploading (e.g., stamping `[PAGE_ID: 1]` on the image), which complicates the pipeline. *For this experiment, rely on exact quotes as the primary evidence, not page numbers.*

### 3. Prompt Engineering: "Binding Language" Rigidity

**The Plan:** The prompt strictly requires "must/shall/required".
**The Risk:** Many valid policies use "active voice" or "present indicative" to indicate mandates without those specific keywords.
*   *Example:* "The CISO reviews access logs daily." (This is a binding statement of fact/policy, but lacks "must").
*   *Example:* "Policy: All users enforce strong passwords."

**Recommendation:**
Update the `prompts/control_centric/system` prompt to broaden the definition of binding language:

```text
...
2. If found, quote the exact text.
   Matches include:
   - Explicit mandates: "must", "shall", "required", "will", "is prohibited"
   - Declarative policy statements: "Passwords are 12 characters", "The CISO reviews logs"
   - Responsibility assignments: "The Engineering Team is responsible for..."
   
   Exclusions (Non-binding):
   - "Should", "Recommended", "Best Practice"
   - Future tense plans: "We aim to...", "We plan to..."
...
```

### 4. Technical Implementation: Cache Lifecycle & Concurrency

**The Plan:** `_process_batch` runs in parallel with a semaphore.
**The Footgun:** Gemini Cache objects have a "creation time" overhead. If you create a Cache, immediately blast 10 concurrent requests, and then delete it, you might hit:
1.  **Propagation Delays:** The cache might not be ready instantly (though usually fast).
2.  **Rate Limits (TPM):** 10 concurrent calls * (Full Doc Tokens + Output Tokens) will explode the TPM (Tokens Per Minute) limit of the standard tier immediately. 37 documents * 50 pages * 500 words = massive context.

**Recommendation:**
1.  **TPM Throttling:** The `asyncio.Semaphore(10)` limits *connections*, not *tokens*. You need a token bucket rate limiter or a retry decorator specifically for `429 Resource Exhausted`.
2.  **Shared Cache:** Ensure the `GeminiCacheManager` uploads the document **once**, waits for the state to be `ACTIVE`, and then all batches use that single `cache.name`. Do not create a cache per batch. (Your plan implies this correctly, but verify implementation).

### 5. Missing Metric: "Controls Skipped"

**The Plan:** Use `ColModernVBERT` threshold (0.48) to filter candidates.
**The Gap:** In the report, you noted top-K filtering lost 23% of ground truth.
**Recommendation:**
In `control_centric_decider.py`, explicitly log:
*   `n_total_controls`
*   `n_candidates_above_threshold` (The "Model Ceiling")
*   `n_batches_created`

This allows you to separate "Embedding Retrieval Error" from "LLM Decision Error" in the final analysis.

### 6. Additions to `implementation_plan.md`

Add this specific logic to the **Files to Create / `control_centric_decider.py`** section:

#### **Retry Logic Wrapper**
You need a specific wrapper for the batch execution to handle Gemini's 429s aggressively, as this mode is token-heavy.

```python
# Add to control_centric_decider.py imports
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Wrapper for _process_batch
@retry(
    retry=retry_if_exception_type(ResourceExhausted), 
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5)
)
async def _process_batch_safe(self, batch, cache_name):
    return await self._process_batch(batch, cache_name)
```

#### **Modified Prompt Schema**
In `prompts/control_centric/response.json`, make `page_numbers` optional or allow strings to prevent validation failures.

```json
{
  "batch_results": [
    {
      "control_id": "string",
      "addresses_control": "boolean",
      "confidence": "high|medium|low|none",
      "evidence_quote": "string (exact quote)",
      "location_reference": "string (Page number OR section header)", 
      "reasoning": "string"
    }
  ]
}
```

### Summary of Actionable Changes

1.  **Change Batching:** Switch from **Diverse** to **Coherent/Semantic** batching (group by Cluster ID) to aid LLM comparison.
2.  **Broaden "Binding":** Allow declarative statements in the system prompt, not just "must/shall".
3.  **Soften Page Numbers:** Rename `page_numbers` to `location_reference` in JSON schema to allow textual descriptions.
4.  **Harden Retries:** Add `tenacity` retry logic specifically for Token Limits (429s).

If you agree, I can proceed with generating the code files incorporating these adjustments.