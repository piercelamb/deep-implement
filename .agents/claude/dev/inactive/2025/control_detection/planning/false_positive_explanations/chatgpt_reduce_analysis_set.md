You’ve got two different problems mixed together:
	1.	Understanding the FP distribution (so fixes generalize), and
	2.	Finding the biggest FP drivers (so you get maximum lift per fix).

You can solve both without reading 5,287 instances by switching your unit of analysis from “FP row” to “FP pattern,” then sampling intelligently.

Step 1: Deduplicate into “FP patterns” (huge win)

Most of those 5,287 are repeats of the same failure mode.

Create a signature for each FP instance, then group on it:

Good signature fields (pick 3–6):
	•	control_id
	•	policy_doc_id (or policy family/type)
	•	IR_rule(s)_triggered (or the top IR)
	•	evidence_span_hash (hash of normalized excerpt text; lowercase, strip whitespace/punct, maybe keep 200–400 chars)
	•	reasoning_template_hash (optional: hash the model’s rationale summary)
	•	retrieval_chunk_id (optional; helps catch repeated chunk reuse)

Now compute:
	•	#unique patterns
	•	pattern frequency (how many instances each pattern accounts for)

Then: analyze patterns, not instances. One analyzed representative can “cover” hundreds of identical failures.

Practical policy: analyze the top patterns until you cover, say, 70–85% of all FP instances by weight.

This alone often turns “5,287” into “a few hundred patterns.”

⸻

Step 2: Stratified sampling for representativeness (coverage)

After dedupe, you still want to ensure the sample represents the distribution.

Use stratified sampling with weights. I’d stratify on:
	•	Control: head vs tail (e.g., top 20 controls by FP count; everything else)
	•	Policy doc: each of the 37 docs gets a minimum quota
	•	IR rule: each IR gets representation (because you’re fixing IRs)
	•	(Optional) confidence bucket: high/med/low confidence of the original mapping

A simple, strong allocation strategy

Make your sample be a mix of:
	1.	Impact slice (Pareto): take the most frequent patterns until you cover ~70% of all FP instances.
	2.	Representation slice: from the remaining patterns, draw a stratified random sample so every policy and IR is represented.

This prevents the classic trap: “we fixed the biggest cluster, but missed a totally different failure mode in the long tail.”

⸻

Step 3: Use clustering to reduce long-tail review effort

If you have lots of remaining “unique-ish” patterns, cluster them and sample cluster representatives.

Pipeline:
	1.	Embed the (control text + evidence excerpt + IR rule) into a vector.
	2.	Cluster (k-medoids or HDBSCAN).
	3.	Review cluster medoids (the most central example per cluster), plus 1–2 random extras per large cluster.

This is extremely cost-effective because many “unique hashes” are semantically the same mistake phrased slightly differently.

⸻

Step 4: Use sequential sampling + stop when stable

Don’t decide a sample size up front. Iterate until the distribution of root causes stabilizes.

Procedure:
	•	Start with, say, 150–250 pattern reviews (weighted toward top patterns).
	•	After each batch of 50, recompute:
	•	% per root_cause
	•	% per misapplied_rule
	•	Stop when the last two batches change each major bucket by less than, e.g., ±2–3 percentage points (or your tolerance).

This avoids over-sampling.

⸻

Step 5: A concrete “do this tomorrow” plan

0) Add bookkeeping

For each FP instance, store:
	•	control_id, policy_id, IR_rule, evidence_text, mapping_confidence, maybe chunk_id

1) Build patterns

Group by: (control_id, IR_rule, evidence_span_hash) (add policy_id if needed)

2) Choose review set

A. Top coverage patterns
	•	Sort patterns by frequency desc.
	•	Take patterns until you hit ~75% cumulative FP coverage.
	•	Review all of these (or at least the top N if still too many).

B. Stratified tail
From the remaining patterns:
	•	For each policy doc, sample at least 3–5 patterns
	•	For each IR rule, sample at least 10–20 patterns (depending on how many rules you have)
	•	Fill the rest with weighted random (weight = pattern frequency)

3) Estimate lift and prioritize fixes

When you label patterns with root_cause, compute:
	•	Expected FP reduction per fix = sum of frequencies of patterns addressed
	•	This gives you a ranked backlog of IR/prompt changes by impact.

⸻

How many do you actually need to review?

If you do pattern-based + Pareto + stratified tail, typical numbers are:
	•	100–300 pattern reviews to identify and validate the dominant failure modes
	•	300–600 if the space is messy and you want high confidence across 37 docs + many IRs

That’s usually a 10–20× reduction in cost vs 5,287.

⸻

One more trick: “cheap pre-triage” before human/judge review

Before spending judge tokens, auto-tag obvious buckets:
	•	Evidence contains only aspirational language (“may,” “aim,” “consider”) → likely non-binding
	•	Control requires a numeric (retention duration, frequency) and evidence has none → missing specificity
	•	Evidence references a different scope (employees vs systems) → scope mismatch

Even if imperfect, this helps you pick a more balanced sample and speeds review.

⸻

If you tell me what your IR list looks like (how many rules, and whether FPs are concentrated in a handful of IRs/controls), I can propose a concrete sampling allocation (e.g., “review the top 120 patterns + 12 per IR + 4 per policy = ~X total”) that’s tuned to your actual distribution.