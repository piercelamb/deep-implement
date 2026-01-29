This is a comprehensive and well-structured plan. It correctly identifies the core constraint (long documents requiring Context Caching) and leverages the correct architecture (Parallel processing with rate limiting).

 However, there are a few technical "footguns" regarding the Google GenAI SDK versions, model naming, and data consistency that need to be addressed before implementation.

Here is an analysis of the plan with specific additions and corrections.

### 1. SDK Version & Import Confusion (Critical)
The plan mixes up the **Legacy SDK** and the **New SDK**.
*   **The Version:** `google-genai>=1.46.0` refers to the *legacy* package (`google-generativeai`).
*   **The Code:** `client.aio.caches.create` and `types.Part.from_bytes` syntax belongs to the *new* SDK (`google-genai`, typically v1.0+).
*   **The Fix:** You must use the **new SDK** for the code snippets provided to work.
    *   **Dependency:** Change to `google-genai` (current version is approx `0.2` to `1.0` depending on release channel, *not* 1.46).
    *   **Imports:** Ensure you use `from google import genai` and `from google.genai import types`.

### 2. Model Naming Verification
*   **The Issue:** `gemini-2.5-pro-preview-06-05` likely does not exist or is a hallucination of a future version.
*   **Correction:** As of late 2025:
    *   **Gemini 1.5 Pro** (`gemini-1.5-pro-002`): Best for reasoning, supports caching.
    *   **Gemini 2.0 Flash** (`gemini-2.0-flash-exp`): Faster, supports caching, cheaper.
    *   **Gemini 2.0 Pro**: (If available/previewed).
*   **Action:** Update default model to `gemini-1.5-pro-002` or `gemini-2.0-flash-exp`.

### 3. Orphaned Cache "Footgun"
If the script is interrupted (Ctrl+C) or crashes hard (OOM) inside the `try/finally` block, the `delete_cache` might not fire.
*   **Risk:** You will hit the "Cached Content" quota (usually 5-10 active caches per project) very quickly, blocking subsequent runs.
*   **Addition:** Add a standalone cleanup utility or a startup check that lists active caches matching your prefix (e.g., `policy_mapping_`) and deletes them before starting the new run.

### 4. Ground Truth Logic Gap
*   **The Logic:** The plan says: "If the control does NOT appear to map... explain why" AND "Write results (only mapped controls)".
*   **The Problem:** This script is based on *Ground Truth*. We *know* the control is mapped. If the LLM says "Not Mapped", that is a **False Negative** failure mode.
*   **Refinement:** Do not silently drop these.
    *   Create a separate log file or section in the markdown: `## Missed Controls (LLM failed to verify)`.
    *   Log the `unmapped_reason` provided by the LLM. This is crucial for debugging the prompt or the policy content.

### 5. String Normalization (Data Hygiene)
*   **Risk:** The Ground Truth JSON might have `DCF-04` while the CSV has `DCF-4`, or the PDF filename in JSON is `Policy.pdf` but the file on disk is `policy.pdf`.
*   **Addition:**
    *   Normalize Control IDs (strip whitespace, uppercase).
    *   Normalize Filenames (check case-insensitivity if on Linux).

---

### Revised Plan Additions

Please incorporate the following changes into your implementation:

#### A. Updated `cache_manager.py` (New SDK Syntax)
Ensure the `upload_pdf` method explicitly waits for the cache to be active.

```python
# In GeminiCacheManager
async def upload_pdf(self, pdf_bytes: bytes, display_name: str) -> str:
    # ... create code ...
    # CRITICAL: Context caching requires the cache to be in STATE_ACTIVE before use
    # The new SDK usually handles this, but verify loop might be needed depending on file size.
    return cached_content.name
```

#### B. Robust Cleanup (`__main__` or `run.py`)
Add a cleanup handler for safe exits.

```python
import signal
# ... inside run logic ...
# Register signal handler to ensure cache deletion on Ctrl+C
loop = asyncio.get_running_loop()
for sig in (signal.SIGINT, signal.SIGTERM):
    loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown_handler()))
```

#### C. Progress Bars
With 3 policies * 5 controls, you might have hundreds of operations.
**Action:** Use `tqdm` to wrap the `asyncio.as_completed` or update a progress bar within the gathered tasks.

#### D. Adjusted `prompts/control_reasons/response.json`
Add a confidence score to help filter weak mappings.

```json
{
  "properties": {
    "confidence_score": {
      "type": "integer",
      "description": "1-10 score of how strongly the document supports this control",
      "minimum": 1,
      "maximum": 10
    },
    // ... existing fields
  }
}
```

#### E. Handling "Missed" Ground Truths in `reason_generator.py`

Modify the write logic:

```python
# Inside process_policy
for result in results:
    if isinstance(result, ControlReasons):
        if result.is_mapped:
            output_writer.append_control_reasons(...)
        else:
            # NEW: Record that the LLM disagreed with Ground Truth
            output_writer.append_missed_control(
                control_id=result.control_id,
                reason=getattr(result, 'unmapped_reason', 'No reason provided')
            )
```

### Summary of Tasks to Update
1.  **Dependency**: Switch to `google-genai` (New SDK).
2.  **Config**: Fix Model Name to `gemini-1.5-pro-002`.
3.  **Safety**: Implement "Clean on Exit" logic.
4.  **Logic**: handle False Negatives (log them, don't ignore them).
5.  **UX**: Add `tqdm` progress bars.