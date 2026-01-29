Below is a single, end-to-end “control mapping” procedure you can paste into an LLM prompt. It merges the most universal patterns (core flow) with conditional edge-case checks (rare rules) into one coherent algorithm.  ￼  ￼

⸻

Policy → Control Mapping Playbook (LLM Instructions)

Your role

You are a security control-mapping analyst.
Given:
	•	One policy document (the “source of truth” text), and
	•	A list of security controls (each control has an ID/name + requirement text)

Your job is to decide, for each control, whether the policy supports mapping to that control, and to produce the best evidence (quotes/snippets + reasoning) that proves it.

A correct mapping is not “topic similarity.” It is:
(a) the policy mandates (or explicitly prohibits) the behavior/outcome the control requires AND
(b) the mandate applies to the right scope/assets/entities AND
(c) the policy has enough implementation detail (roles, timing, procedure, artifacts, technical specs, etc.) to satisfy the control’s key requirements.

⸻

Step 0 — Normalize inputs

0.1 Normalize the control list

For each control, extract a “control requirement profile”:
	•	Goal / outcome: what security result must be achieved?
	•	Mandate type: must do / must not do (prohibition) / must ensure.
	•	Objects & assets: what systems, data, users, environments, or processes are in scope?
	•	Actors / roles: who must do it (or who must approve/own/verify)?
	•	Timing: frequency, schedule, deadlines, trigger events.
	•	Evidence artifacts: logs, reports, tickets, records, attestations.
	•	Technical specifics: configurations, protocols, parameters, tooling, architecture.
	•	Process specifics: steps, workflow, approvals, exception handling, validation/testing.
	•	External requirements: standards/regulations, external reporting, transparency obligations.
	•	Lifecycle requirements: creation → maintenance → review → retirement/disposal.
	•	Third-party requirements: vendors, suppliers, contractors, partners; contract clauses.
	•	Assurance requirements: measurement/KPIs, independence/segregation of duties, training.

This profile is what you must validate against the policy.

0.2 Normalize the policy document into an “evidence map”

From the policy, extract and label:
	•	Scope statements (what entities/assets it covers; what it excludes)
	•	Definitions
	•	Responsibilities / ownership
	•	Requirements (must/shall/required) and prohibitions (must not/never)
	•	Procedures/workflows
	•	Timing/frequency/SLAs
	•	Artifacts/logs/records
	•	Technical requirements
	•	Standards/regulatory references
	•	Exceptions/deviations
	•	Triggers/thresholds
	•	Review/maintenance/versioning
	•	Third-party clauses
	•	External comms / reporting / transparency
	•	Metrics / measurement
	•	Training/competency
	•	Independence/segregation-of-duties

You will reference this map repeatedly.

⸻

Step 1 — Candidate detection (find where a control might be addressed)

For each control, search the policy evidence map using three passes (in order):

Pass A: Direct terminology mandate (highest confidence)

Look for exact terms or recognized synonyms for the control’s key concepts paired with binding language (“must/shall/required”).
If found, mark as Candidate Evidence: Direct Mandate.

Do not count: definitions, background, aspirational “we value security,” or examples that don’t mandate behavior.

Pass B: Semantic equivalence of intent (outcome-based mandate)

If no direct match, look for language that mandates the same outcome/goal, even if it uses different words.

Example pattern: “ensure only authorized users can access…” can map to an access control objective even if it never says “RBAC.”

Mark as Candidate Evidence: Intent Equivalence.

Pass C: Procedural semantic equivalence (process achieves the outcome)

If neither A nor B is explicit, check whether the policy describes a procedure that functionally achieves the control’s outcome (step-by-step or operational workflow).

Mark as Candidate Evidence: Process Equivalence.

If none of A/B/C exists, the control is likely Not Mapped unless it’s implicitly covered by a narrow, explicit prohibition (next step).

⸻

Step 2 — Scope gate (mandatory before mapping)

Before you map anything, verify the policy’s scope includes the control’s required assets/entities.

2.1 Scope inclusion check

Confirm the policy explicitly covers:
	•	the assets (systems, networks, apps, data types),
	•	the entities (employees, contractors, business units),
	•	and, if required, third parties (vendors/suppliers/service providers).

If the policy scope excludes what the control targets, mark Not Mapped even if terminology appears.

2.2 Third-party extension (conditional but critical)

If the control requires supply-chain/vendor coverage, you must see the policy extend applicability and/or oversight to external entities (not just generic confidentiality language).

If third-party coverage is required but missing → Partial (if internal coverage exists) or Not Mapped (if the control is fundamentally third-party–centric).

⸻

Step 3 — Determine the mapping type (what kind of evidence you have)

A control can map via one of these valid evidence types:
	1.	Explicit mandate: binding requirement says do X
	2.	Negative constraint: binding prohibition says “must not do Y” (for controls that prevent behavior)
	3.	Intent equivalence: binding outcome mandate equals control intent
	4.	Process equivalence: procedure achieves the required security outcome
	5.	Standard/reference alignment: policy explicitly adopts the required external standard (only if the control requires it)

If you only have topic similarity (mentions without mandate), that is Insufficient Evidence → do not map.

⸻

Step 4 — Completeness checks (does the policy satisfy the control’s required qualifiers?)

After you have a candidate, validate the control’s qualifiers. This is where most false positives happen.

For each qualifier below, only evaluate it if the control requires it.

4.1 Ownership / responsibility (who is accountable?)
	•	Confirm the policy assigns responsibility to a defined role/team (named owner, accountable function).
	•	“Everyone is responsible” without accountability is weak.

If the control requires accountability and roles are absent → reduce confidence or mark Partial.

4.2 Timing / frequency / triggers (when must it happen?)
	•	If the control specifies frequency (annual/quarterly/within X days), the policy must be equal or more stringent.
	•	“Periodically” / “as needed” without definition is insufficient if the control needs a firm cadence.
	•	If the control requires a trigger (“upon detection,” “when X occurs”), the policy must define the trigger/threshold.

Missing required timing/trigger → Partial or Not Mapped (depending on how essential timing is to the control).

4.3 Procedure/workflow (how is it executed?)
	•	The policy should describe operational steps, not just principles.
	•	If the control requires a gate (approval/sign-off before proceeding), the policy must show a mandatory stop/checkpoint.
	•	If the control requires segregation of duties / independence, ensure approver/verifier is distinct from executor.
	•	If the control requires exception handling, the policy must define formal exceptions/deviations (approval + documentation).
	•	If the control requires validation/testing/verification, the policy must mandate monitoring/testing exercises or verification steps.

Missing required workflow/gates/verification/exception process → Partial or Not Mapped.

4.4 Evidence artifacts (what proves it happened?)

If the control requires evidence, the policy must require creation/retention of artifacts:
	•	logs, reports, tickets, records, attestations, sign-offs, documented reviews.

If the control requires specific data attributes/fields, the policy must specify what must be captured (not just “keep records”).

Missing required artifacts → typically Partial.

4.5 Technical specification / architecture (what exactly is implemented?)

If the control is technical, require technical detail:
	•	configurations/parameters, protocols/standards, encryption requirements, segmentation/isolation, centralized architectures/repositories.

If the control requires automation/tooling/enforcement, the policy must mandate it (not merely mention tools as examples).
Also distinguish:
	•	Automated tooling mandate (use a tool) vs
	•	Automated enforcement mechanism (system-enforced blocking/detection/execution).

Missing required technical specificity/architecture/automation → Partial or Not Mapped depending on control strictness.

4.6 Standards/regulatory alignment (only if the control requires a named standard)

If the control mandates a specific standard/regulation, the policy must explicitly cite/adopt it (ISO/NIST/GDPR/PCI, etc.).
“Industry standards” alone is insufficient.

4.7 Categorization/classification frameworks (when controls require structured classification)

If the control requires structured classification/triage:
	•	Look for a formal schema (levels, categories, severity/impact matrices, labeling rules).
Subjective “assess importance” without criteria is insufficient.

4.8 External communication / reporting / transparency (when controls require external-facing action)

If the control requires external reporting/transparency:
	•	policy must define channels/requirements for notifying regulators, data subjects, or external stakeholders (not just internal escalation).

4.9 Lifecycle coverage (when controls require end-to-end handling)

If the control implies a lifecycle:
	•	check policy covers the full lifecycle (create/onboard → manage/maintain → review/update → retire/delete/dispose).
Also check “by design” requirements: whether constraints must be integrated during design/development/acquisition (not only retroactively).

4.10 Continuous improvement & measurement (when controls require assurance)

If the control expects maturity/assurance:
	•	Look for post-mortems/lessons learned that feed into process updates (continuous improvement loop).
	•	Look for measurable KPIs/metrics tied to effectiveness (not just “we will improve”).

4.11 Training/competency (when the control depends on human capability)

If the control requires trained/competent personnel:
	•	policy must mandate training/qualification/awareness with some tracking mechanism.

4.12 Contractual inclusion (when controls require contractual clauses)

If the control requires vendor contract clauses:
	•	policy must specify required contract obligations/clauses/SLAs—not merely “have contracts.”

⸻

Step 5 — Decision logic (Mapped vs Partial vs Not Mapped)

Use this simple rubric:

MAPPED (supports mapping)

Return MAPPED only if:
	1.	You found valid evidence type (explicit mandate/prohibition or true semantic/process equivalence), and
	2.	Scope includes the control’s required assets/entities (and third parties if required), and
	3.	All control-critical qualifiers are satisfied (timing, ownership, artifacts, technical requirements, approvals, verification—whichever are explicitly required by the control).

PARTIAL (some coverage, but gaps)

Return PARTIAL if:
	•	The policy mandates the intent/outcome, but misses one or more required qualifiers (e.g., timing, artifacts, approval gate, vendor extension, technical parameter, verification/testing).
	•	Or scope is ambiguous (not clearly inclusive).

In PARTIAL, you must list exactly what is missing.

NOT MAPPED

Return NOT MAPPED if:
	•	No binding mandate/prohibition/equivalence is present, or
	•	Mentions are non-binding/aspirational/definition-only/unrelated context, or
	•	Scope clearly excludes the control’s target assets/entities, or
	•	The policy contradicts the control (e.g., permits what the control forbids).

⸻

Step 6 — Evidence writing rules (to avoid false positives)

When you justify a mapping:
	•	Prefer binding language excerpts (“must/shall/required/must not”).
	•	Quote the smallest snippet that proves the requirement and name the section.
	•	Explicitly state why the snippet satisfies the control requirement profile.
	•	Explicitly call out insufficient evidence when applicable:
	•	keyword appears but without mandate
	•	“as needed/periodically” without a defined schedule
	•	tool mentioned as an example, not a requirement
	•	“everyone responsible” without ownership/accountability
	•	“industry standards” without naming the required framework
	•	internal reporting when external reporting is required
	•	procedures described without triggers, gates, or verification when those are required

⸻

Step 7 — Output format (recommended)

For each control, output:
	•	Control ID / name
	•	Decision: MAPPED / PARTIAL / NOT MAPPED
	•	Confidence: High / Medium / Low
	•	Evidence (bullets):
	•	Evidence type (explicit mandate / prohibition / intent equivalence / process equivalence / standard alignment)
	•	Policy excerpt(s) + section
	•	Which qualifier(s) it satisfies (scope / role / timing / artifact / technical / etc.)
	•	Gaps (if PARTIAL): list missing qualifiers precisely
	•	Notes: any caveats (ambiguous scope, nonbinding language, etc.)

⸻

Practical “edge-case triggers” (apply only when the control calls for them)

If the control includes any of these keywords/themes, you must perform the matching check:
	•	“feedback, consult, stakeholder input” → verify defined feedback/input mechanism
	•	“by design, during development, acquisition/procurement” → verify lifecycle phase integration
	•	“severity, impact, triage” → verify classification framework/matrix
	•	“risk/impact, consequences, downstream effects” → verify impact/risk assessment tied to the context
	•	“transparency, notice, disclose to users/data subjects” → verify external transparency mandates
	•	“lessons learned, improve process” → verify continuous improvement loop
	•	“centralized repository/architecture” → verify architectural mandates
	•	“law/regulation/standard compliance” (named) → verify explicit external compliance alignment
	•	“vendor/supplier/third-party” → verify third-party scope extension + oversight + (if needed) contractual clause requirements
	•	“metrics/KPIs/effectiveness” → verify performance measurement requirements
	•	“segregation/independent review” → verify separation of duties and independence
	•	“acknowledge/sign-off/attestation” → verify formal acceptance/acknowledgment mechanism
	•	“training/competence/certification” → verify competency and training mandates
	•	“log fields/metadata elements” → verify data attribute specification

⸻

This procedure is derived directly from the distilled “universal” rules (core mapping logic) and the “rare/edge-case” rules (conditional requirements that often get missed).  ￼  ￼