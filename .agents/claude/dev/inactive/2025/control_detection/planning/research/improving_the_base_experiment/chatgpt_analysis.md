You’ve basically built a high-recall candidate generator (CONTROL_COVERAGE @ 0.48) feeding a human-like adjudicator (LLM) that’s getting worse when you hand it more “maybes.” So the core problem is no longer “find related controls,” it’s (a) shrink the candidate set without losing recall, and (b) force the LLM to behave like an evidence-based checker, not a semantic matcher.

Below are directions I’d seriously consider, in roughly “highest ROI first” order.

⸻

0) Quick sanity check: one metrics inconsistency to verify

In Exp 2 you list “GT above threshold (0.48) = 480 (93.8%)” but GT is 686, so 480 can’t be 93.8% of 686. That might be a reporting bug (per-page vs per-doc aggregation, or denominator changed). Before you optimize, confirm the evaluation plumbing is consistent across experiments—otherwise you can chase ghosts.

⸻

1) The obvious fix: stop giving the LLM 50–100 raw controls

Why it’s failing

Controls are semantically clustered + templated. If you show 100, you’re not giving “more signal,” you’re giving more near-duplicates and triggering attention collapse / satisficing (“pick a few that sound right”).

What to do instead (still “page → many controls”)

Add a middle rerank/dedup stage that produces smaller, cleaner, more diverse candidate sets than “top-K by similarity.”

Practical options:
	1.	MMR / diversity sampling over embeddings
Keep high-score items, but penalize controls that are too similar to already-chosen controls. This often beats top-K for “LLM list selection” tasks because it removes near-duplicates.
	2.	Cluster then pick representatives
Cluster candidates above threshold (e.g., by control text embedding), keep top 1–3 per cluster. LLM sees “one from each idea,” not 40 variants of access control.
	3.	Per-domain caps
If 70% of candidates are in one domain, cap that domain to N and keep others. This preserves breadth and reduces overload.
	4.	Dynamic K based on score distribution
Instead of fixed K=50/100: include all above threshold until the score gap drops below a delta, or until marginal gain is tiny.

Expected impact: precision up, LLM recall-vs-shown up, and you’ll often keep or improve end-to-end recall because you’re removing confusion, not removing signal.

⸻

2) Flip the problem shape (strongly recommended): “control → evidence” not “page → controls”

Right now your unit of work is “a page decides among many controls.” That’s the worst cognitive shape for an LLM.

New shape

For each control:
	1.	Retrieve the best 1–3 evidence spans/pages from the policy.
	2.	Ask the LLM a binary question: “Does this policy contain binding language satisfying this control? Show the sentence(s).”

This does two huge things:
	•	Candidate overload disappears: LLM evaluates 1 control at a time
	•	You can require evidence extraction, which kills false positives

How to make it computationally feasible

You don’t actually run 779 LLM calls blindly. You still use retrieval:
	•	Compute doc-level max score per control (max over pages) and keep controls above a threshold (or top-N per domain).
	•	For each kept control, attach the top evidence pages (by score) + neighbor pages if needed.

Even if you keep ~150 controls per doc, that’s 150 small LLM calls, which can be cheaper/more accurate than fewer giant calls depending on your provider + caching.

This is the single most likely change to move F1 materially, because it aligns the LLM with what it’s good at: targeted verification with cited evidence.

⸻

3) Make “evidence or nothing” a hard rule (fix the false positives)

Your prompt says “binding mandate required,” but the model can still “feel” like something matches and select it.

Make selection contingent on quoting

Require output to include:
	•	exact quote(s) containing must/shall/required (or equivalent),
	•	and a short paraphrase mapping quote → requirement.

If it can’t quote, it can’t select.

This usually:
	•	drops FP a lot,
	•	may drop recall initially (because the model is forced to be honest),
	•	but you can recover recall via better retrieval + section aggregation (next items).

⸻

4) Use the “vanilla RAG blob” — but not as your primary retriever

Yes, a text RAG store can help a lot, just not in the naive “semantic similarity solves it” way.

Best use of RAG here

Mandate-first evidence extraction:
	1.	Index chunks of extracted text with page numbers (or at least anchors).
	2.	Add a query recipe per control:
	•	include control keywords + synonyms,
	•	include binding verbs (“must”, “shall”, “required”, “prohibited”, “will ensure”),
	•	include likely artifact nouns (“review”, “log”, “approve”, “annually”, etc).
	3.	Retrieve top evidence snippets.
	4.	LLM judges the control using those snippets.

This makes RAG a precision booster (it surfaces binding sentences), not just another fuzzy matcher.

If you truly can’t keep page numbers, you can still use RAG to locate passages, but you lose explainability + debugging power. If you can fix one thing in that pipeline: preserve page provenance.

⸻

5) Section-level understanding beats page-level hacks

Your neighbor inclusion logic is a patch for a real issue: policies are structured in sections, not pages.

Upgrade granularity
	•	Detect headings / section boundaries (from PDF text or layout).
	•	Create “section objects” spanning 1–N pages.
	•	Run retrieval on sections, and adjudicate at section level.

Benefits:
	•	Fewer LLM calls,
	•	Less fragmentation (mandate sentence + definition sentence stay together),
	•	Better match to how controls are actually addressed.

⸻

6) Add a lightweight supervised model between retrieval and LLM

Right now you have:
embedding recall → LLM precision/recall

Insert:
embedding recall → cheap scorer → LLM

The “cheap scorer” can be:
	•	logistic regression / XGBoost on features like:
	•	ColModernVBERT score,
	•	BM25 score,
	•	keyword overlap,
	•	presence of binding verbs near matched terms,
	•	domain match with section title,
	•	control length / specificity priors.
	•	or a small cross-encoder reranker trained on your 686 labeled positives + mined hard negatives.

This is often a giant ROI lever because your dataset is already labeled.

⸻

7) Improve retrieval quality where it matters: “hard negatives” and “near-duplicate controls”

Your recall at threshold is great, but ranking is bad (GT can be #771). That’s exactly what you’d expect without training against hard negatives (controls that are semantically close but wrong).

Concrete steps
	•	For each GT (policy, control) positive pair:
	•	sample top-50 non-GT controls by embedding score as hard negatives
	•	Fine-tune:
	•	either the embedding model (contrastive),
	•	or a reranker.
Even a modest reranker can turn “GT anywhere” into “GT usually in top 50,” which directly attacks your top-K ceiling.

⸻

8) An agentic approach can work — if you constrain it

“Agent with tools to query RAG, load pages, etc.” is promising, but only if it’s not wandering.

A good agent loop here looks like:
	1.	Start from retrieval candidates (thresholded).
	2.	For each candidate control:
	•	query RAG for binding sentences + synonyms,
	•	if evidence found → verify,
	•	else → reject quickly.
	3.	Escalate only uncertain cases to deeper page inspection.

Key is tight budgets and deterministic steps, not open-ended reasoning.

⸻

If I had to pick a 2–3 step plan
	1.	Switch to control-first adjudication (control → top evidence pages/snippets → binary decision with quotes).
	2.	Add diversified candidate selection (MMR/clustering + per-domain caps) before any LLM step.
	3.	Use RAG mandate extraction to feed the LLM evidence, and require quotes to select.

That combination attacks:
	•	candidate overload,
	•	false positives,
	•	and “control spread across pages/sections.”

⸻

If you tell me what your current constraints are (LLM cost per call, max context, whether you can reliably extract PDF text with page numbers), I can sketch an end-to-end architecture with exact data objects + routing logic (and how to evaluate it so you know which stage actually moved the needle).