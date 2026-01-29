# Rare Rules

**12 rules** (edge cases observed in single sources).

*These rules may represent policy-specific requirements or edge cases.*

## Rule 1: Apply Disjunctive Control Logic

**Source Policy Count:** 1

**Description:** The policy addresses at least one branch of a disjunctive control requirement using semantically equivalent language

**Evidence Type:** explicit_mandate
**Decision Effect:** supports_mapping

**Control Triggers:** `or`, `alternatively`, `mechanism to`, `ability to`, `opt-out`

**Policy Cues:** `appeal`, `contest`, `override`, `review request`, `challenge`

**Failure Pattern:** LLM failed to recognize a disjunctive ('OR') requirement in the control, rejecting the policy because it only addressed one of the valid options via a semantic equivalent.

**Recovery Heuristic:** If a control allows Alternative A OR Alternative B, and the policy explicitly mandates a synonym for Alternative B, this constitutes a match. Do not require the exact terminology of Alternative A.

**Dispute Categories:** PARTIAL

**Source Policies:** AI Governance Policy

---

## Rule 2: Context-Restricted Responsibility Recognition

**Source Policy Count:** 1

**Description:** LLM recognizes that domain-specific accountability satisfies the control requirement within that specific context.

**Evidence Type:** responsibility_assignment
**Decision Effect:** supports_mapping

**Control Triggers:** `Security Team`, `Steering Committee`, `Management Sponsor`, `Oversight`

**Policy Cues:** `is responsible for managing`, `assign management sponsors`, `ownership of this plan`

**Failure Pattern:** LLM rejected role assignment (Question 3) because the role's scope was limited to the document's domain (e.g., Incident Response) rather than the entire organization.

**Recovery Heuristic:** When a control requires a functional team (e.g., Security Team) and the policy is a domain-specific plan, accept role assignments designated to manage that specific plan as valid partial evidence.

**Dispute Categories:** PARTIAL

**Source Policies:** Incident Response Plan

---

## Rule 3: Recognize Management via Access Control

**Source Policy Count:** 1

**Description:** Policy restrictions on who can alter configuration imply a centrally managed state.

**Evidence Type:** responsibility_assignment
**Decision Effect:** supports_mapping

**Control Triggers:** `Centrally manage`, `Centralized control`, `Prevent disablement`

**Policy Cues:** `Restricted to authorized personnel`, `Prohibited from being disabled`, `Unless specifically authorized`

**Failure Pattern:** LLM rejected 'Central Management' because it looked for that exact phrase, missing that restricting configuration changes to authorized personnel functionally establishes central control. This is a Question 1 (Mandate) failure regarding implementation methods.

**Recovery Heuristic:** Recognize that restricting administrative/configuration rights to a specific authorized group is the functional definition of 'Central Management' in a policy context.

**Dispute Categories:** PARTIAL

**Source Policies:** Vulnerability Management Policy

---

## Rule 4: Infer Prohibition from Positive Assignment

**Source Policy Count:** 2

**Description:** Mapping accepted because positive requirement logically enforces negative prohibition.

**Evidence Type:** responsibility_assignment
**Decision Effect:** supports_mapping

**Control Triggers:** `prohibit`, `restrict`, `prevent`, `must not`

**Policy Cues:** `assign owner`, `restricted to`, `guarded by`, `approval required`

**Failure Pattern:** LLM rejected for missing an explicit prohibition (Question 2/4), failing to recognize that a positive mandate to assign ownership or restrict access implies that unowned/unauthorized states are prohibited.

**Recovery Heuristic:** Treat 'Must be X' as equivalent to 'Must not be Y'. If a policy states 'All assets must have an owner', it satisfies a control requiring 'Prohibit unowned assets'.

**Dispute Categories:** NO_MATCH, PARTIAL

**Source Policies:** Asset Management Policy, Data Protection Policy

---

## Rule 5: Prioritize Primary Audience Scope

**Source Policy Count:** 1

**Description:** Mapping is accepted based on primary workforce coverage even if auxiliary roles are not explicitly named.

**Evidence Type:** scope_definition
**Decision Effect:** supports_mapping

**Control Triggers:** `personnel`, `workforce`, `users`, `staff`, `all individuals`

**Policy Cues:** `employees`, `staff members`, `workers`, `associates`, `team members`

**Failure Pattern:** Question 2 (Scope) Failure: Rejecting a policy that covers the primary workforce (Employees) because it fails to explicitly list auxiliary roles (Contractors) mentioned in the control.

**Recovery Heuristic:** If the policy explicitly binds the primary entity (Employees), score as a Match or strong Partial; do not reject solely for missing auxiliary scope unless the control is exclusively about that auxiliary group.

**Dispute Categories:** PARTIAL

**Source Policies:** Code of Conduct

---

## Rule 6: Apply Parent Review Cycles to Child Requirements

**Source Policy Count:** 1

**Description:** The specific requirement exists within a container document that has a defined review schedule.

**Evidence Type:** frequency_timing
**Decision Effect:** supports_mapping

**Control Triggers:** `Periodically review`, `Review requirements`, `Update list`

**Policy Cues:** `Policy will be reviewed annually`, `Review to meet standards`

**Failure Pattern:** LLM failed to recognize that a mandate to review a document (Parent) constitutes a review of the specific requirements (Children) contained within it. This is a Question 3 (Ownership/Maintenance) failure.

**Recovery Heuristic:** If a control requires periodic review of a specific item (e.g., NDA requirements), and that item exists within a policy that has a mandated review cycle, the control is satisfied.

**Dispute Categories:** NO_MATCH

**Source Policies:** Information Security Policy

---

## Rule 7: Identify Constitutive Elements of Definitions

**Source Policy Count:** 2

**Description:** Mapping accepted because policy contains the definition of the term, if not the term itself.

**Evidence Type:** artifact_reference
**Decision Effect:** supports_mapping

**Control Triggers:** `non-repudiation`, `integrity`, `authenticity`

**Policy Cues:** `who performed it`, `user identity`, `event logs`, `audit trails`

**Failure Pattern:** LLM rejected because the exact industry term (e.g., 'Non-repudiation') was missing (Question 1), even though the policy mandated the component parts that define that term (e.g., logging 'who' and 'what').

**Recovery Heuristic:** Deconstruct the control term into its definitions (e.g., Non-repudiation = Identification + Attribution). If the policy mandates the components, accept the mapping as semantically equivalent.

**Dispute Categories:** NO_MATCH

**Source Policies:** Asset Management Policy, Data Protection Policy

---

## Rule 8: Validate External Standard References

**Source Policy Count:** 1

**Description:** Mapping accepted because specific config is inherited from referenced standard.

**Evidence Type:** standard_reference
**Decision Effect:** supports_mapping

**Control Triggers:** `configuration`, `settings`, `parameters`, `hardening`

**Policy Cues:** `industry-accepted standards`, `benchmarks`, `vendor recommendations`, `hardening standards`

**Failure Pattern:** LLM rejected for missing specific technical configurations (Question 1), failing to recognize that the policy mandated adherence to an external industry standard (e.g., CIS Benchmarks) that contains those configurations.

**Recovery Heuristic:** If a policy mandates adherence to a comprehensive external standard (CIS, NIST, ISO), assume standard configuration items (like DNS, Registry, Ports) are covered by that reference unless explicitly excluded.

**Dispute Categories:** NO_MATCH

**Source Policies:** Asset Management Policy

---

## Rule 9: Allow Onboarding Timing Equivalence

**Source Policy Count:** 1

**Description:** Mapping is accepted when action occurs at the immediate start of the relationship, even if control says 'before'.

**Evidence Type:** frequency_timing
**Decision Effect:** supports_mapping

**Control Triggers:** `prior to`, `before`, `pre-employment`, `pre-hire`, `in advance`

**Policy Cues:** `when they start`, `upon hire`, `during onboarding`, `commencement of employment`, `initial`

**Failure Pattern:** Strictly enforcing 'prior to' timing requirements against policy mandates that occur 'upon start', ignoring functional equivalence in risk mitigation.

**Recovery Heuristic:** If policy mandates action at the commencement of the relationship (onboarding), treat as satisfying pre-engagement control requirements unless the specific time gap creates critical unmitigated risk.

**Dispute Categories:** PARTIAL, NO_MATCH

**Source Policies:** Code of Conduct

---

## Rule 10: Exclude Artifact Demands from Policy

**Source Policy Count:** 1

**Description:** Mapping is accepted based on the activity mandate without requiring explicit text on artifact generation.

**Evidence Type:** artifact_reference
**Decision Effect:** supports_mapping

**Control Triggers:** `document`, `record`, `log`, `report`, `evidence`

**Policy Cues:** `shall test`, `shall perform`, `conduct`, `execute`, `carry out`

**Failure Pattern:** Framework Misapplication: Rejecting a policy mandate for a core activity (e.g., testing) because it does not explicitly require the generation of evidence/logs (artifacts).

**Recovery Heuristic:** Differentiate between the mandate to perform an action (Policy) and the requirement to document it (Evidence/Procedure). If the action is mandated, the artifact is implied.

**Dispute Categories:** PARTIAL, NO_MATCH

**Source Policies:** Disaster Recovery Plan

---

## Rule 11: Recognize Template Mandates

**Source Policy Count:** 1

**Description:** Recognition that the policy establishes the governance framework, even if specific values are templated.

**Evidence Type:** explicit_mandate
**Decision Effect:** supports_mapping

**Control Triggers:** `specific threshold values`, `defined risk levels`, `quantifiable limits`

**Policy Cues:** `placeholder text`, `variable brackets`, `template structures`, `binding language surrounding placeholders`

**Failure Pattern:** LLM incorrectly answers Question 1 (Mandate) by treating placeholder values (e.g., '<VALUE>') or variables as a lack of requirement, ignoring the binding framework surrounding them.

**Recovery Heuristic:** When policy contains placeholders for specific thresholds or values, evaluate the surrounding text. If the text mandates the *existence* and *definition* of these values, treat Question 1 as satisfied.

**Dispute Categories:** PARTIAL, NO_MATCH

**Source Policies:** Risk Assessment Policy

---

## Rule 12: Recognize Indirect Binding Mechanisms

**Source Policy Count:** 1

**Description:** Mapping is accepted when the binding mechanism legally enforces the control's intent, regardless of document title.

**Evidence Type:** explicit_mandate
**Decision Effect:** supports_mapping

**Control Triggers:** `agreement`, `contract`, `NDA`, `sign`, `commitment`

**Policy Cues:** `acknowledgment`, `certify compliance`, `agree to abide`, `terms of employment`, `code of conduct`

**Failure Pattern:** Question 1 (Mandate) Failure: Demanding a specific document title (e.g., NDA) while ignoring a binding acknowledgment of a parent policy containing the same obligations.

**Recovery Heuristic:** Verify if the policy establishes a binding obligation for the subject matter (e.g., confidentiality) through an aggregate mechanism (e.g., Code of Conduct acknowledgment) rather than looking for a specific instrument title.

**Dispute Categories:** PARTIAL, NO_MATCH

**Source Policies:** Code of Conduct

---
