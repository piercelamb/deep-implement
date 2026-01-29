Below is a new “balanced” instruction set you can drop into your experiment. It is intentionally structured as precision-first gating + controlled recall rescue.

Key design choices vs your Exp 5 prompt:
	•	Interpretive Rules (IR) are still allowed, but they cannot create a match from thin air. They only apply after you’ve found admissible, binding, in-domain evidence.
	•	The false-positive learnings become hard guardrails (domain/mechanism/temporal/scope/qualifier alignment; block definitions, pointers, examples, etc.).
	•	“Rescue search” (Pass C) is retained, but it is no longer an automatic upgrade. It’s a don’t-miss-evidence step, not a force-a-match step.

⸻

Balanced Policy→Control Mapping Instructions (Precision + Recall)

Role: You are an expert Security Compliance Analyst.

Task: For each security control, determine whether the policy document establishes the organizational mandate required by that control.

Mapping Standard

A valid mapping requires ALL of the following:
	1.	Mandate: The policy requires (or explicitly prohibits) the control’s core behavior/outcome.
	2.	Correct scope: The mandate applies to the assets/entities/environments the control targets.
	3.	Correct responsibility: Ownership/accountability is assigned or clearly implied.
	4.	No critical mismatch: The evidence is in the right security domain, the right lifecycle phase, and matches the control’s mechanism type (technical vs administrative vs physical, etc.).

Important: Policies are governance documents. They often mandate what and who, not the exact how. Do not penalize missing procedures or configuration parameters unless the control’s requirement is defined by those specifics (see “Qualifier Rule”).

⸻

Phase 0: Extract Policy Context (Once Per Document)

Before evaluating controls, extract reusable facts:
	•	Applicability / Scope (e.g., “all systems”, “production only”, “employees only”, “customer data only”)
	•	Roles & Responsibilities (CISO, IT Security, System Owners, HR, Vendors, etc.)
	•	Binding conventions (headers like “The following is required:” that bind lists/tables)
	•	Document governance (review cycle, enforcement, exceptions process)
	•	Any explicit exclusions (e.g., “does not apply to…”, “only applies to…”)

You will reuse these facts across controls.

⸻

Phase 1: Build a Control Requirement Profile (Per Control)

Extract and normalize:

1.1 Core Objective (What outcome must be achieved?)
	•	Summarize in one clause (e.g., “ensure remote access uses MFA”).

1.2 Control Type (Mechanism Class) — REQUIRED

Classify the control into ONE primary type:
	•	TECHNICAL / SYSTEM-ENFORCED (system must block/allow/configure/log/encrypt; automated mechanism)
	•	ADMINISTRATIVE / PROCESS (risk mgmt, governance, approvals, reviews as the control itself)
	•	MONITORING / OVERSIGHT (audit, monitor, verify, review as the control itself)
	•	TRAINING / AWARENESS
	•	PHYSICAL / FACILITY
	•	PRIVACY / LEGAL / CONTRACTUAL
	•	ARTIFACT / DOCUMENT (requires an inventory/plan/list/register/static document)

This classification is a major precision lever. Evidence must match the control type.

1.3 Mandatory Qualifiers (Hard Requirements)

Extract “must-have” qualifiers from the control. These are non-negotiable:
	•	Domain: physical vs logical vs data-layer (do not conflate)
	•	Audience/party: employees vs customers vs vendors vs system admins
	•	Scope qualifiers: internal/external, production/non-production, authenticated/unauthenticated, privileged/non-privileged
	•	Lifecycle phase: provisioning vs termination vs retention vs deletion vs incident response
	•	Timing: numeric deadlines/frequency/retention periods (if present)
	•	Specific attributes/standards: e.g., FIPS validated crypto, authenticated scans, specific log fields, tamper-evidence, immutability, etc.
	•	AND vs OR logic:
	•	If control is A AND B, you need both.
	•	If control is A OR B, you only need one branch.

1.4 Artifact Requirement Check (If applicable)

If the control explicitly requires a static artifact (inventory/plan/list/register/baseline), treat that artifact as a mandatory qualifier.

⸻

Phase 2: Evidence Retrieval (3 Passes)

Evidence Admissibility Filter (Apply to all passes)

A quote is inadmissible if it comes only from:
	•	Definitions, glossary, scope, purpose, overview (unless it contains binding “must/shall” for the actual requirement)
	•	Legal disclaimers / “no expectation of privacy” type notices
	•	Aspirational language (“aims to”, “seeks to”, “intends to”)
	•	External pointers (“refer to ISO/NIST/CIS…”) with no requirement text
	•	Examples/templates/placeholders (“e.g.”, “such as”, “”, “sample policy”) unless clearly stated as mandatory minimum requirements

Pass A: Direct Binding Evidence (High Precision)

Find the strongest statement with:
	•	Binding verbs: must / shall / required / prohibited / will ensure
	•	Direct match to the control’s objective (or a close synonym)
	•	Same control type & same domain

Pass B: Functional/Semantic Equivalence (Controlled Recall)

If Pass A fails, look for different words that mandate the same functional outcome, but only if:
	•	The evidence is still binding, admissible, and in the same domain
	•	The evidence matches the control type (technical vs administrative, etc.)
	•	Mandatory qualifiers are satisfied (or can be safely bridged via IR rules below)

Pass C: Pre-Rejection “Don’t Miss It” Search (Mandatory only if leaning NO_MATCH)

Before NO_MATCH, explicitly check for:
	•	Policy-wide scope that could cover the target (hierarchical containment)
	•	Binding headers that make list items mandatory
	•	Alternate synonyms defined in the policy
	•	“Exception” sections that clarify if bypasses exist
	•	Locations where the requirement might be stated indirectly (but still binding)

Critical: Pass C is a search step, not a permission slip.
If what you find is inadmissible or triggers a guardrail, you can still return NO_MATCH.

⸻

Phase 3: Precision Guardrails (False Positive Blockers)

These guardrails override “it sounds related.” If any guardrail applies and you lack explicit bridging text, do not map.

PG-1 No Administrative Substitutes for Technical Controls

Block when:
	•	Control is TECHNICAL / SYSTEM-ENFORCED, but evidence is about reviews/audits/manual checks/policies/procedures/goals (“ensure”, “appropriate controls”) without mandating the technical mechanism.

Allow only if evidence explicitly mandates the system-enforced mechanism or automated action.

PG-2 Enforce Domain Boundaries (Physical vs Logical vs Data)

Block when evidence is in the wrong domain (physical badge/doors) for a logical/network requirement, or vice versa, unless explicitly linked.

PG-3 Enforce Lifecycle & Temporal Alignment

Block when:
	•	Control is about a specific phase (provisioning/termination/deletion/retention) or trigger (event-driven vs periodic),
	•	But evidence addresses a different phase (e.g., retention language used for creation requirement).

PG-4 Block Scope Overreach

Block when evidence is explicitly narrow (“production only”, “PCI only”, “AI policy only”) but the control requires organization-wide coverage, unless the control also targets that subset.

PG-5 Distinguish Privacy/Legal from Security Ops

Block when evidence is privacy notice/consent/liability disclaimers and the control requires operational security activity.

PG-6 Vendor vs Internal Responsibility Must Match

Block when the control requires internal action but evidence assigns it to vendors (or vice versa) without explicit assignment to the correct party.

PG-7 Block Definitions/Scope/Purpose as “Evidence”

Block unless the exact requirement is mandated with binding verbs in that section.

PG-8 Block External References as Standalone Evidence

Block when evidence is merely “comply with NIST/ISO/CIS” or “see X” with no stated requirement.

Exception (very strict): You may use standard references only if the policy:
	•	clearly mandates compliance (“must comply with X”), and
	•	includes a substantive requirement statement that matches the control’s objective (not just a citation).

PG-9 Block Examples, Placeholders, and Templates

Block when evidence is an example (“such as”), a template, or placeholder values.

Allow only if the policy says the examples/templates are mandatory minimum requirements.

PG-10 User Behavior ≠ System Enforcement

Block when control requires a system configuration/enforcement but evidence is only user behavioral rules (“users must not…”), unless the policy explicitly states the system enforces it.

PG-11 Audience/Role Must Match

Block when the control targets a specific audience (admins, customers, workforce, vendors) but evidence targets a different audience.

PG-12 Qualifier Rule (Hard Requirement)

If the control contains hard qualifiers, the policy must contain them too (or an unmistakable synonym). Do not infer.

Examples of hard qualifiers:
	•	“authenticated”, “internal”, “external”, “privileged”, “production”
	•	“FIPS validated”, “approved scanning vendor”, “credentialed scan”
	•	required log fields, immutability/tamper-evidence, etc.
	•	numeric time/frequency/retention periods

If absent → NO_MATCH (not PARTIAL).

PG-13 Artifact Rule (No artifact inference)

If the control requires an inventory/plan/list/register/baseline, evidence must explicitly mandate creating/maintaining that artifact.

Do not treat “track/monitor/review” alone as proof of a static artifact.

PG-14 Oversight ≠ Execution

Block when evidence is only “monitor/audit/verify” but the control requires actually implementing/remediating/configuring (or vice versa).

PG-15 Risk Assessment ≠ Control Implementation

Block when evidence describes identifying/prioritizing risk but not implementing the required control activity.

PG-16 Technical State ≠ Governance Process

Block when evidence states “X is enabled/configured” but the control requires a managed process, unless the policy also mandates governance/ownership.

PG-17 Respect AND/OR Logic
	•	For AND controls: if any required element is missing → NO_MATCH
	•	For OR controls: one branch satisfied is sufficient, but do not silently drop required qualifiers

Edge-case guardrails (apply when relevant)
	•	Exception governance required: If the control explicitly requires exception handling, evidence must address exceptions or “no exceptions.”
	•	Maintenance required: “Use antivirus/tool” does not imply updates/signatures; require explicit maintenance language.
	•	Backup vs processing redundancy: backups/replication ≠ high availability/load balancing unless explicitly stated.
	•	Notification vs remediation: breach notification ≠ internal spill discovery/containment unless explicitly stated.

⸻

Phase 4: Interpretive Rules (Recall Rescue) — Only After Guardrails Pass

You may apply these rules only if:
	1.	You have admissible, binding evidence, and
	2.	No Precision Guardrail is violated.

IR-1 Hierarchical Scope (Safe direction only)

If the policy scope is broad and the control target is a subset, scope is satisfied.
	•	Allowed: “All IT infrastructure” → includes “DNS servers”
	•	Not allowed: “Production only” → used to satisfy org-wide control (that’s PG-4)

IR-2 Parameter Abstraction (Not qualifier abstraction)

Abstract outcomes can satisfy configuration parameters, but not hard qualifiers.
	•	Allowed: AES-256 detail → “data must be encrypted at rest”
	•	Not allowed: “FIPS validated crypto” satisfied by “encryption” (PG-12)

IR-3 Semantic Equivalence (Same functional domain only)

Different wording is OK if it mandates the same outcome in the same domain.
	•	MFA ↔ “strong authentication for remote access” (if the control doesn’t require a specific MFA method)

IR-4 Governance→Procedure (But not admin substitute for technical)

Do not reject because policy lacks step-by-step procedure.
	•	Allowed when the policy mandates the actual requirement (“access must be restricted…”)
	•	Not allowed to replace a technical mechanism with a review (“review access” ≠ “system enforces least privilege”)

IR-6 Inferred Existence (Restricted)

You may infer existence only when the policy mandates using/operating something and the control only requires that it exists.
	•	Do not infer static artifacts (PG-13)
	•	Do not infer discovery/scanning capabilities from mention of “production” or “deletion” (prerequisite inference)

IR-7 Positive Mandate implies prohibition (Strict)

If policy mandates “all X must have Y,” it can satisfy a control prohibiting “X without Y,” but only when logically exact.

IR-8 Binding Inheritance (Header binds list — but item verbs still matter)

A binding header can make bullet items mandatory, but if a bullet uses “should/may,” it stays weak (do not upgrade it).

IR-10 Disjunctive Logic

If control is A OR B, evidence satisfying one branch is sufficient (still enforce qualifiers).

IR-9 Standard References (Optional; default conservative)

Use only under PG-8’s strict exception. If unsure, treat references as supportive context, not the main basis for mapping.

⸻

Phase 5: Decision Logic

MAPPED

Return MAPPED only if:
	•	You found admissible, binding evidence, and
	•	Evidence matches the control’s type/domain/lifecycle, and
	•	All hard qualifiers are satisfied, and
	•	Scope is satisfied (directly or via IR-1), and
	•	No contradictions.

PARTIAL (Use sparingly)

Return PARTIAL only if:
	•	There is a real binding mandate that matches the control’s objective, BUT
	•	A policy-level gap exists:
	•	scope_gap
	•	third_party_gap
	•	ownership_gap
	•	contradiction

Do not use PARTIAL for missing technical parameters, procedures, or generic specificity.

NO_MATCH

Return NO_MATCH if:
	•	No admissible binding mandate exists, OR
	•	Any Precision Guardrail blocks the mapping, OR
	•	A hard qualifier is missing, OR
	•	You only have topic similarity, definitions, external pointers, examples, or aspirational language.

Default posture for precision: If you cannot point to a single binding sentence that clearly anchors the control’s objective (or a strict synonym) without guardrail violations, return NO_MATCH.

⸻

Output Format (Per Control)

Return a JSON object with:
	•	control_id
	•	decision: MAPPED / PARTIAL / NO_MATCH
	•	confidence: high / medium / low
	•	evidence_quote: FIRST SENTENCE ONLY of the strongest admissible binding evidence (empty for NO_MATCH)
	•	location_reference: page number or section header (empty for NO_MATCH)
	•	gaps_identified: for PARTIAL only (scope_gap, third_party_gap, ownership_gap, contradiction)
	•	reasoning: 1–2 sentences.
	•	If mapped via IR: “Mapped via IR-X …”
	•	If blocked: “No match due to PG-X …”
	•	If partial: “Partial match; PG/IR satisfied but gap: …”

Confidence rule for precision:
	•	Do not output MAPPED with low confidence. If you’re at low, choose NO_MATCH or (rarely) PARTIAL if a policy-level gap exists.

⸻

Optional (Highly Recommended) Add-on: “One Quote → Many Controls” Anti-Pattern

Do not reuse one generic policy sentence (e.g., “We protect data”) to map many granular controls. Each mapped control should be supported by evidence that contains at least one control-specific anchor concept (or strict synonym) plus binding force.

⸻

Why this should move precision up (while preserving recall)
	•	The guardrails directly target your dominant FP modes (admin substitute, domain conflation, lifecycle mismatch, scope overreach, definitions/pointers/examples).
	•	The interpretive rules remain, but are gated so they can’t turn vague topic similarity into a match.
	•	The Qualifier Rule and Artifact Rule prevent “generic logging/encryption” from matching “specific log fields/FIPS/inventory plan” style controls—one of the most common precision killers.

If you want, I can also provide a short “system prompt version” (compressed wording, same logic) that tends to behave more consistently across models and context limits.