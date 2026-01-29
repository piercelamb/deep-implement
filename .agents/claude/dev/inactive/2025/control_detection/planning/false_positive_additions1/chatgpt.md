I mostly agree with your diagnosis: the confirmation stage is behaving like a permissive entailment classifier, and the IRs are functioning as “yes-generators.” Your stats (7 true controls vs 98 positives) scream that the model’s default prior is “it probably matches” once it sees any related security language—especially in an AUP-ish doc.

That said, I’d be careful with “require exact terminology” as the main fix. That will absolutely raise precision, but it’ll also nuke portability/generalization and you’ll reintroduce FNs that your FN analysis already exposed (synonyms, abstract outcomes, binding headers, etc.). The better move is: make ‘YES’ expensive, not “make ‘YES’ literal.”

Here’s what I think is actually happening, and what I’d do.

⸻

Why the guardrails aren’t firing

1) You’re missing a hard gating condition before IRs

Right now, the model can:
	•	grab any vaguely related sentence,
	•	declare it “direct,” or run IR-3,
	•	then retrofit qualifiers/scope via IR-1/IR-2/IR-6.

Guardrails only work if the model has to prove admissibility before it’s allowed to reason.

2) “Direct match” is unconstrained

“Direct” should mean: the evidence sentence contains (a) binding language + (b) a control-specific anchor + (c) the right domain/mechanism.
If “direct” can mean “mentions MFA somewhere,” you’ll map every MFA-flavored control.

3) IR-3/IR-4/IR-6 are too powerful in this architecture

These are exactly the rules that collapse distinctions:
	•	IR-3 turns topic similarity into “equivalence”
	•	IR-4 turns governance language into “implementation”
	•	IR-6 turns references into “existence”

Those three are precision killers when you’re already feeding the model high-recall candidate sets from embeddings.

⸻

What I’d change (concrete, high-impact)

A) Add a “Minimum Evidence Gate” (MEG) that must pass to map

Before any IR is allowed, require the model to extract an Evidence Triple:
	1.	Binding verb (must/shall/prohibited/required)
	2.	Control anchor (a noun phrase unique-ish to the control objective, not generic “security”)
	3.	Mechanism match (technical vs administrative vs physical vs training vs monitoring)

If any of the three are missing → NO_MATCH (or at most PARTIAL if the control is explicitly governance/process and you have 1+2).

This single gate will drop a huge portion of your FPs.

B) Kill “medium confidence MAPPED”

I agree with you. In your pipeline, “MAPPED” is effectively a positive classification. If you allow medium/low, you’re asking for FPs.
Make it:
	•	MAPPED only if confidence = high
	•	PARTIAL can be medium
	•	NO_MATCH for everything else

(You can still preserve recall by letting PARTIAL exist, but only when a policy-level gap is explicit.)

C) Replace IRs with “Allowed Bridges” that are type-specific

Instead of 10 IRs, use 3 narrow bridges:
	1.	Scope containment (old IR-1) but only if:

	•	policy scope is explicitly broad (“all systems / all employees”), and
	•	control target is a clear subset, and
	•	no explicit scoping restriction exists (“production only”, “remote access only”).

	2.	Parameter abstraction (old IR-2) but only for:

	•	algorithm strength, cipher suite versions, password length, etc.
And explicitly not allowed for:
	•	FIPS, authenticated/credentialed, tamper-evidence, immutable logs, specific fields, third-party scope, etc.

	3.	Binding inheritance (old IR-8) but only if:

	•	header is binding and
	•	the list item itself does not weaken it (no “should/may”).

Everything else—especially IR-3/IR-4/IR-6—should be either removed or made “NO_MATCH unless explicit.”

D) Introduce “Anchor Token” requirements per control family

This is how you fix the “one MFA sentence maps to every MFA control” problem.

For each control, derive 2–4 anchor tokens/phrases that must appear in the evidence sentence or immediately adjacent context, e.g.:
	•	MFA for remote access: must include “remote”/“VPN”/“offsite”/“external” or equivalent
	•	MFA for privileged/admin: must include “admin/privileged/root” or equivalent
	•	MFA for all users: must include “all users” or “all accounts” etc.

If the control has a qualifier, require an anchor for that qualifier. This is basically PG-12 operationalized into a deterministic-ish rule.

E) Add a “cap” sanity prior, but don’t hard block—route to review

I like your “if >30% MAPPED something is wrong,” but I’d implement it as:
	•	soft fail: downgrade all MAPPED to PARTIAL unless they pass an extra confirmation step
	•	or trigger a second-pass “batch consistency check” prompt

Because some docs (e.g., an all-encompassing InfoSec Policy) really can map to a lot. But an AUP mapping to ~80 is almost certainly wrong.

F) Fix candidate generation: don’t send 100% recall into the confirmer

This is under-discussed in your note but it matters:
	•	If embeddings retrieve 200 candidates, and you ask the LLM 200 times “does this match?”, the model will say yes too often.
Instead:
	•	Use embeddings to retrieve, then lexical pre-filter by required anchors/qualifiers before LLM.
	•	Or ask the LLM to select top-N controls that are most strongly supported before doing per-control confirmation.

Your architecture is currently incentivizing over-confirmation.

⸻

About your recommendations (my take)
	1.	“Remove or drastically restrict IRs” — yes, specifically remove IR-3/IR-4/IR-6. Keep only narrow IR-1/IR-2/IR-8 with hard gates.
	2.	“Only allow HIGH confidence MAPPED” — yes.
	3.	“Batch-level sanity check” — yes as a soft/second-pass check.
	4.	“Document-type priors” — yes, and make it explicit in prompt: “AUPs generally map to a small number of controls; treat mass mapping as suspicious.”
	5.	“Require exact terminology” — partially. I’d instead require control anchors, not exact phrases. Exact terminology is brittle.

⸻

A tighter confirmation prompt pattern (core idea)

If you want a compact behavioral change, add this constraint:

“You may only return MAPPED if you can extract a single sentence that contains BOTH (1) binding language AND (2) a control-specific anchor for the control’s objective/qualifier. If you need interpretive rules to invent either, return NO_MATCH.”

That forces the model to stop using IRs as escape hatches.

⸻

If you want the fastest precision win

Do these three changes first:
	1.	MAPPED requires: binding verb + anchor + qualifier present (MEG)
	2.	No medium/low MAPPED
	3.	Delete IR-3, IR-4, IR-6

That combo usually drops FP volume dramatically in these “confirm a candidate” pipelines.

⸻

If you paste your current “FP-optimized” prompt (or even just the IR/guardrail section), I can rewrite it into a short, production-grade confirmer prompt that bakes in the Minimum Evidence Gate + restricted bridges and is harder for the model to wriggle into “yes.”