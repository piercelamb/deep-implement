Here’s a concrete distillation plan that keeps the decision-critical logic (high precision, decent recall) while cutting/merging the “instructional” bulk that’s hard for an LLM to internalize in one pass.

1) Start from what your ground-truth is actually scoring

If your ground-truth is primarily scoring decision correctness (MAPPED/PARTIAL/NO_MATCH), then the prompt should optimize for:
	•	False-positive avoidance (explicitly prioritized in the methodology: default NO_MATCH + Golden Rule).  ￼
	•	Reliable evidence gating (binding verbs + admissibility filter).  ￼
	•	Correct handling of qualifiers and “policy vs procedure” gaps (primary vs secondary qualifier logic + “don’t penalize missing procedures/parameters”).  ￼  ￼
	•	Guardrails-first, IR-second order-of-ops (this is what protects precision while preserving recall via sanctioned bridges).  ￼  ￼
	•	Binary confidence rule (kills “creative” mappings).  ￼

If ground-truth also scores correct rule-citation IDs (G-#, IR-#), treat that as a separate subproblem and keep an ultra-compact ID cheat sheet (see §3).

⸻

2) Compression strategy: reduce “teaching,” keep “gates + decision tree”

Your current doc teaches a full methodology. A single-shot “do the task” prompt should instead be a tight decision procedure.

Keep (non-negotiable invariants)

These are the highest-leverage lines to preserve decision accuracy:
	1.	Stance + default

	•	“Strict external auditor”, default NO_MATCH, Golden Rule.  ￼

	2.	Evidence gate

	•	Binding language required; inadmissible sections rejected; hard/soft blockers.  ￼

	3.	Policy vs procedure

	•	Don’t penalize missing parameters/procedures/frequencies.  ￼

	4.	Primary vs secondary qualifiers

	•	Primary missing ⇒ block; secondary missing ⇒ doesn’t block if core mandate exists.  ￼

	5.	Order of operations

	•	Guardrails block → stop; IR bridges only if admissible binding evidence exists and no guardrail violated.  ￼  ￼

	6.	Sufficiency / no evidence assembly

	•	Evidence must stand alone (sufficiency test); avoid stitching across sections.  ￼

	7.	Decision criteria

	•	MAPPED requires all requirements; no “medium MAPPED”; any doubt => NO_MATCH.  ￼

	8.	Output schema

	•	JSON schema + rules_cited guidance.  ￼

Cut or move to appendix (low marginal utility in one-shot)
	•	Long “teaching” exposition, long lists of examples, extended guardrail table text.
	•	Document classification lists and broad calibration prose (keep as one-line heuristic only if it measurably reduces mass-mapping). The “mass mapping” anti-pattern can be reduced to a single warning + check.  ￼  ￼

Merge aggressively
	•	17 guardrails → 5–7 guardrail buckets (still faithful, easier to remember):
	1.	Type mismatch (technical vs admin/monitoring)
	2.	Domain/lifecycle mismatch
	3.	Scope restriction conflicts
	4.	Primary qualifier missing
	5.	Evidence quality inadmissible (external refs only, risk assessment vs implementation)
	6.	Evidence assembly / non-localized
	7.	Contradictions
	•	IR-1..IR-8 → “Allowed Bridges” list with short “never bridge” bullets (esp. IR-2 restrictions like FIPS/third-party/etc.).  ￼

This preserves recall without reopening false-positive floodgates.

⸻

3) Two-layer distilled prompt (core + micro “ID lookup”)

To maximize correctness, structure the prompt as:

Layer A — “Core algorithm” (what the model must follow)

A short, numbered checklist:
	1.	Extract control core objective + qualifiers; label qualifiers primary vs secondary.  ￼
	2.	Find one contiguous evidence quote with binding verbs; fail admissibility blockers.  ￼  ￼
	3.	Run guardrail buckets; if any hit → NO_MATCH.  ￼
	4.	If no guardrails, apply allowed IR bridges (subset scope, parameter abstraction with restrictions, frequency abstraction, binding inheritance).  ￼
	5.	Decide:
	•	MAPPED only if irrefutable; no “medium MAPPED”; any doubt => NO_MATCH.  ￼
	•	PARTIAL only for explicit exclusions/ownership silence/contradiction (rare).  ￼
	6.	Output JSON per schema.  ￼

Layer B — “Tiny rule-ID cheat sheet” (only if you need exact G/IR codes)

If your evaluator expects rules_cited to be correct, keep a one-line-per-ID table—no examples, no prose. The prompt already reinforces when to cite rules and when not to.  ￼
(If citations are not scored strictly, you can simplify to citing only IRs used + “guardrail triggered” category.)

⸻

4) How to distill safely: an ablation-based workflow

Do this like model compression, not editing:
	1.	Define a minimal “must pass” control suite

	•	Include cases that specifically test each mechanism:
	•	Primary qualifier missing (FIPS/third-party/etc.)  ￼
	•	Parameter abstraction allowed vs disallowed  ￼
	•	“should” soft-blocker nuance  ￼
	•	Evidence assembly/sufficiency failure  ￼
	•	“risk assessed” vs “implemented” evidence quality failure  ￼
	•	PARTIAL vs NO_MATCH vs MAPPED boundary  ￼

	2.	Iterative ablation

	•	Start with Layer A only (core algorithm).
	•	Add Layer B (ID sheet) only if rule-ID accuracy materially affects scoring.
	•	Each cut must be justified by “no regression” on the suite.

	3.	Error taxonomy logging
For each failure, label which gate failed:

	•	Missed binding verb gate / admissibility
	•	Misclassified primary vs secondary qualifier
	•	Skipped guardrail-before-IR ordering
	•	Overused PARTIAL
	•	Evidence assembly / non-localized quote
This tells you what text is actually doing work, and what is dead weight.

	4.	Guard against mass-mapping behavior
Keep a single hard warning: “If you’re mapping >30–40% of a batch, re-check each control has its own binding evidence and anchor.”  ￼
(This is small but often prevents catastrophic precision collapse.)

⸻

5) A concrete “distilled v1” shape (what the final prompt should look like)

You can target ~250–450 tokens by implementing:
	•	5-line stance + Golden Rule + default NO_MATCH  ￼
	•	8–10 line evidence admissibility gate (hard/soft blockers)  ￼
	•	6–8 line decision tree (guardrails → IR → decide; binary confidence)  ￼  ￼
	•	6–10 line “allowed bridges” summary (IR-1/2/3/5 mainly)  ￼
	•	1–2 line PARTIAL rule (rare + gap types)  ￼
	•	Output JSON schema + minimal rules_cited guidance  ￼

Everything else becomes appendix or gets dropped.

⸻

If you want, I can produce the actual distilled prompt text in that “Layer A + optional Layer B” format (tight enough for single-shot), but the plan above is the critical part: treat this as gate-preserving compression driven by ablation against your labeled ground truth.