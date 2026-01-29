Your README makes the core issue pretty clear: the map‑reduce succeeded at abstraction (195 → 13), but the “universal patterns” you got are descriptive of what policies contain (scope, mandates, procedures, roles, artifacts…) rather than predictive rules for deciding whether a specific policy satisfies a specific control.  ￼

That outcome is largely “baked in” by the prompts:
	•	Round 1 explicitly asks for “UNIVERSAL PATTERNS” and forbids control/policy specifics, which nudges the model toward high-level taxonomies rather than decision procedures.
	•	You only feed positive mappings (generalized reasons for pairs that do map), so the model learns “what compliant policies generally look like,” not “what distinguishes a mapping vs. a non‑mapping.”
	•	Reduce‑phase merge logic rewards generalization (“use the more general description when merging”), which tends to erase discriminative edges and converge to “policy anatomy.”

Below are concrete prompt changes that will push the system toward actionable heuristics (“do these checks; if X then Y”) while still fitting your map‑reduce structure.

⸻

1) Change the Round 1 goal from “universal patterns” to “decision rules”

What to change

In the Round 1 system prompt, replace “identify UNIVERSAL PATTERNS” with something like:
	•	“Extract auditor decision rules that can be applied to a new control‑policy pair.”
	•	“A rule is only valid if it can be written as an IF (control signal) + IF (policy evidence) → THEN (mapping effect).”
	•	“Avoid generic policy descriptors unless they materially change a mapping decision.”

Why this helps

It forces the model to produce patterns that are operationalizable, not just true.

Drop‑in replacement (System Prompt)

You are a GRC auditor. Your output will be used as a playbook for predicting whether a policy satisfies a control.

Your job is NOT to describe what policies usually contain.
Your job IS to extract DECISION RULES an auditor uses to decide “maps / partially maps / does not map”.

Each rule must include:
1) Control-side trigger: what in a control statement makes this rule applicable (verbs, nouns, obligations).
2) Policy-side evidence test: what text/features to look for in the policy (sections, keywords, artifact mentions).
3) Mapping effect: how this evidence changes the mapping decision (supports / weak support / blocks).
4) Failure modes: common false positives and what evidence is NOT sufficient.

If a candidate pattern cannot be expressed as an IF/THEN rule with observable signals, discard it.
Prefer narrower, more discriminative rules over broad “policy anatomy” statements.


⸻

2) Make Round 1 output atomic (stop bundling many evidence_types / mapping_patterns)

Right now your universal patterns often have 3–5 evidence_types and 2–4 mapping_patterns in one entry (e.g., “Explicit Mandate and Strategic Alignment” has multiple of each). That encourages “kitchen sink” patterns that merge too easily later.

What to change

In Round 1, enforce:
	•	Exactly 1 evidence_type
	•	Exactly 1 mapping_pattern
	•	If the reason implies multiple, split into multiple atomic rules.

Drop‑in addition (User Prompt)

Add this near the top of Round 1 user prompt:

Atomicity requirement:
- Each pattern MUST map to exactly ONE evidence_type and ONE mapping_pattern.
- If a reason supports multiple evidence_types or mapping_patterns, output multiple separate patterns.

Why this helps

Your reduce step will merge much more meaningfully, and the final set will look like “a toolbox of moves” rather than “8 big buckets.”

⸻

3) Add “how to apply” fields so the result becomes a playbook (not prose)

Right now, “description” is unconstrained and the easiest thing is a broad summary. You can keep your existing schema, but you’ll get much better results if you add required structure.

Recommended schema upgrade for Round 1

Add these required fields:
	•	control_triggers (array of strings)
	•	policy_cues (array of strings)
	•	decision_effect (enum: supports_mapping, weak_support, blocks_mapping)
	•	strength (enum: high, medium, low)
	•	insufficient_evidence (string)
	•	false_positive_risks (string)

Example revised pattern item:

{
  "name": "Ownership assignment satisfies 'assign responsibility' controls",
  "control_triggers": ["assign responsibility", "designate owner", "accountable for", "role responsible"],
  "policy_cues": ["Responsibilities section", "named roles (CISO, Data Owner)", "RACI-like language", "shall/must assign"],
  "decision_effect": "supports_mapping",
  "strength": "high",
  "insufficient_evidence": "Generic 'management is responsible' without a specific role or accountability",
  "false_positive_risks": "Titles listed without duties; role named but no authority to execute",
  "evidence_types": ["responsibility_assignment"],
  "mapping_patterns": ["ownership_alignment"],
  "observed_in": ["source_1", "source_2"]
}

If you cannot change the schema

Then enforce a structured mini-template inside description, e.g.:

Description format MUST be:
- Control trigger:
- Policy evidence:
- Decision effect:
- Not sufficient:
- False positives:

This is less robust than schema fields, but still a big improvement.

⸻

4) Stop asking Round 1 to avoid control details; instead abstract them into “control signals”

Your current instruction “Do NOT include policy-specific or control-specific details” is exactly why you got generic “policy anatomy.”

What to change

Allow control-level abstraction via signals:
	•	Verbs: establish, define, assign, review, retain, monitor, encrypt, log, prohibit
	•	Modality: must/shall vs “should”
	•	Evidence expectation: “document/record/log”

You don’t need to mention “SOC2 CC7.2” etc. You just need “this control is asking for X.”

Drop‑in wording

Replace:

“Do NOT include policy-specific or control-specific details.”

With:

Do not reference specific control IDs or policy names.
But you MUST express the rule in terms of:
- Control-side signals (what the control is asking for),
- Policy-side signals (what evidence in the policy satisfies it).


⸻

5) Add contrast: include non-mapping or weak-mapping examples (this is huge)

If you only aggregate reasons from successful mappings, the model has no way to learn what doesn’t count.

Two low-friction ways to do this

A) Add “near-miss” negatives per policy
For each policy, provide 3–5 controls it does not satisfy (or satisfies weakly) and include either:
	•	a short “non-mapping reason”, or
	•	just the control statement + “NOT SATISFIED” label.

Then ask Round 1 to extract:
	•	rules that support mapping
	•	rules that block mapping / indicate insufficient evidence

B) Generate synthetic negatives (if you don’t have labeled negatives)
Even synthetic “hard negatives” help:
	•	Take a mapped control and swap key requirement (e.g., “annual review” → “quarterly review”).
	•	Ask the model: “What policy evidence would fail this control?”

Prompt addition (Round 1)

You will be given both POSITIVE (maps) and NEGATIVE (does not map / insufficient) examples.
Extract rules that distinguish them.
Every rule must state whether it supports mapping or blocks mapping.

This is the fastest path to “predictive” heuristics.

⸻

6) Tighten the Reduce prompt to avoid over-merging into generic buckets

Your reduce prompt currently says: “Use the more general description when merging.” That is a recipe for generic convergence.

What to change
	•	Merge only if control_triggers overlap strongly and policy evidence tests are the same and decision_effect matches.
	•	If two rules share evidence_type/mapping_pattern but apply to different control intents, do not merge—keep siblings.

Drop‑in replacement snippet (Reduce System Prompt)

Merge conservatively.
Only merge patterns if they:
- Have the same decision_effect (supports/blocks),
- Have materially the same control-side triggers,
- Have materially the same policy evidence test.

Do NOT merge solely because evidence_types/mapping_patterns match.
If unsure, keep them separate (prefer specificity over generality).
When merging, preserve discriminative details and list combined triggers/cues.

Optional: allow hierarchy

Let the reducer output:
	•	a parent “family” rule
	•	plus child rules with specific triggers

This keeps universality without losing usefulness.

⸻

7) A concrete “better Round 1” user prompt you can paste in today

Here’s a version that keeps your union+consolidate approach but forces playbook-style output.

Analyze the following generalized mapping reasons from {NUM_SOURCES} policy documents and extract mapping DECISION RULES.

## Source 1: {SOURCE_1_NAME}
{SOURCE_1_REASONS}

## Source 2: {SOURCE_2_NAME}
{SOURCE_2_REASONS}

Goal: Produce a MASTER LIST of unique auditor rules that can be applied to NEW control-policy pairs.

Union + Consolidate logic:
1) Extract ALL distinct rules from either source.
2) If the same rule appears in both, merge and set observed_in accordingly.

IMPORTANT CONSTRAINTS:
- Each rule MUST be atomic: exactly ONE evidence_type and ONE mapping_pattern.
- Each rule MUST be actionable: include control triggers + policy evidence test + mapping effect.
- Do NOT include generic “policies define scope” unless it changes a mapping decision. Prefer rules that affect confidence and discrimination.

For each rule, include:
1) name
2) control_triggers: phrases/verbs/nouns in a control that activate this rule
3) policy_cues: what to look for in the policy text
4) decision_effect: supports_mapping | weak_support | blocks_mapping
5) strength: high | medium | low
6) insufficient_evidence: what would NOT count
7) false_positive_risks
8) evidence_types (ONE value from enums)
9) mapping_patterns (ONE value from enums)
10) observed_in

Use ONLY the provided enum values for evidence_types and mapping_patterns.


⸻

8) What your final output will look like (more aligned with your goal)

Instead of 8 broad universals, you’ll start getting things like:
	•	Rule: Ownership alignment
	•	Control triggers: “assign responsibility”, “designate”, “accountable”
	•	Policy cues: explicit role + duty + authority; escalation path
	•	Effect: supports mapping (high)
	•	Rule: Timing requirement
	•	Control triggers: “review annually/periodically”, “at least every”
	•	Policy cues: specific cadence + trigger for ad hoc review + evidence artifact (minutes/attestation)
	•	Effect: supports mapping if explicit; blocks if missing when control demands it
	•	Rule: Artifact requirement
	•	Control triggers: “retain records”, “maintain logs”
	•	Policy cues: named artifacts + retention period + ownership of records
	•	Effect: supports mapping; weak if artifacts listed without retention/owner

That’s the kind of “LLM reasoning playbook” your README says you actually want.  ￼

⸻

If you only do 3 changes, do these
	1.	Require IF/THEN decision rules with control triggers + policy evidence tests (most impact).
	2.	Make patterns atomic (1 evidence_type, 1 mapping_pattern) (prevents generic mega-patterns).
	3.	Introduce negatives or “insufficient evidence” cases (creates discrimination instead of taxonomy).

If you want, I can also sketch the downstream prompt that uses these rules to score a new (policy, control) pair and produce: (mapped? confidence? evidence excerpts? missing evidence?)—but the biggest leverage is fixing the aggregation prompts first.