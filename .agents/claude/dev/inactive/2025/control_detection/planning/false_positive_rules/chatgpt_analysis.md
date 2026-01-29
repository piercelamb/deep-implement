Overall: this plan is solid and very implementable. It’s basically Option A done “for real” (clear phases, schema’d JSON output, provenance, pilot mode, and atomic writes). The biggest risks now are (a) over-blocking / FN regressions, (b) batching bias (sorting by policy_name can accidentally hide diversity), and (c) phase-3 synthesis making rules too generic.  ￼

Here’s what I’d change / add.

What I like (keep)
	•	3-phase pipeline is exactly right: extract → merge within root cause → de-conflict across causes.  ￼
	•	Pilot mode is a must-have and you already have it.  ￼
	•	Boundary conditions + recovery checks baked into the rule schema is the main defense against turning “avoid FPs” into “block everything.”  ￼
	•	Provenance (derived_from) + batch outputs will save you when a rule causes a regression.  ￼

The main footguns

1) example_count is wrong in Phase 1 (easy bug, big downstream effects)

Right now you set example_count=len(fps) for every rule emitted from the batch. That makes every rule look equally frequent and will mess up “universal vs rare” logic and any later ranking.  ￼

Fix: change example_count to mean “approx #examples supporting this rule,” and require the model to output example_ids (or indices) per rule; then compute example_count=len(example_ids) yourself.

2) Sorting high-volume categories by policy_name can bias the rules

It’s great for “keep similar together,” but it can also:
	•	overweight a few verbose policies
	•	produce policy-specific rules that don’t generalize
	•	hide long-tail patterns until late batches  ￼

Mitigation: do stratified batching:
	•	Group by policy_name (or (policy_name, control_type)), then round-robin into batches so each batch has diversity but still coherent clusters.
	•	Or keep your sort, but also add a “diversity pass” batch per root_cause sampled across policies.

3) Phase 3 synthesis is where rules get mushy (and regress)

If the synthesis prompt “merges” too aggressively, you’ll end up with vague rules that block valid mappings (“semantic similarity isn’t enough”) without testable conditions.  ￼

Hard requirement I’d add to Phase 3 output:
	•	Every final rule must include at least one positive allow condition (“ALLOW if evidence includes X”) in addition to the block/boundary/recovery trio.
	•	Also require a conflicts_with: [rule_id...] field to make collisions explicit instead of silently resolved.

4) Output schema: “decision_effect” is always blocks_mapping

I get why (FP rules), but it’s limiting: sometimes the best “avoidance rule” is “require more evidence” not “block.” Right now you force everything into “block.”  ￼

Suggestion: allow decision_effect enum:
	•	blocks_mapping
	•	requires_more_evidence
	•	downgrade_confidence
Even if you initially only use blocks_mapping, having the shape prevents you from inventing hacks later.

5) Missing: determinism + repeatability controls

You’re using temps (0.7/0.5/0.3). Good, but for a pipeline like this you’ll want:
	•	a run metadata file (you mention it) that records model, temps, prompt hash, input counts, and git SHA.  ￼
	•	ideally a fixed seed if the API supports it (not always possible)

Prompt/schema improvements I’d add

Add “counterexample safety”

In Phase 1, require each rule to include:
	•	safe_example_pattern: what a valid mapping would look like that might otherwise be blocked
	•	danger_example_pattern: the FP bait

This forces the model to think in discriminators, not platitudes.  ￼

Add grounding fields (lightweight, huge value)

Have the model emit:
	•	evidence_triggers: short quoted spans (from original_evidence_quote) that caused the FP
	•	required_evidence: what must be present for a map to be allowed

That makes rules auditable and turns them into deterministic checks later.

Testing: one more gate you should add

Your “dry-run against known True Positives” is great. Add one more:
	•	Backtest on the same FP set: measure how many FPs each rule would have caught (coverage) and check overlap. Otherwise you can generate 200 rules that all describe the same thing.

Also, add a simple “rule linter”:
	•	blocking_condition contains “always/never” → fail unless boundary_condition is non-empty and concrete
	•	boundary_condition must reference evidence or scope explicitly (not “unless it’s relevant”)

Quick “do this next” checklist
	•	Fix example_count by collecting per-rule example IDs.
	•	Switch batching to stratified/round-robin by policy_name (at least for SEMANTIC_STRETCH / SCOPE_OVERREACH).
	•	Expand decision_effect to include requires_more_evidence (even if unused at first).
	•	Tighten Phase 3 prompt to not generalize away discriminators; require allow-conditions + explicit conflicts.
	•	Add rule coverage/backtest + linter step.

If you paste your Phase 2 + Phase 3 prompt templates (or if they’re in the plan but omitted), I can mark up the exact wording changes to reduce “mushy rule” risk.  ￼