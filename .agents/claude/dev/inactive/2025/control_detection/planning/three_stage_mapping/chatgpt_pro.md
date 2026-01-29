Here’s an analysis of the three‑stage plan and a set of concrete recommendations to increase precision (and keep the experiment measurable and actionable).  ￼

What’s strong about the plan

1) The added Stage 3 is directionally correct for your failure mode

Your hypothesis (“Gemini Flash is overwhelmed by full doc + long prompt + 10 controls → permissive MAPPED”) matches a common pattern: once the model sees any related language, it rationalizes a mapping. A per‑control verifier with an explicitly adversarial frame (“try to reject”) is a good way to counteract that bias.  ￼

2) Immediate dispatch is a good engineering choice for UX and experimentation

Spawning verifications as soon as Stage 2 produces MAPPED results gives you:
	•	early validated outputs (time‑to‑first‑verified)
	•	a clean concurrency story for the experiment
	•	a path to production latency improvements later (priority / reserved slots)

3) Reusing the Gemini cache is smart for cost

If the cache truly amortizes the document + system prompt, Stage 3 becomes a relatively cheap “second opinion” per candidate mapping.

The biggest gap: the math makes “80% precision” hard with Stage 3 alone

Your own worked example is a good sanity check: if Stage 2 yields 30 MAPPEDs with 6 TP / 24 FP (20% precision), and Stage 3 rejects 20 of the 24 FPs, you get 6 TP / 4 FP = 60% precision.  ￼

To hit 80% precision with the same 6 true positives, you need FP to drop to ≤ 1–2. That means Stage 3 must reject roughly 94%+ of false positives (and ideally not reject true positives). That’s a very high bar for a single LLM verifier.

Implication: Stage 3 is likely necessary, but probably not sufficient. You’ll likely need at least one of:
	•	fewer false positives entering Stage 2 (better candidate gating / doc-type filtering), or
	•	a stronger evidence discipline (verbatim + local + checkable quotes), or
	•	a “VERIFIED must be high confidence only” rule (and treat the rest as manual review), or
	•	a better model for verification (even if Stage 2 stays Flash)

Key risks & recommendations (high impact first)

Recommendation 1: Remove “confirmation bias” from Stage 3

Right now Stage 3 gets Stage 2’s evidence and reasoning. That’s useful for debugging, but it anchors the verifier toward agreement.

Change: Stage 3 should re-evaluate from scratch, using Stage 2 output only as a hint.

Two practical options:

Option A (best for precision): don’t pass Stage 2 reasoning at all
	•	Pass: control_id/name/description, and maybe page hints from Stage 1 (top 1–3 pages).
	•	Don’t pass: Stage 2 reasoning.
	•	Pass Stage 2 evidence quote only if you tell the verifier to treat it as untrusted.

Option B: pass it, but force an explicit “disprove first” workflow
Stage 3 prompt structure:
	1.	“First, verify the quoted text exists verbatim in the document at the claimed location. If you can’t find it verbatim, REJECT.”
	2.	“Second, restate the control requirements in 1–3 bullets.”
	3.	“Third, list all reasons this mapping could be wrong (guardrails, scope mismatch, artifact mismatch).”
	4.	Only then allow VERIFIED.

This is small prompt work, but it often makes a large difference.

⸻

Recommendation 2: Make Stage 3 require fresh evidence extraction (and output a verifiable quote)

Your Stage 3 plan tries to detect “assembled evidence” and guardrail violations, but the verifier can’t reliably do that if it doesn’t re-locate evidence in the doc.

Change: Stage 3 should be required to produce:
	•	verified_evidence_quote (verbatim, contiguous)
	•	verified_location_reference (page/section)
	•	(optional) evidence_is_verbatim: true/false

And your code should programmatically validate the quote exists in extracted page text (or in the PDF text you already have). If it can’t be found (within reasonable normalization), auto‑reject or downgrade.

This single move often:
	•	kills hallucinated/loose paraphrase evidence,
	•	enforces locality,
	•	gives you deterministic confidence boosters.

⸻

Recommendation 3: Adjust evidence rules by control type (ARTIFACT vs mandate)

Your Stage 3 rejection checklist includes “quote lacks binding language (must/shall/will).” That’s good for mandate-type controls, but it can be wrong for artifact controls.

Example from your Appendix B: an ARTIFACT control (DCF‑37) is mapped using a descriptive statement about the policy’s purpose.  ￼
If the control is essentially “an Acceptable Use Policy exists / is established,” requiring “must/shall” language may incorrectly reject true positives.

Change: Stage 3 should first classify the control requirement profile (artifact vs administrative vs technical) and then apply evidence standards:
	•	ARTIFACT controls: evidence may be document title, purpose statement, applicability section, version/approval block, etc. Binding language is not always required.
	•	MANDATE controls (admin/technical): require binding language and direct requirement coverage.

Your system prompt already has control typing logic (“Phase 1: Control Requirement Profile”). Make Stage 3 explicitly use it.

⸻

Recommendation 4: Add cheap deterministic “pre-verification filters” to cut Stage 3 volume

Right now every MAPPED + HIGH goes to Stage 3. If precision is low, this could be a lot of calls.

Before Stage 3, add cheap checks that automatically downgrade or reject obvious bad mappings:
	•	Binding-language check (only for mandate-type controls): if evidence quote lacks strong modal verbs (“must/shall/required”), mark as “needs verification” or auto-reject.
	•	Evidence locality check: if Stage 2 provides multiple locations / or quote length is tiny, treat as suspicious.
	•	Document-type gating: if document classified as Acceptable Use Policy, automatically reject controls requiring Physical Security Policy, BCP plan, etc., unless the control explicitly allows coverage in AUP.
	•	Page alignment check: if Stage 1 says top page(s) are {4, 7}, but Stage 2 cites page 1 with no overlap, downgrade confidence or reject.

These are cheap and will reduce LLM calls and improve precision.

⸻

Recommendation 5: Reduce Stage 2 “context search burden” by feeding only relevant text, not the whole PDF

Even with caching, the model is still effectively “searching” the whole doc. That’s a major source of permissive matches.

Since Stage 1 already scores controls against pages, you have a natural RAG structure:
	•	For each control in Stage 2, include:
	•	top 1–3 page numbers, and
	•	the extracted text of those pages (or top paragraphs).
	•	Instruct: “You may not use evidence outside these provided excerpts. If it’s not in these excerpts, output NO_MATCH.”

This will almost always increase precision. It may reduce recall slightly, but your pipeline is currently recall-heavy and precision-starved—this is a good trade.

A hybrid compromise:
	•	Stage 2 uses only top excerpts (precision).
	•	If Stage 2 returns NO_MATCH but retrieval score is extremely high, optionally run a “broader search” fallback.

⸻

Recommendation 6: Fix the Stage 3 response schema issues (important to avoid silent parsing failures)

In your proposed response.json:
	•	enum is incorrectly specified for control_id ("enum": "CONTROL_ID" should be an array, and conceptually you want const, not enum).  ￼
	•	You likely want conditional requirements:
	•	if verdict = REJECTED → require rejection_reason (and ideally guardrails_violated).
	•	if verdict = VERIFIED → require verified_evidence_quote + verified_location_reference.

Even if your schema system doesn’t support full JSON Schema conditionals, you can enforce it in code and treat violations as REJECTED.

Also consider allowing:
	•	guardrails_violated: string[] (multiple guardrails often apply)
	•	confidence: ["high","medium","low"] (or keep two levels but treat VERIFIED+medium as “manual review”)

⸻

Recommendation 7: Re-think “VERIFIED means cannot find reason to reject” into “VERIFIED requires affirmative proof”

Your current framing is good (“attempt to reject”), but you can make it even tighter:

Require Stage 3 to pass an explicit sufficiency test:
	•	“List the control’s mandatory qualifiers. For each, point to a phrase in the quote that satisfies it.”
	•	If any qualifier is not explicitly met → REJECTED.

This forces the model to demonstrate coverage rather than just “not noticing problems.”

⸻

Orchestration & concurrency recommendations

1) Tag tasks explicitly and fail closed

Your pseudocode uses is_stage2_task(task) vs is_stage3_task(task). Make this robust:
	•	name tasks via create_task(..., name="stage2:batch_03")
	•	or attach metadata on the task object
	•	and if parsing fails → treat as REJECTED (precision-first)

2) Ensure cache deletion is in a finally and doesn’t race outstanding tasks

If any tasks are still using the cache when you delete it, you’ll get flaky failures. For the experiment:
	•	wait for all spawned tasks to finish or cancel them,
	•	then delete cache in finally with asyncio.shield() as you noted.  ￼

3) Even in “experiment mode,” prevent runaway verification

“No hard cap” is fine until Stage 2 outputs 150 “MAPPED+HIGH” and you run 150 extra calls.

A safe experiment guardrail:
	•	cap Stage 3 calls to something large but finite (e.g., 100 per doc),
	•	and log when you hit the cap.

This prevents worst-case blowups while still letting you measure performance meaningfully.

⸻

Metrics & experiment design improvements

You already listed good metrics. Add these to make results more diagnostic:

A) Measure precision at different acceptance policies

Compute:
	•	Precision(VERIFIED only)
	•	Precision(VERIFIED + VERIFIED-medium)
	•	Precision(VERIFIED + PARTIAL-high) if you ever promote partial

This helps you pick a production policy.

B) Track “Verifier disagreement rate” and “TP loss rate”
	•	disagreement_rate = rejected / stage2_mapped_sent_to_stage3
	•	tp_loss_rate = stage3_rejects_true_positive / stage2_true_positives_sent_to_stage3

If you gain precision but lose many TPs, you’ll see it immediately.

C) Analyze rejection reasons distribution

Aggregate rejection_reason / guardrail violated counts:
	•	If most rejections are “binding language missing,” you can fix Stage 2 evidence discipline.
	•	If most are “doc-type mismatch,” you should add doc-type gating earlier.

D) Run ablations to pinpoint what actually helps

Suggested ablation grid:
	1.	Stage3 with Stage2 reasoning vs without
	2.	Stage3 uses Stage2 quote vs must re-extract quote
	3.	Stage2 full document vs top-page excerpts only

These three experiments will tell you if the core issue is anchoring, evidence quality, or context overload.

⸻

A pragmatic path to 80% precision

If the production requirement is truly ~80%+ precision, the most realistic approach is:
	1.	Make Stage 2 stricter and excerpt-based (reduce FP inflow)
	2.	Make Stage 3 proof-based + verbatim evidence extraction (reject remaining FPs)
	3.	Only “credit” VERIFIED+high; everything else becomes “needs review” (don’t count as mapped)

That combination can plausibly reach 80%+ precision because you’re:
	•	reducing the FP denominator before Stage 3, and
	•	requiring affirmative, checkable evidence for final acceptance.

⸻

Quick prioritized checklist

If you only do 5 changes, do these:
	1.	Stage 3 must re-locate and output a verbatim quote + page/section (and you validate it in code).
	2.	Remove or de-emphasize Stage 2 reasoning in Stage 3 to reduce anchoring.
	3.	Differentiate ARTIFACT vs mandate controls in Stage 3 evidence rules.
	4.	Feed Stage 2 only the top relevant page excerpts from Stage 1, not the full doc.
	5.	Fix the Stage 3 schema (control_id, conditional fields, guardrails list) and fail closed on parse issues.

If you want, I can also propose an updated Stage 3 prompt + schema that incorporates (1) re-extraction, (2) artifact-vs-mandate rules, and (3) qualifier-by-qualifier sufficiency checks—while staying compatible with your “reuse the same cache” constraint.