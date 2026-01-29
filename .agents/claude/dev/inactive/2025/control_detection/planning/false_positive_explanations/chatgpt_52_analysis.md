Here’s what jumps out to me as the biggest footguns in this FP-analysis plan, plus what I’d add to make it sturdier and more actionable.  ￼

Footguns


2) Judge anchoring / “reviewing the model’s reasoning” bias

You’re explicitly feeding the original LLM reasoning + IR rules. That’s useful for debugging, but it anchors the judge into the same framing and often reproduces the same mistakes (“looks reasonable because the earlier model said so”).

Mitigation options (pick one or combine):
	•	Or: keep one pass, but instruct the judge to first write an independent determination before reading the original reasoning (and enforce it in schema: independent_verdict, anchored_verdict).

⸻

3) Sampling 100 FPs “randomly across policies” can be badly unrepresentative

FPs are often dominated by:
	•	a handful of high-frequency controls, or
	•	a few policy templates that trigger specific IRs.

A naive random sample can overfit you to the loudest cluster and miss long-tail failure patterns.

Fix: stratify sampling across at least:
	•	Control frequency (head vs tail),
	•	Policy type (security policy vs HR, vendor mgmt, etc.),
	•	IR cited in the original mapping (so you can attribute blame to the right rule),
	•	optionally confidence buckets (high-conf FPs are most dangerous).

Also record and persist the sampling seed for reproducibility.



⸻

5) Evidence quote may not be binding, but judge needs more than a single snippet

Your plan rightly asks “was it binding?”, but if you only provide one quote you’ll get tons of UNCERTAIN or shaky “confirmed” results.

Fix: always provide:
	•	the quote,
	•	the section header and any surrounding modal verbs (“shall/must/required”),
	•	and the nearest scope statement (e.g., “applies to all systems…”).

⸻

6) “Misapplied_rules” can become noisy unless you constrain it

If you let the judge freely name “root causes” and IR misapplications, you’ll end up with mushy categories and hard-to-aggregate output.

Fix: define controlled vocabularies:
	•	root_cause as an enum (10–20 categories),
	•	misapplied_rules constrained to IR-1..IR-10 plus maybe NONE/NOT_SPECIFIED,
	•	add failure_mode like SCOPE_OVERREACH, GENERIC_SECURITY_LANGUAGE, NON_BINDING_STATEMENT, TECH_SPECIFICITY_REQUIRED, etc.

⸻

7) Dedupe & weighting: you’ll double-count the same issue a lot

You note “same controls can be a false positive across many documents” — if you aggregate naïvely, you’ll bias the analysis toward repeated templates.

Fix:
	•	Produce stats both by-instance and deduped:
	•	dedupe by (control_id, policy_template_hash) or (control_id, policy_name) depending on need,
	•	Track “FP rate per control” and “FP rate per policy family.”

⸻

What I think is missing (additions)

A) Add an explicit “what would make it map?” field

For prompt iteration you want actionable constraints.

Add to schema:
	•	missing_requirement: what concrete requirement is absent (e.g., “must specify time sync source / NTP / log retention”)
	•	minimum_evidence_needed: the smallest policy statement that would justify mapping

This makes it much easier to tighten IR rules precisely.

⸻

B) Add calibration checks so the judge isn’t just “always confirming”

Add lightweight meta-metrics:
	•	% CONFIRMED_FP vs UNCERTAIN 
	•	correlation between original mapping confidence and judge confidence
	•	spot-check with a small known set of true positives / true negatives (“canary set”) to ensure the judge isn’t drifting.

⸻

C) Add multi-judge or self-consistency for the “high-impact” slice

For top-importance items (e.g., high-confidence mapped results, high-frequency controls), use:
	•	2 different judge prompts or models, or
	•	same model with 3 runs + majority vote.

Not for everything—just the slice where you most fear systematically tightening the wrong rule.

⸻

E) Add “IR applicability constraints” directly to outputs

Since the point is fixing interpretive rules, have the judge output:
	•	rule_constraint_suggestion: e.g., “IR-2 allowed only if control does NOT specify an implementation detail beyond generic encryption”
	•	counterexample_control_types: e.g., “clock sync”, “log retention durations”, “MFA method requirements”

This gives you a direct to-do list for IR edits.

⸻

Concrete changes I’d make to your schema (minimal but high impact)

Verdict enum:
	•	CONFIRMED_FP
	•	UNCERTAIN

Add fields:
	•	independent_assessment (1–2 sentences, before reading original reasoning)
	•	missing_requirement
	•	minimum_evidence_needed
	•	rule_constraint_suggestion
	•	needs_more_context: boolean (and if true, what to fetch)

Constrain taxonomy:
	•	root_cause: enum list
	•	failure_mode: enum list (optional but useful)

⸻

Final “gotcha” to watch for

If your FP judge sees the original mapping system prompt and it’s long, it may spend tokens “understanding the rules” instead of evaluating policy content. Keep the judge prompt short, and include only the IR list + definitions, not the entire mapping prompt verbatim unless necessary.

⸻

If you want, I can propose a root_cause enum (10–20 categories) tailored to the specific IR-1…IR-10 behaviors you described, so your aggregation in fp_analysis_summary.json becomes immediately useful rather than a pile of free-text.