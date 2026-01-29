Claude’s write-up is directionally right: your false positives aren’t “random,” they cluster around a few generalizable failure modes (document identity, scope creep, “presence vs configuration,” “input vs program,” and “behavioral vs technical enforcement”). The main tweak I’d make is: don’t add a pile of topic-specific guardrails (proxy/encryption/antimalware)—fold them into a small number of abstract, reusable guardrails with a couple of examples each. That keeps it robust across arbitrary policy/control sets.

What’s strong about the suggestions
	•	They correctly diagnose the core error: the model is mapping on keyword adjacency and plausible implication instead of on an explicit mandate with the right mechanism/scope.
	•	They identify “document-type controls” as a special pitfall: “this is a policy” ≠ “this establishes the policy required by the control.”
	•	They spot “use vs management” and “install vs configure” errors: these are ubiquitous across frameworks (ISO, NIST, CIS, SOC 2).

Where I’d adjust for generalization

Several proposed “new guardrails” are really instances of guardrails you already have:
	•	Proxy → IDS/IPS/filtering is basically G-2 + G-4 + G-14 (behavioral vs technical + mechanism mismatch + general≠specific).
	•	Encryption mention → key management/configuration is basically G-10 + G-14 (missing qualifiers and specificity) plus a “presence vs management” nuance.
	•	IR reporting → IR program is basically G-13 (risk/process ≠ implementation) plus a “program completeness” nuance.
	•	“May be monitored” should already die in your Admissibility Filter (permissive language), but it’s not being enforced hard enough.

So rather than adding 6–8 bespoke guardrails, I’d add 3–4 “meta-guardrails” that subsume these patterns and are easy for an LLM to apply consistently.

⸻

Recommended prompt changes (general-purpose)

1) Add a “Document Identity / Artifact Purpose” guardrail (covers the “Document IS Policy” fallacy)

New Guardrail: G-15 — Artifact Identity & Primary Purpose

Block when: A control requires an artifact like a policy/plan/standard/register, but the document under review is not clearly that artifact by title/purpose/scope, or only addresses the topic as a subsection.

Operational test (fast and general):
	•	Does the title or purpose explicitly indicate the document establishes the required artifact?
	•	Does the scope match the artifact’s expected breadth (org-wide vs narrow behavioral rules)?
	•	A section about X inside a different policy is not “the X policy.”

This is framework-agnostic and will stop “AUP → InfoSec Policy” style FPs everywhere.

⸻

2) Add a “Presence/Use vs Configuration/Management” guardrail (covers encryption/antimalware/firewall/mobile hardening)

New Guardrail: G-16 — Presence vs Operational Characteristics

Block when: The control requires how something operates/configures/is managed (e.g., automatic updates, default-deny, key rotation, hardening standards, scanning on insert, specific logging attributes), but the evidence only mandates:
	•	“use/enabled/installed/implemented” (presence), or
	•	a high-level outcome without the required operational modifier.

Rule of thumb: If the control includes an operational qualifier like automatically, configured to, default, managed, hardened, rotated, tamper-evident, immutable, on insert, then that qualifier must appear in the same evidence sentence (or an exact strict synonym). Otherwise NO_MATCH (G-16).

This one guardrail knocks out multiple FP families without being encryption- or malware-specific.

⸻

3) Add an “Input to Program vs Program Exists” guardrail (covers incident-response overreach + training overreach)

New Guardrail: G-17 — Program Completeness / Input ≠ Program

Block when: Evidence describes one input or component (e.g., “users report incidents”) but the control requires a formal program/artifact (incident response plan, breach notification procedure, training program for responders, detection/handling procedures, etc.).

Operational test: If the control contains words like plan, program, procedure, runbook, training (delivered), exercises, roles/responsibilities for responders, then the evidence must explicitly mandate that artifact/program/training—not merely user reporting or awareness language.

This generalizes beyond IR to any “program” control (vuln mgmt program, access governance program, vendor management program).

⸻

4) Strengthen G-2 into an explicit “Who/What enforces” test (covers proxy/user scanning vs automatic scanning)

Your existing G-2 is right, but it needs a sharper operational rule:

G-2 (enhancement): Behavioral vs Technical Enforcement
	•	If the evidence is phrased as “Users/personnel must…” it is ADMINISTRATIVE evidence.
	•	It can only satisfy a TECHNICAL control if the same sentence also states a system enforcement/configuration (e.g., “systems are configured to,” “technology enforces,” “access is technically restricted by…”).
	•	Time/trigger mismatch defaults to NO_MATCH:
“before use” (user-initiated) ≠ “on insert/automatically” (system behavior).

This kills a ton of “proxy means boundary filtering” and “scan before use means automatic scanning” errors without naming proxies or malware.

⸻

Tighten enforcement where the prompt already says the right thing

A) Make “permissive language” a hard blocker for MAPPED

Right now, you say reject “may/should,” but models still slip. Add an explicit line:

Hard Rule: If the evidence sentence contains may/might/can/should/recommended/encouraged/where applicable/as appropriate, it is inadmissible for MAPPED or PARTIAL (unless the same sentence also contains a binding verb that clearly makes the requirement mandatory—which is rare).

This directly addresses the “activity may be monitored” FP class.

B) Add a “Quote Sufficiency Test” to stop evidence piecing (even subconsciously)

Even with the single-sentence rule, models mentally combine context. Add:

Quote Sufficiency Test (mandatory before MAPPED/PARTIAL):
“Assume the policy contained only this sentence. Would the control still be satisfied without importing context from elsewhere?”
	•	If no → NO_MATCH (cite single-sentence rule / G-14 / G-16 depending on why)

This is surprisingly effective at stopping “clean desk + shredding + handling” ⇒ “privacy program controls.”

C) Consider narrowing IR-6 (Standard Reference) because it’s a precision trap

IR-6 is risky across arbitrary corpora because many policies say “align with ISO/NIST” without making specific requirements auditable.

A safer general rule:
	•	Only apply IR-6 if the policy mandates compliance and either
	•	includes the requirement text inline, or
	•	the referenced standard is incorporated by reference as binding requirements (explicitly stated).
Otherwise treat it as G-12.

You’ll lose a bit of recall on weakly written policies, but you’ll gain a lot of precision and audit defensibility.

⸻

Why this will generalize across any policy/control set

These changes don’t depend on:
	•	specific control IDs,
	•	specific technologies (proxy, IPS, AES),
	•	or the eval’s specific ground-truth quirks.

They encode stable abstractions:
	1.	Artifact identity matters (policy ≠ “the” policy).
	2.	Mechanism matters (behavioral/admin ≠ technical enforcement).
	3.	Operational qualifiers matter (presence/use ≠ configuration/management).
	4.	Program controls require explicit program artifacts (inputs ≠ programs).

Those abstractions hold across NIST/ISO/CIS/SOC2/custom control libraries and across policy types.

⸻

Quick note on the DCF-32 false negative

Without seeing the batch, the most common causes (given your strictness) are:
	•	The policy uses a synonym you did not whitelist in Pass B, so it fails the “anchor concept” test.
	•	The control has a hidden qualifier (scope/audience/lifecycle) that the model treats as mandatory and blocks (G-10/G-14), even though ground truth treated it as satisfied.

A good generalized fix (if that’s what happened) is expand Pass B’s synonym table in a controlled way, but only for true equivalences (e.g., “security incident” ↔ “information security event” if defined).

⸻

If you want something directly pasteable: I can rewrite your guardrail section with G-15/G-16/G-17, the G-2 enhancement, and the Quote Sufficiency Test, keeping your numbering/style consistent and avoiding topic-specific rules.