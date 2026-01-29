Below is an audit of the plan as written, with the highest‑risk mistakes/footguns called out first, and then a deeper dive on Intelligent Neighbor Page Inclusion (where I think you can get a lot more accuracy and fewer “context explosions”).  ￼

Top issues to fix before you build (real “gotchas”)

1) Neighbor inclusion is described, but your core decide_document() snippet doesn’t actually do it

In the “Core logic” snippet you only fetch the primary page image and call decide_page(page_num, page_image, controls)—no neighbor selection, no extra images, no context_page_nums. That’s a classic implementation footgun because you’ll think you shipped neighbor inclusion but it never runs.

Recommendation
	•	Make “build PageLLMInput (primary + chosen neighbors)” a single explicit step in the document flow, and unit test it independently:
	•	given page_predictions + page_num, assert it returns the expected ordered page numbers and image list.

2) “Parallelizable” but the example loop is sequential

You say the per-page calls can run concurrently, but the code example appends decisions in a normal for‑loop. If you ship the sequential version, you’ll get much higher latency and timeouts for big PDFs.

Recommendation
	•	Implement concurrency from day one (async client .aio or a bounded thread pool), with a global semaphore so you don’t trip Vertex rate limits.

3) The Gemini model name in the plan is likely wrong

You’ve got gemini-3.0-pro. Current Vertex/Gemini docs show Gemini 3 Pro Preview names like gemini-3-pro-preview (and often versioned variants), not gemini-3.0-pro.
Also, some Gemini endpoints are location-sensitive (e.g., global vs region). Google’s docs explicitly show initializing the GenAI SDK with location='global' for global endpoints.

Recommendation
	•	Treat model string + location as config validated at startup:
	•	do a tiny “health” generate request on boot and fail fast with a helpful error.

4) Structured output wiring is underspecified (easy to silently fail)

You load a response.json schema, but the plan doesn’t show actually setting response_mime_type='application/json' and passing the schema into the SDK request config. Those are required patterns in the official structured output docs/samples.

Recommendation
	•	Add a small “structured output contract test” that:
	•	passes a trivial schema,
	•	asserts the model response parses as JSON,
	•	asserts required keys exist.

5) “Per-page LLM calls” requirement conflicts with “skip LLM call” edge-case

You list as a requirement: each qualifying page gets an LLM call.
Then you list an edge case: “Single page qualifies with single control → Return directly (skip LLM call).”

That’s not just wording: if you implement the skip, you’ll lose the whole point of the LLM as a verifier against retrieval false positives.

Recommendation
	•	If you want an optimization, gate it with a strong condition like:
	•	only one candidate and it beats the next-best by a large margin and score is far above threshold,
	•	otherwise still call LLM.

6) Hard failure when no pages pass threshold will bite you in production

Raising ValueError("No pages have controls above threshold") is fine for an experiment, but it’s a production footgun:
	•	scanned PDFs / low-text PDFs,
	•	OCR failures,
	•	a threshold tuned too high for a given document type.

Recommendation
Return a structured “no decision” result with diagnostics (max score observed, pages sampled, etc.) and/or run a fallback strategy (details below).

⸻

Other important edge cases & failure modes

Retrieval/thresholding edge cases
	•	Score scale instability: your thresholds assume the score distribution is comparable across docs. If score distributions vary by policy type, you’ll get “no qualifying pages” or “too many qualifying pages” swings.
	•	Consider per-document normalization (percentiles, z-scores) or adaptive thresholds (e.g., top X pages).
	•	Repeated headers/footers: if your page text includes boilerplate repeated on every page (“Company Confidential”, policy name, etc.), retrieval can get artificially high scores and neighbor inclusion will amplify the error.
	•	Pre-strip headers/footers or downweight repeated n-grams across pages.

Multimodal input edge cases
	•	Tiny font tables: sending page images can fail if the model can’t read small text reliably. Consider:
	•	higher DPI rendering,
	•	and/or include extracted PDF text alongside the image when available.
	•	Rotation/cropping: some PDFs have rotated landscape pages; ensure rendering preserves orientation and full page.

Candidate control set edge cases
	•	If you only pass “controls above threshold”, you can create a nasty failure mode:
	•	the correct control is just below threshold on the primary page but above neighbor threshold on the neighbor page,
	•	you include the neighbor page as context,
	•	the model “sees” it’s the correct control,
	•	but can’t select it because it’s not in candidates.

That’s a very common source of “LLM clearly knows the answer but is forced to pick something else.”

⸻

Deep dive: Intelligent Neighbor Page Inclusion (main feedback)

Your current logic:
	•	Consider only adjacent pages.
	•	Include neighbor if it contains a control above neighbor_threshold and that control is “related” to any qualifying control on the primary page, where relatedness tiers are:
	1.	same control ID
	2.	same domain
	3.	same classification

This is a strong starting point, but it has two big risks:
	1.	false context expansion (including irrelevant neighbors, hurting accuracy),
	2.	false context omission (missing critical continuation pages, hurting accuracy).

Below are concrete improvements that address both.

⸻

A) Make inclusion stricter at coarse relatedness levels

Problem: “Same classification” is usually too broad

If “Protect” contains many domains, then classification-level matching becomes close to “always include the neighbor as long as it has any half-decent score.” In a document that’s consistently about “Protect”-type controls, you’ll include neighbors constantly—especially if header/footer artifacts drive scores.

Better approach: level-specific thresholds (not one neighbor_threshold)

Use different inclusion criteria by tier:
	•	Tier 1 (same control ID): permissive, because it’s very strong evidence.
	•	Tier 2 (same domain): moderate.
	•	Tier 3 (same classification): strict and require extra evidence (page similarity or continuity signal).

Example policy:

Tier 1: include if score >= 0.3 * score_threshold
Tier 2: include if score >= 0.6 * score_threshold
Tier 3: include if score >= 0.9 * score_threshold AND page_similarity >= sim_thresh

This single change typically reduces “neighbor spam” dramatically while keeping the “true continuation” pages.

⸻

B) Don’t let “ANY matching control” trigger inclusion

Problem: one random matching control can include the neighbor

Your loop says: if any neighbor top_control above threshold shares classification/domain with any primary qualifying control → include.

This is vulnerable when:
	•	the primary page has multiple qualifying controls across domains/classifications,
	•	or the neighbor has a noisy high-scoring control in a broad classification.

Better approach: use the “best related match” only

Compute a single best relatedness match between the primary page’s control-set and the neighbor’s control-set, then decide based on that best match (with tier weighting).

Pseudo:

BEST_TIER_WEIGHT = {0: 1.0, 1: 0.7, 2: 0.4}  # id, domain, class
# pick the neighbor control that maximizes score * weight(tier)

And include neighbor only if that best weighted score exceeds a threshold.

This gives you:
	•	a reason code (“included because domain match: Change Management @ 65”),
	•	predictable behavior when there are lots of controls.

⸻

C) Add a “continuity” signal that is independent of retrieval

Problem: retrieval can miss continuation pages

Continuation pages often:
	•	have fewer keywords (tables, diagrams),
	•	or start mid-sentence with pronouns/implicit references.

So retrieval relatedness can be low even when the page is essential context.

Add one (or more) lightweight continuity checks

Pick at least one signal that doesn’t depend on control scoring:
	1.	Page-to-page semantic similarity
You already have embeddings in the system (ColModernVBERT). Use them:
	•	compute similarity(primary_page_embedding, neighbor_page_embedding),
	•	include neighbor if similarity is high even if control hierarchy match is weak.
	2.	Layout / text heuristics from extracted PDF text (cheap and very effective)
Examples:
	•	primary page ends without punctuation / ends with “(continued)”,
	•	neighbor begins with a lowercase letter / bullet continuation,
	•	repeated section header detected on both pages.

You don’t need OCR for text PDFs; just use the text layer if present.

Key recommendation:
Use (hierarchy match) OR (continuity evidence), not hierarchy match only.

⸻

D) Define an explicit window-expansion strategy (and keep it contiguous)

Right now you define a hard cap max_total_pages, but not how you expand beyond ±1.

If you want this to work well on:
	•	long tables spanning 3 pages,
	•	sections spanning 4–5 pages,

you need deterministic expansion.

Strong default: contiguous “grow outward” window
	1.	Start with [primary]
	2.	Evaluate primary-1 and primary+1
	3.	Add whichever passes inclusion (or both)
	4.	If you added primary+1, then evaluate primary+2 (and similarly on the left)
	5.	Stop at max_total_pages

This gives the LLM a clean contiguous chunk of the document (much easier than disjoint context pages).

Alternative (sometimes better): pick the “best neighbors” by relevance score

If you want to allow non-symmetric windows, rank candidates by a relevance score and pick top pages, but in policy PDFs I’d prefer contiguous windows.

⸻

E) Expand the candidate control list when you include neighbors

This is one of the biggest accuracy wins with minimal cost.

Problem (re-stated)

Neighbor inclusion adds context pages that might contain the strongest evidence for the correct control, but your candidate list might exclude that control if it didn’t clear threshold on the primary page.

Recommendation: candidate set = primary candidates + neighbor candidates (bounded)

If you include neighbor pages, add:
	•	any neighbor controls above neighbor_threshold that match tier 1 or 2 (same ID/domain),
	•	and optionally the neighbor page’s top 1 control.

Then cap total candidates (e.g., max 15–25).

Also: label them in the prompt (“Primary-page candidates” vs “Neighbor-suggested candidates”) so the model knows what came from where.

⸻

F) Log why a neighbor was included (this matters for debugging)

Add structured diagnostics:
	•	included_pages: [4,5,6]
	•	inclusion_reason per page:
	•	tier: “domain”
	•	matching_domain: “Change Management”
	•	matched_control_id: “DCF-5”
	•	neighbor_score: 65
	•	neighbor_threshold_used: 50
	•	page_similarity: 0.83 (if used)

Without this, neighbor inclusion becomes a “why is this page even here?” black box.

⸻

Prompt / response schema suggestions that prevent subtle failures

1) Tell the model exactly how the images map to pages

Because you’re passing multiple page images, include a caption before each image in the multimodal content:
	•	“Image 1: PRIMARY page 5”
	•	“Image 2: CONTEXT page 4”
	•	“Image 3: CONTEXT page 6”

And in the text prompt, reiterate: “Use context pages only to understand page 5.”

This reduces misattribution (“model chose the control that matches the context page”).

2) Add a “no good match” escape hatch (optional but valuable)

Right now the schema forces a control selection even if the page is a title page / revision history / boilerplate.

Consider allowing:
	•	selected_control_id: "NONE" (and include it in the enum)
	•	or add a boolean no_match: true/false

This will lower false positives and make aggregation more trustworthy.

3) Validate that all placeholders are filled

Your insert_context() only replaces values that are str, which means {PAGE_NUM} will not be replaced unless you pre-stringify it. That’s an easy-to-miss bug that silently degrades prompt quality.

Add:
	•	an assertion that the final user prompt contains no {…} placeholders,
	•	otherwise error early.

⸻

Aggregation: a couple of improvements (cheap wins)

1) “Highest confidence wins” can be brittle

If one page yields “high” on a spurious match, it can override multiple “medium” votes that agree on the true control.

Better default: weighted voting

Assign weights:
	•	high = 3
	•	medium = 2
	•	low = 1

Sum by control_id; tie-breaker by max retrieval score.
This makes the system robust to single-page flukes.

2) Track “coverage”

A nice diagnostic signal is:
	•	how many pages selected the winning control,
	•	and whether they are contiguous (stronger evidence).

⸻

One suggested “fallback path” that saves you when thresholds/OCR fail

If no pages clear threshold:
	1.	pick top K pages by max score (e.g., K=3–5),
	2.	run LLM on those pages anyway with their top N candidates,
	3.	aggregate.

This prevents total failure on documents where score scale differs or text extraction is weak.

⸻

Quick checklist of changes I would make to the plan text/code
	•	Integrate neighbor selection into decide_document() (currently missing in core snippet).
	•	Implement real concurrency + rate limiting (semaphore).
	•	Fix model name default and validate model/location at startup.
	•	Wire structured output config explicitly (response_mime_type + schema).
	•	Replace single neighbor_threshold_ratio with tier-specific thresholds (ID vs domain vs classification).
	•	Add continuity signal (page embedding similarity and/or PDF-text heuristics).
	•	Expand candidate set with neighbor-derived candidates (bounded).
	•	Add rich logging of neighbor inclusion reasons + aggregated vote math.

If you want, I can propose a concrete get_context_window(primary_page_num, ...) -> (page_nums, candidate_controls) function signature and a reference implementation sketch that encodes the tier weights + continuity checks cleanly (so it’s testable and tunable).