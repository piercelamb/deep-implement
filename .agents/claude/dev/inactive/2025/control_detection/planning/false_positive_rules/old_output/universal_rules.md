# Universal Failure Avoidance Rules

*16 rules*

## Reject Non-Binding Preamble, Intent, and Future Statements (0 examples)

**Pattern:** The LLM maps controls to high-level statements of intent, design, or applicability found in introductory sections (Purpose, Scope, Background) or future-tense commitments rather than binding operational mandates.

**Triggers:** `Purpose of this policy`, `Introduction`, `Objectives`, `Background`, `designed to`, `intended to`, `aims to ensure`, `Scope`, `Goal`, `will establish`, `commitment to`, `strives to`

**Block when:** Evidence is drawn from a preamble section (Purpose, Scope, Introduction, Background) OR describes the document's design/intent (e.g., 'aims to') OR uses future tense (e.g., 'will establish') rather than stating a current binding mandate.

**Allow when:** The text within the section contains explicit binding imperatives (e.g., 'shall', 'must') or specific definitions/objectives explicitly required by the control.

---

## Reject Illustrative Examples, Templates, and Placeholders (0 examples)

**Pattern:** The LLM cites content from Appendices, templates, placeholders, or illustrative lists (introduced by 'e.g.') as binding policy mandates.

**Triggers:** `Appendix`, `Example template`, `Placeholder`, `<`, `>`, `e.g.`, `for example`, `such as`, `sample`, `template`, `include`

**Block when:** Evidence is extracted from an 'Appendix', 'Template', or 'Example' section, contains placeholder syntax, OR is a subordinate example following 'e.g.'/'such as'.

**Allow when:** The specific appendix or template is explicitly referenced in the main policy body as a normative and binding attachment, or the text explicitly states the examples are mandatory.

---

## Block Cross-Document Pointers and References (0 examples)

**Pattern:** The LLM maps a control requiring specific definitions or procedures to a text that merely references another document (internal or external) as the authority without providing the content.

**Triggers:** `refer to`, `see the`, `consult the`, `defined in the`, `accordance with`, `policies includes`, `per the`, `outlined in`, `governed by`

**Block when:** Evidence relies on a pointer or citation to another document (e.g., 'Refer to X', 'defined in the Policy') without providing the specific criteria or procedures required by the control.

**Allow when:** The evidence explicitly summarizes the mandatory requirement or procedure alongside the reference.

---

## Reject Definitions and Glossary Entries (0 examples)

**Pattern:** The LLM treats definitions of terms or concepts in Glossaries or Appendices as binding operational mandates to implement controls related to those terms.

**Triggers:** `Glossary`, `Definitions`, `is defined as`, `means`, `Terminology`, `defined hereinafter`

**Block when:** Evidence is located in a 'Glossary' or 'Definitions' section, or follows the structure of a definition (Term + 'means'/'is defined as'), describing a concept rather than mandating a control action.

**Allow when:** The definition is part of a normative statement (e.g., 'must maintain X, defined as...') or explicitly contains binding verbs imposing a requirement.

---

## Block Broad Generalizations for Specific Technical Controls (0 examples)

**Pattern:** The LLM maps broad, high-level evidence (e.g., 'security measures', 'ISO compliance') to specific, granular control requirements (e.g., MFA, FIPS, Encryption).

**Triggers:** `security measures`, `appropriate controls`, `compliance with`, `ISO 27001`, `best practices`, `hardening`, `ensure`, `protect against`

**Block when:** Control requires a specific technical mechanism, tool, or granular process (e.g., MFA, FIPS) AND Evidence only provides a broad category, general goal, or high-level principle.

**Allow when:** Evidence explicitly mentions the specific technical mechanism, tool, or detailed process required by the control.

---

## Enforce Strict Scope and Asset Specificity (0 examples)

**Pattern:** The LLM maps evidence with a mismatched scope (e.g., Niche vs General, Endpoint vs Infrastructure, Production vs All) to the control requirement.

**Triggers:** `specific to`, `limited to`, `production systems`, `endpoint`, `workstation`, `AI Policy`, `Cloud Policy`, `only for`

**Block when:** Evidence scope (asset class, audience, environment) is narrower than or disjoint from Control scope (e.g., Niche vs General, Endpoint vs Infra, Production vs All).

**Allow when:** Control specifically targets the narrower scope found in evidence OR evidence explicitly states the subset represents the entire scope.

---

## Distinguish Physical from Logical Domains (0 examples)

**Pattern:** The LLM conflates physical security controls (doors, guards, facility access) with logical or network security controls (firewalls, authentication, encryption).

**Triggers:** `physical access`, `facility`, `premises`, `badge`, `door`, `logical access`, `network`, `password`, `encryption`

**Block when:** Control requires logical, network, or system-level controls AND Evidence refers to physical, facility, or environmental controls (or vice versa).

**Allow when:** Evidence explicitly links the physical control to the logical requirement (e.g., 'physical access to server room controls logical access').

---

## Block Vendor/Third-Party Obligations for Internal Controls (0 examples)

**Pattern:** The LLM uses contractual requirements for third parties (vendors/business associates) to satisfy operational controls for the organization's own internal assets or processes.

**Triggers:** `vendor`, `third-party`, `business associate`, `supplier`, `contract`, `agreement`, `external`

**Block when:** Control requires internal organizational action/governance AND Evidence refers to vendor obligation, contract stipulations, or external parties.

**Allow when:** Control explicitly governs Vendor Management, Third Party Risk, or the creation of external agreements.

---

## Distinguish User Behavior from System Enforcement (0 examples)

**Pattern:** The LLM maps user-facing behavioral prohibitions (e.g., 'users must not') to controls requiring system-level technical enforcement (e.g., 'system must prevent').

**Triggers:** `users must not`, `prohibited`, `manual`, `behavior`, `code of conduct`, `system must`, `prevent`, `block`, `configure`

**Block when:** Control requires technical enforcement, prevention, or system configuration AND Evidence relies on user behavioral rules, prohibitions, or manual actions.

**Allow when:** Evidence explicitly states the system enforces the control technically.

---

## Distinguish Oversight/Monitoring from Execution (0 examples)

**Pattern:** The LLM maps evidence of monitoring, auditing, or verifying a process (oversight) to a control requiring the actual execution of that process.

**Triggers:** `monitor`, `audit`, `review`, `verify`, `report on`, `log`, `track`, `oversight`

**Block when:** Evidence describes a process of monitoring, auditing, or verifying a responsibility (oversight) rather than the execution of the underlying security task required by the control.

**Allow when:** The control specifically requires the monitoring, logging, or auditing of that process.

---

## Enforce Lifecycle, Frequency, and Temporal Alignment (0 examples)

**Pattern:** The LLM maps evidence from the wrong lifecycle phase (Retention vs Creation) or frequency (Periodic vs Continuous) to the control.

**Triggers:** `retention`, `deletion`, `creation`, `periodic`, `continuous`, `annually`, `quarterly`, `backup`, `restore`

**Block when:** Control requires a specific lifecycle phase (e.g., creation) or frequency (e.g., continuous) AND Evidence refers to a different phase (e.g., retention) or frequency (e.g., annual).

**Allow when:** Evidence explicitly states the requirement applies to the control's specific lifecycle phase or frequency.

---

## Block Activity/Metric as Artifact Evidence (0 examples)

**Pattern:** The LLM infers the existence of a formal artifact (Plan, List) or mandate solely from a metric, KPI, or description of a dynamic activity.

**Triggers:** `track`, `monitor`, `percentage of`, `number of`, `metric`, `KPI`, `count`, `strategies in place`

**Block when:** Control requires a specific static artifact (e.g., 'Inventory', 'Plan') or mandate AND Evidence is a metric/KPI or describes performing a dynamic activity.

**Allow when:** Evidence explicitly mandates the creation, retention, or documentation of the specific artifact required by the control.

---

## Block Permissive, Advisory, and Conditional Language (0 examples)

**Pattern:** The LLM maps to evidence using permissive modals (should, may), conditional qualifiers (where possible), or text labeled as guidance.

**Triggers:** `should`, `may`, `recommended`, `where possible`, `if possible`, `suggested`, `best practices`, `guidance`

**Block when:** Evidence relies on permissive modals, conditional qualifiers, or is derived from non-binding guidance sections.

**Allow when:** The control requirement explicitly permits a risk-based approach or the modal is used in a restrictive phrase (e.g., 'may not').

---

## Distinguish Privacy/Legal Disclaimers from Security Operations (0 examples)

**Pattern:** The LLM maps requirements for operational security controls (monitoring, logging) to Privacy notices, Legal contracts, or Liability clauses.

**Triggers:** `subject to monitoring`, `privacy`, `consent`, `liability`, `legal`, `gdpr`, `no expectation of privacy`

**Block when:** Control requires Security/Operational technical control OR External disclosure AND Evidence refers to Privacy notices, Legal liability, or passive disclaimers.

**Allow when:** Evidence explicitly mandates the specific security operation or external disclosure required by the control.

---

## Require Explicit Negative Prohibitions (0 examples)

**Pattern:** The LLM infers a specific negative prohibition (e.g., 'must not use') from a positive mandate to use a secure technology or establish management procedures.

**Triggers:** `must not`, `prohibited`, `disabled`, `remove`, `prevent`, `use`, `ensure`

**Block when:** Control requires a negative constraint (preventing, disabling, removing) or strict exclusivity AND Evidence only mandates the usage of a secure alternative or existence of a process.

**Allow when:** Evidence explicitly states that the insecure option is disabled, prohibited, or that the secure option is the exclusive source.

---

## Enforce Compound and Disjunctive Logic (0 examples)

**Pattern:** The LLM maps evidence that only satisfies part of a compound requirement (A AND B) or treats a mandate as optional (A OR B).

**Triggers:** `and`, `including`, `both`, `or`, `either`, `as applicable`, `distinct`

**Block when:** Control imposes a compound requirement or lists multiple distinct scope items, but the evidence only addresses a subset OR presents the requirement as optional.

**Allow when:** Evidence uses a comprehensive umbrella term defined to explicitly include all missing items, or explicitly addresses all distinct components.

---
