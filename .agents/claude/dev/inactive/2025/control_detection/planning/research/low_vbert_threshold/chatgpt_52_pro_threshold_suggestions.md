You’re running into two overlapping issues:
	1.	Your current ColModernVBERT score is essentially “% of the page that can be aligned to the control”, and pages are long/noisy (headers/footers/logos/boilerplate), so even “perfect” matches top out around ~0.4. That forces a low threshold.  ￼
	2.	Your eval ground truth includes compliance associations that often have weak/no semantic overlap with the policy text, so a semantic retriever has to keep a ton of candidates to avoid missing those “compliance-only” controls.  ￼

Below are fixes that I think will actually move the needle, ordered by “most likely to help quickly” → “bigger changes”.

⸻

1) Flip the scoring direction: measure “control coverage” instead of “page coverage”

Right now (as described in your normalization writeup), you’re doing a MaxSim late interaction where the sum is over page tokens, then normalizing by page self-similarity. That answers:

“How much of the page looks like this control?”

But you typically want:

“How much of this control is supported by something on the page?”

That’s a different question. In ColBERT terms, you want the control tokens to be the ‘query’ and the page tokens to be the ‘document’.

What to implement

You already have the similarity matrix between page token embeddings and control token embeddings. Just change the pooling:
	•	Current (page→control):
s_{p,c} = \sum_{i \in \text{page tokens}} \max_{j \in \text{control tokens}} \langle p_i, c_j \rangle
	•	Proposed (control→page):
s'_{p,c} = \sum_{j \in \text{control tokens}} \max_{i \in \text{page tokens}} \langle c_j, p_i \rangle

And normalize by control self-similarity (exactly like you did for pages):
	•	\text{upper}_c = \sum_{j} \max_{k} \langle c_j, c_k \rangle
	•	\text{norm}'_{p,c} = \text{clamp}( s'_{p,c} / \text{upper}_c, 0, 1)

Why this tends to help candidate size

A short control with a few distinctive concepts (“asset inventory”, “encryption key rotation”, “PowerShell constrained language mode”) will only score high if those concepts show up on the page. Boilerplate on the page no longer inflates the score because you’re not summing over page noise.

This doesn’t magically solve semantic-vs-compliance mismatch, but it usually widens the useful score range and makes thresholds sane for the semantically-retrievable part of the problem. Your current observation that even near-perfect matches are ~0.38 of page self-sim is a strong signal that you’re optimizing the wrong direction for thresholding.  ￼

Even better: use a bidirectional score

Compute both normalized scores:
	•	page_coverage = page→control normalized (what you have)
	•	control_coverage = control→page normalized (new)

Then combine them with something strict like harmonic mean:

\text{bi}(p,c) = \frac{2}{\frac{1}{\text{page\_coverage}+\epsilon} + \frac{1}{\text{control\_coverage}+\epsilon}}

This tends to keep pairs where the page actually talks about the control AND the control is well-supported by the page, and it knocks out a lot of “generic control matched generic page language” cases.

⸻

2) Penalize “generic controls” with baseline correction (z-score / percentile per control)

You already saw a symptom: controls like “System Security Plans” float to the top even when they’re not the right semantic match.  ￼
That’s classic “generic query” behavior: some controls are just easy to match everywhere.

Fix: normalize per control using score distributions

For each control c, compute its distribution over a background set of pages (you already have hundreds of pages from template policies; even better if you can use a larger corpus).
	•	mean_c = average of norm’(p,c) across pages
	•	std_c = stddev of norm’(p,c) across pages

Then:

z(p,c) = \frac{\text{norm}'(p,c) - \mu_c}{\sigma_c + \epsilon}

Or use percentile instead of z-score:
	•	pct(p,c) = percentile rank of norm’(p,c) within that control’s page-score distribution

How to use it

Instead of “keep score ≥ 0.23”, do:
	•	keep if z(p,c) ≥ 2.0 (or pct ≥ 99th)
	•	OR keep top-K by z per page (small K, like 25–50)

This is one of the cleanest ways to kill “always-high” generic controls without OCR.

⸻

3) Stop feeding the LLM “a page + hundreds of controls”. Invert the LLM step.

Your current downstream pain comes from trying to pack huge candidate lists into a single prompt. The simplest way to make this tractable with the tools you listed is:

Control-centric verification
	1.	Use retrieval to get a document-level candidate set of controls (not page-level thresholding).
	2.	For each candidate control, pick the top 1–2 evidence pages (by control→page score or by z-score).
	3.	Run a small multimodal LLM call:

Input: (control ID + name + description) + (page image(s))
Output: {supported: yes/no, evidence: short quote/region description, confidence}

This replaces “one giant prompt” with many tiny prompts you can parallelize (Flash/Haiku-style). You also get cleaner attribution (“this control is supported by page 7”).

Why this is a big deal

Even if retrieval still returns, say, 150–250 controls for a document, you’re no longer forcing the model to compare 150 descriptions at once. Each decision is a binary (or ternary) verification problem.

This also naturally eliminates pages: a page that isn’t top-1/top-2 for any candidate control never gets sent anywhere.

⸻

4) Use document-type classification as the “compliance bridge” (covers the semantic mismatch cases)

Your own analysis shows the low threshold is dragged down by controls that are associated for compliance reasons but don’t semantically appear in the policy (e.g., Windows hardening controls tied to Change Management).  ￼  ￼

If you truly need recall on those, you need a non-semantic signal.

Practical path with your toolbox
	•	Run a fast vision LLM on page 1 (or title + TOC pages) to classify:
	•	policy type (e.g., “Change Management Policy”, “Access Control Policy”, “PCI DSS Compliance Policy”)
	•	optionally 1–3 secondary types/domains

Then use a mapping:
	•	policy type → known associated controls (from your framework metadata / internal mapping)

Candidate controls = union of:
	•	controls associated with predicted policy type(s) (compliance mapping)
	•	controls retrieved semantically above a higher threshold (semantic mapping)

This lets you raise semantic thresholds dramatically without sacrificing compliance recall, because the “compliance-only” controls come in through the policy-type path, not through semantic similarity.

If your control dataset doesn’t already have “associated policy types”, you can bootstrap it from your existing ground truth (policy name → set of controls), then refine over time.

⸻

5) LLM-expand each control into “policy-language queries” and score against those too

This is a middle ground if you can’t (or don’t want to) rely heavily on metadata mappings.

Offline (one-time, cached), use a strong LLM to generate 2–5 short “policy evidence phrases” per control, e.g.:
	•	Control: “PowerShell Constrained Language Mode”
	•	Expansions:
	•	“Changes to endpoint scripting configurations must follow change management and approval”
	•	“Administrative configuration baselines are managed and updated through controlled change procedures”
	•	“Security configuration changes are reviewed, approved, tested, and documented”

Then at retrieval time:
	•	Score page vs each expansion string (plus the original description)
	•	Take max (or a weighted max)

This directly injects the compliance rationale into the text side so your semantic matcher has something to grab onto. It’s noisy if done naively, but with short, consistent templates it can help pull up those “compliance-only” controls so you don’t need 0.22-ish thresholds globally.  ￼

⸻

6) A lightweight supervised “calibrator” using only your score matrix (no OCR, no new model)

You already have labeled data: for each document, which controls are positives.

Instead of thresholding raw similarity, train a tiny model (logistic regression / XGBoost) that takes features derived from the score matrix:

For each (doc, control):
	•	max score across pages
	•	mean of top-2 / top-3 pages
	•	“peakiness” = max − median (or max − mean)
	•	maybe page index of max (some controls cluster on specific sections)
	•	control length / domain (if available)

Train to predict “control is in GT for document”.

This often dramatically improves ranking because it learns:
	•	generic controls that always score high are usually negatives
	•	controls with one sharp spike on one page are more likely positives than controls with flat moderate scores everywhere

Then you can take “top N by predicted probability” and get much smaller N for the same recall.

This is one of the highest ROI tricks if you’re sitting on score matrices already.

⸻

7) If you’re willing to do minimal text/layout extraction, do it strategically (not full OCR-everything)

You said you’d prefer not to extract text/layout, but if you ever decide to, the sweet spot is:
	•	OCR only:
	•	page titles/headings
	•	TOC entries
	•	bolded section headers
	•	maybe first line of each paragraph

Even a noisy “bag of headings + keywords” enables:
	•	BM25 keyword filtering (great at killing false positives)
	•	domain classification (cheap and accurate)
	•	hybrid fusion with ColModernVBERT ranks

You don’t need perfect OCR; you just need enough lexical signal to separate “PowerShell” from “asset inventory”.

⸻

What I would do first (concrete plan)
	1.	Implement control→page scoring + control-self normalization (plus optional bidirectional combo).
	2.	Add per-control baseline correction (z-score or percentile).
	3.	Switch downstream to control-centric verification (one control + top-2 pages per call) using a small fast multimodal model.
	4.	Add policy-type classification (page 1) to cover compliance-only controls, and union those candidates with semantic candidates.

This combination attacks:
	•	score range/thresholding (1–2)
	•	LLM token explosion (3)
	•	semantic-vs-compliance mismatch (4)

And it does it without requiring full OCR.

⸻

One last note: don’t chase “perfect recall” on controls that aren’t in your control set

Your normalization doc found that a non-trivial slice of ground truth controls simply don’t exist in the 779-control set (so they can never be retrieved). That’s an eval/data hygiene issue you’ll want to fix regardless of retrieval strategy.  ￼