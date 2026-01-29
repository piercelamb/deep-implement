Below are the extra “footguns” / missing pieces I’d fix beyond Gemini’s notes, plus a couple factual corrections based on current Google docs.

0) Quick factual corrections (SDK + model names)
	•	google-genai versioning: Gemini’s analysis claims google-genai>=1.46.0 is “legacy,” but google-genai is the new SDK and is currently in the 1.x line (e.g., PyPI shows recent 1.x releases).  ￼
The “new SDK” import style you’re using (from google import genai, from google.genai import types) matches the official repo docs.  ￼
	•	Model naming: Your plan hard-codes gemini-2.5-pro-preview-06-05 in config + cache creation.  ￼ The official “model code” for Gemini 2.5 Pro is gemini-2.5-pro (and caching is supported).  ￼
Recommendation: default to gemini-2.5-pro and allow override via config/CLI.

1) Concurrency + rate-limit footguns (the biggest operational risk)

You correctly note total concurrency is n * c (e.g., 15).  ￼ But you’re missing protections that prevent “thundering herd” retries and quota lockups:
	•	Global concurrency cap: You have a per-policy semaphore for controls, but the plan doesn’t show a policy-level semaphore / worker pool implementation. Add a top-level semaphore so max_parallel_policies is actually enforced (and doesn’t just “fan out” tasks). (This is implied in the plan but not implemented in the snippet.)  ￼
	•	429/503-aware retry: Your retry is exponential backoff with no jitter and catches all exceptions.  ￼
Fixes:
	•	Add jitter to avoid synchronized retries
	•	Treat 429 / RESOURCE_EXHAUSTED / 503 differently (longer backoff; respect Retry-After if exposed)
	•	Add a request timeout so one hung call doesn’t stall a whole policy
	•	Adaptive throttling: If you observe repeated 429s, automatically reduce concurrency (c then n) mid-run.

2) “Evidence + page citations” are easy to hallucinate unless you verify

Your objective explicitly requires “page number citations.”  ￼ This is where LLMs are most likely to look confident and be wrong.

Recommended hardening:
	•	Require per-reason page numbers (not one merged list). Right now the writer collapses pages across all reasons, losing traceability.  ￼
Instead, write:
	•	Reason bullet
	•	Evidence snippet
	•	Pages for that reason
	•	Normalize page indexing: Decide (and document) whether the model should return 1-indexed PDF pages. Then enforce it in code and tests.
	•	Automated evidence verification (high value):
	•	Extract text per page (cheap local PDF text extraction).
	•	For each returned evidence, confirm it appears (exact or fuzzy match) on one of the cited pages.
	•	If it doesn’t match, mark the reason as “unverified” and optionally re-ask the model with a stricter prompt.

This prevents quietly producing a markdown file that “looks audited” but isn’t.

3) Ground truth disagreement shouldn’t be “skip and move on”

Your plan says: skip unmapped controls.  ￼ Gemini correctly calls out the logic gap for ground truth and recommends capturing false negatives.  ￼

I’d go further and split outcomes into 4 buckets per policy:
	1.	Mapped (verified) – evidence verified by post-check
	2.	Mapped (unverified) – model says mapped but evidence doesn’t match cited pages
	3.	LLM false negative – model says not mapped (store unmapped_reason)
	4.	Error – timeouts, parse failures, quota, etc. (store raw error + retry count)

That makes debugging prompt/model regressions dramatically easier.

4) Cache lifecycle: handle cancellation + “orphan caches” more aggressively

You already have try/finally deletion.  ￼ Gemini notes Ctrl+C / hard crash can still orphan caches.  ￼

Add:
	•	Startup cleanup mode: --cleanup-caches that lists cachedContents with your prefix and deletes them before running.
	•	Cancellation-safe deletion: when tasks are cancelled, finally can be interrupted; shield cache deletion (asyncio.shield) and ensure your signal handler awaits cleanup before exit.
	•	Run-scoped display_name: include a run-id + policy name to safely target cleanup (e.g., cmr/{run_id}/{policy_slug}).

Also note: TTL default is 1 hour if not set, and caching docs emphasize TTL semantics.  ￼

5) Output idempotency + ordering (diffs and reruns)

Today the writer just appends.  ￼ That creates two problems:
	•	Reruns can duplicate sections.
	•	Parallel results come back non-deterministically; output ordering becomes unstable.

Fixes:
	•	Write to a temp file then atomic rename (avoids half-written markdown on crash).
	•	Enforce stable ordering: sort controls by ID before emitting; within a control, preserve reason order from the model.
	•	Add --overwrite/--resume:
	•	overwrite: regenerate file from scratch
	•	resume: skip controls already present (parse existing markdown headings)

6) Structured output schema improvements (avoid parse traps)

Your schema requires "reasons" even if "is_mapped": false.  ￼ Models often omit fields in negative cases; you’ll see parse failures.

Suggested schema tweaks:
	•	Make reasons optional or allow empty array when unmapped
	•	Make unmapped_reason required when is_mapped=false (conditional requirement)
	•	Add confidence_score (Gemini suggested) but treat it as advisory only.  ￼
	•	Add evidence_type: "quote" vs "paraphrase" so you can enforce quoting when you want strictness

Also: store the raw model text alongside parsed JSON whenever parsing fails (debugging gold).

7) CLI + UX missing pieces that prevent painful runs

Your plan has good CLI basics.  ￼ I’d add:
	•	--max-total-concurrency (hard cap independent of n and c)
	•	--dry-run (counts policies/controls, estimates calls)
	•	--output-json (machine readable artifacts for eval/analysis; markdown is for humans)
	•	A summary line at end: total controls processed, mapped/unmapped/errors, total retries, caches cleaned.

8) PDF edge cases you’ll hit in the wild

Not covered in the plan:
	•	Scanned PDFs / image-only pages: evidence verification via text extraction may fail; in that case fall back to (a) model-only evidence, but mark as unverified, or (b) OCR selectively.
	•	Encrypted/invalid PDFs: detect early and fail the policy with a clear error bucket.
	•	Huge PDFs: loading full bytes into memory (pdf_path.read_bytes())  ￼ is fine until it isn’t; add a size guardrail and clear error.

⸻

If you only implement 5 changes
	1.	Switch default model string to gemini-2.5-pro (and config override).  ￼
	2.	Add global concurrency cap + 429-aware backoff w/ jitter.  ￼
	3.	Emit per-reason citations (don’t collapse page numbers) + add evidence verification.  ￼
	4.	Track false negatives + errors instead of skipping unmapped ground-truth controls.  ￼
	5.	Add startup cache cleanup + cancellation-safe deletion.  ￼

If you want, I can propose concrete revised dataclasses / schema + a markdown layout that supports the 4 outcome buckets without making the output noisy.