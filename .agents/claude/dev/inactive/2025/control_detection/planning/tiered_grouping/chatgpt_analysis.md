Here are the biggest footguns I see, plus concrete additions I’d make to the plan. (Ref:  ￼)

Footguns / ambiguity that can bite you
	1.	“page_scores” doesn’t exist in the described data model
	•	Step 1 says argmax(control.page_scores)  ￼, but later you say ScoredControl only has a single page_num + score, and you reconstruct “max page” by iterating page predictions  ￼.
	•	Add: a crisp definition of the input list to create_page_aware_batches():
	•	Is candidates already deduped to one row per control_id (max score + argmax page)?
	•	Or is it a bag of (control_id, page_num, score) entries across pages (which must be reduced first)?
	2.	Duplicate controls across pages will silently wreck batching + capacity math
	•	If a control appears in top_controls for multiple pages (very likely), you can end up batching the same control multiple times unless you dedupe by control_id before Step 0. Your own reconstruction snippet implies duplicates exist and must be reduced  ￼.
	•	Add: “Step -1: reduce to unique controls (take max score; tie-break deterministically).”
	3.	Step 0 truncation is underspecified and can drop the “right” controls
	•	Step 0 “keep top N by score”  ￼ assumes “score” is comparable across controls and that dropping the lowest is least harmful.
	•	Two issues:
	•	If you don’t dedupe first, you might drop entire controls while keeping duplicates of others.
	•	Even with dedupe, purely score-based truncation can over-select a single doc section (e.g., TOC or a glossary page that matches many controls).
	•	Add: a safer truncation policy (see “Over-capacity policy” below).
	4.	Step 3 can fail to reach MAX_CALLS, but MAX_CALLS is described as a hard constraint
	•	The algorithm explicitly allows “stop merging (may exceed MAX_CALLS as last resort)”  ￼, which conflicts with “MAX_CALLS = 50 … (cost control)”  ￼.
	•	Add: a hard decision tree for what you do if you cannot merge to ≤ MAX_CALLS under MAX_BATCH_SIZE (truncate more? raise threshold? skip LLM for some?).
	5.	Greedy pairwise merging can paint you into a corner
	•	“Merge smallest combined size first”  ￼ is reasonable, but greedy “best pair each time” can get stuck with lots of batches of size 9–10 where nothing fits, while still having too many batches.
	•	Add: either (a) an explicit bin-packing style approach, or (b) a second-phase fallback that guarantees meeting MAX_CALLS by dropping candidates.
	6.	Determinism gaps
	•	You call out determinism as a success criterion  ￼, but there are multiple tie cases:
	•	equal max score on multiple pages (you noted this and suggested lowest page)  ￼
	•	Counter(...).most_common(1) tie behavior isn’t guaranteed stable across Python versions if counts tie  ￼
	•	find_best_mergeable_pair tie-breaking not specified  ￼
	•	Add: deterministic tie-break rules everywhere (e.g., page, then control_id sort).
	7.	K-means splitting with a “cluster_map” is under-specified
	•	Step 2 says “split_by_clustering(group, MAX_BATCH_SIZE)”  ￼, but the function signature passes cluster_map: dict[str,int]  ￼.
	•	A global cluster id doesn’t directly produce sub-batches ≤ MAX_BATCH_SIZE; you still need a packing strategy inside each cluster (or recluster within the page group).
	•	Add: define exactly how split_by_clustering turns cluster labels into bounded sub-batches.

⸻

Things I’d add to the plan (so it’s shippable)

1) Define inputs + add a “Step -1: dedupe”

Add a pre-step:
	•	Build unique_controls: dict[control_id] -> {max_score, primary_page, top_pages} by scanning page predictions (you already have a sketch)  ￼.
	•	Tie-break if scores equal: choose lowest page number (you already recommend)  ￼.
	•	Keep top_pages (you mention RetrievalAnchors can provide up to 3 pages)  ￼ for later.

This makes Step 0 capacity math correct and prevents duplicate LLM work.

2) Make MAX_CALLS truly hard with an explicit over-capacity policy

Right now you “may exceed MAX_CALLS”  ￼. I’d codify:
	1.	Try to batch + merge normally.
	2.	If still num_batches > MAX_CALLS, do secondary truncation:
	•	Drop entire controls starting from lowest max_score, but with diversity guards:
	•	per-page cap (don’t let one page dominate)
	•	or per-control-family cap (if you have categories)
	3.	Log structured telemetry: how many dropped, from which pages, min/max scores, etc. (You already log a warning in Step 0  ￼; expand that.)

3) Use target_batch_size explicitly as a “packing target,” not just a concept

You state the key insight (minimum necessary batch size)  ￼, but Step 3 doesn’t directly optimize toward it—just merges until ≤ MAX_CALLS  ￼.

Add to Step 3:
	•	Compute target = ceil(N / MAX_CALLS)  ￼.
	•	Prefer merges that move both batches toward target (e.g., merging 1+1 before 1+9 is good; merging 4+4 when target=4 is unnecessary).
	•	This reduces pathological merges and makes behavior more predictable.

4) Deterministic ordering + tie-break rules (write them down)

Add explicit rules:
	•	Always sort controls within a batch by (-max_score, control_id).
	•	Always sort batches by (primary_page, min_control_id) for stable output.
	•	For primary_page ties in Counter, pick the lowest page among tied modes (don’t rely on most_common)  ￼.
	•	For merge candidate ties, break ties by (combined_size, page_distance, min(primary_page), max(primary_page))  ￼.

5) Clarify what pages you send to the LLM (context-window footgun)

Your pipeline says “Gemini reads the full document”  ￼. If docs can be long, this becomes a practical failure mode.

At minimum, add:
	•	For each batch, pass page hints (primary page + top 1–3 pages) alongside the control list.
	•	If you are sending the whole doc, document the max doc size that fits and what happens when it doesn’t.

6) Expand tests to cover the real failure modes

You already have a great start  ￼. I’d add:
	•	Dedup test: same control appears on multiple pages; ensure only one instance makes it to batching.
	•	Hard MAX_CALLS test: construct a case where merging can’t get ≤ MAX_CALLS unless you drop candidates; assert you do the documented fallback.
	•	Determinism test: run twice with same input; byte-for-byte same output ordering.

7) Observability you’ll want on day 2

Add a small “Metrics” section:
	•	num_candidates_in, num_unique_controls, num_truncated_step0, num_truncated_postmerge
	•	num_batches_out, avg_batch_size, p95_batch_size
	•	avg_page_span_per_batch (max-min pages), avg_page_distance_in_merges
	•	downstream: LLM acceptance rate / disagreements per batch size (to validate the quality premise)

⸻

If you want, I can also propose a concrete Step 3 merging/packing algorithm that guarantees ≤ MAX_CALLS when feasible (and otherwise triggers the fallback deterministically), but the list above should cover the main “surprise” footguns in the current writeup.