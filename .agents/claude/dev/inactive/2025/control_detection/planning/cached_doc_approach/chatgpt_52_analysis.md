Below are the main mistakes/footguns I see in implementation_plan.md, plus concrete additions I’d make to the plan so it’s harder to build the “wrong” thing and easier to evaluate the new mode.

⸻

1) Internal inconsistencies that will cause bugs (fix first)

A. “Diverse” vs “Coherent” is contradictory in multiple places
	•	Overview claims diverse batching (5–10 dissimilar controls)  ￼
	•	Key design decision table says coherent is the intended default (with a toggle)  ￼
	•	Decider steps + architecture diagram still say create diverse batches and _create_diverse_batches()  ￼  ￼
	•	Success criteria says “Diversity: each batch has controls from different clusters”  ￼
	•	But the batching enum section makes COHERENT default  ￼

Recommendation: pick one narrative and align names/criteria everywhere:
	•	Rename _create_diverse_batches → _create_batches
	•	Update architecture diagram + success criteria to reflect the chosen default (coherent) and make “diverse” a variant experiment.

B. Candidate filtering is underspecified for “bounded calls”

You filter by doc_max_score >= 0.48  ￼ and promise “never > 50 calls”  ￼, but there’s no plan for what happens if the threshold yields too many candidates.

This matters because your prior results show retrieval is high-recall at 0.48  ￼, and LLMs get worse with overload  ￼—so you need an explicit candidate budget rule.

⸻

2) Big functional footgun: “exact quotes required” will cause false negatives

You require an “exact quote” in evidence_quote  ￼ and even instruct “If you cannot quote evidence, mark … false”  ￼.

That’s great for precision, but it will fail hard when:
	•	PDFs are scanned images / low OCR quality
	•	Gemini paraphrases or introduces minor OCR errors (hyphenation, ligatures, whitespace)
	•	“binding language” is split across lines/pages

Two ways to make this robust (I’d add one of them explicitly):
	1.	Back the quote requirement with deterministic text extraction. Pre-extract per-page text (PDF text layer if present; OCR otherwise) and validate quotes via fuzzy matching.
	2.	Relax “exact” to “verbatim after normalization” (casefold + collapse whitespace + remove soft hyphens), and enforce quote-validity with a validator. If it fails, downgrade confidence or flip to false.

Right now the plan doesn’t say how quotes will be validated or where they come from, only that the LLM must produce them  ￼. That’s a recipe for “hallucinated quote” or “missed control because quote formatting.”

⸻

3) Clustering plan is likely wrong unless you specify the embedding you’re clustering

The plan says “K-means on control embeddings” and “reuse from predictor.py cache”  ￼  ￼, but in your current system the retrieval model is late-interaction / token-level (ColBERT-style MaxSim)  ￼, and that often does not naturally give you a single fixed vector per control unless you explicitly define one.

Add a section that answers:
	•	What exact vector are we clustering? (e.g., pooled token embeddings? a separate sentence-embedding model? an existing “control embedding” artifact you already store?)
	•	How do we version clusters when the embedding model changes?

Also add determinism:
	•	seed / random_state
	•	saved metadata in control_clusters.json (embedding model name/hash, dim, n_clusters, seed, created_at)

Without this, clusters will silently drift and batching behavior becomes non-reproducible.

⸻

4) “Full document cached” still needs retrieval hints or the LLM will miss things

Your prior experiments show the LLM struggles even when the right candidates are present  ￼. A control-centric prompt that says “search the document” can actually be worse if the model doesn’t focus on the right pages/sections.

High leverage addition: for each control, pass retrieval-based anchors:
	•	top_pages: top 1–3 pages by ColModernVBERT score
	•	location_hints: “likely in Access Control section around page 12”
	•	optionally: extracted text snippets from those pages

This keeps the “full doc in cache” design, but gives the model a starting point and reduces misses.

⸻

5) Concrete additions I would paste into implementation_plan.md

A. Add a “Decision Budgeting” section (prevents candidate explosion)

Pasteable block:

## Candidate Budgeting (Required)

Filtering by doc_max_score >= threshold may yield more candidates than we can evaluate under max_calls.

Define an explicit control evaluation budget:
- max_calls_per_doc = 50
- target_batch_size = 8 (configurable; range 5–10)
- max_controls_per_doc = max_calls_per_doc * target_batch_size  # e.g., 400

If n_candidates > max_controls_per_doc:
1) Keep candidates with highest doc_max_score, but enforce per-cluster diversity:
   - For each cluster, keep top M controls by score (M computed to fit budget)
2) Log the truncation:
   - total_candidates, kept_candidates, dropped_candidates
   - dropped_score_p50/p90/min

Rationale: avoids uncontrolled cost and aligns with prior finding that overload harms LLM quality.

Tie to your earlier overload finding  ￼ and retrieval behavior  ￼.

B. Add “Anchored Evidence Search” (reduces misses + improves quote accuracy)

Pasteable block:

## Retrieval Anchors Per Control (Recommended)

For each candidate control, compute:
- top_pages_by_score: top 3 pages by ColModernVBERT score
- best_page: argmax page
- best_page_score: doc_max_score

Include these anchors in the LLM prompt for each control:
- "Start by checking pages: [p12, p13, p14] (highest similarity)"
- If evidence is found elsewhere, still allowed, but anchors are the default search path.

This uses the strengths of the existing retrieval stage described in the report  ￼ while addressing the LLM weakness  ￼.

C. Add “Evidence Quote Validation” (prevents hallucinated quotes)

Pasteable block:

## Evidence Quote Validation (Required)

We require evidence_quote, but we must validate it.

Implementation:
1) Extract per-page text:
   - Use PDF text layer when present.
   - Fallback OCR for scanned pages.
2) Normalize and validate:
   - casefold, collapse whitespace, remove soft hyphens
   - fuzzy match evidence_quote within extracted text
3) If validation fails:
   - downgrade confidence to "low" OR set addresses_control=false (configurable)
   - log: control_id, location_reference, evidence_quote, validation_status

Store: validated_page_number (if match found).

This makes the “quotes required” rule in your schema  ￼ safe instead of brittle.

D. Fix success criteria to match coherent default (and make “diverse” a variant)

Right now success criteria requires diversity  ￼ which conflicts with coherent default  ￼. Replace #3 with:

3. **Batching works**:
   - coherent: batches are predominantly single-cluster (or tightly related clusters)
   - diverse: batches maximize cluster spread
   - both: every candidate control appears in exactly one batch; n_batches <= max_calls

E. Add “Clustering Definition + Versioning”

Pasteable block:

## Control Clustering Details (Required)

Define the embedding used for clustering:
- embedding_source: <explicit> (e.g., pooled control encoder output OR separate sentence embedding model)
- dim: <int>
- preprocessing: <normalization / pooling>

Determinism + versioning:
- random_seed: 42
- Save metadata in control_clusters.json:
  - embedding_source, embedding_model_id/hash, dim, n_clusters, seed, created_at
- On mismatch (embedding hash differs), recompute clusters or hard-fail with a clear error.

This shores up the current vague “reuse from predictor cache” language  ￼.

⸻

6) Smaller but important implementation footguns
	•	Retry policy: you only retry ResourceExhausted  ￼. Consider also retrying transient timeouts and adding jitter; otherwise batch-level flakiness will look like model failures.
	•	Schema ambiguity: location_reference as a free string  ￼ is hard to evaluate automatically. Consider a structured form (page, section, confidence) even if you also keep a human-friendly string.
	•	Binding language broadening: allowing declaratives (“Passwords are 12 characters”)  ￼ can spike false positives unless you constrain it to policy-normative sections (Policy/Requirements) vs Background. Add a prompt line: “Declarative statements only count if presented as requirements, not descriptions.”

⸻

If you want, I can also rewrite your prompts/control_centric/system and response.json to incorporate (a) retrieval anchors and (b) quote validation expectations, while staying compatible with the current response schema.