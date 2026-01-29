# Universal Failure Avoidance Rules

*20 rules*

## Block Administrative Substitutes for Technical Controls (857 examples)

**Pattern:** The LLM maps requirements for specific technical mechanisms, automated controls, or granular configurations to evidence describing administrative processes, manual reviews, high-level policies, or general security goals.

**Triggers:** `review`, `monitor`, `audit`, `policy`, `procedure`, `manual`, `ensure`, `verify`, `check`, `appropriate controls`, `security measures`, `best practices`, `minimize`, `protect against`

**Block when:** Control requires an automated, technical, system-enforced mechanism, or specific tool configuration AND Evidence describes a manual process, administrative review, policy document, or general high-level goal.

**Allow when:** Evidence explicitly mandates the specific technical mechanism, automated action, or tool required by the control.

---

## Enforce Physical, Logical, and Data Domain Boundaries (330 examples)

**Pattern:** The LLM conflates distinct security domains, mapping physical controls to logical requirements, infrastructure controls to data-layer requirements, or vice versa.

**Triggers:** `physical access`, `facility`, `premises`, `badge`, `door`, `logical access`, `network`, `firewall`, `data`, `information`, `media`, `hardware`, `infrastructure`

**Block when:** Control requires logical/system controls OR infrastructure configuration AND Evidence refers to physical/facility controls OR data-layer outcomes (or vice versa).

**Allow when:** Evidence explicitly links the physical/data control to the logical/infrastructure requirement requested.

---

## Enforce Lifecycle Phase and Temporal Alignment (301 examples)

**Pattern:** The LLM maps evidence from the wrong lifecycle phase (Retention vs Creation) or temporal trigger (Periodic vs Event-driven).

**Triggers:** `retention`, `deletion`, `stored for`, `kept for`, `periodic`, `annually`, `creation`, `provisioning`, `termination`, `lifecycle`, `ongoing`

**Block when:** Control requires a specific lifecycle phase (e.g., creation, immediate action) or trigger (e.g., event-based) AND Evidence refers to a different phase (e.g., retention, periodic review).

**Allow when:** Evidence explicitly states the requirement applies to the control's specific lifecycle phase or trigger.

---

## Block Scope Overreach and Context Mismatches (282 examples)

**Pattern:** The LLM maps evidence explicitly restricted to a specific subset (e.g., Production, AI, PCI, specific assets) to a control requiring organization-wide or general governance.

**Triggers:** `specific to`, `limited to`, `only for`, `production systems`, `AI Policy`, `PCI DSS`, `Cardholder Data`, `workstation`, `laptop`, `mobile device`, `remote access`, `clean desk`, `during testing`

**Block when:** Evidence is explicitly limited to a specific domain, asset subset, regulatory environment, or context (e.g., 'Production only', 'AI only') AND Control requires broad, organization-wide, or universal coverage.

**Allow when:** Control specifically targets the subset/context mentioned in the evidence OR Evidence explicitly states the subset represents the entire scope.

---

## Distinguish Privacy and Legal Mandates from Security Ops (250 examples)

**Pattern:** The LLM maps requirements for operational security controls to Privacy notices, Legal contracts, or passive liability disclaimers.

**Triggers:** `privacy`, `consent`, `gdpr`, `legal`, `contract`, `liability`, `subject to monitoring`, `no expectation of privacy`, `reserves the right`

**Block when:** Control requires Security/Operational technical control OR active monitoring AND Evidence refers to Privacy notices, Legal liability, or passive disclaimers.

**Allow when:** Evidence explicitly mandates the specific security operation or active monitoring required by the control.

---

## Distinguish Vendor Obligations from Internal Responsibilities (238 examples)

**Pattern:** The LLM confuses requirements for the organization to act with requirements for vendors/third-parties to act (or vice versa).

**Triggers:** `vendor`, `third-party`, `provider`, `business associate`, `supplier`, `contract`, `agreement`, `ensure`, `verify`

**Block when:** Control requires internal action/governance AND Evidence refers to vendor obligation (or vice versa).

**Allow when:** Evidence explicitly assigns the responsibility to the correct party required by the control.

---

## Block Definitions, Glossaries, and Scope Sections (198 examples)

**Pattern:** The LLM infers mandates from 'Scope', 'Purpose', or 'Definition' sections which only define applicability or terms, not requirements.

**Triggers:** `scope`, `purpose`, `applies to`, `defined as`, `means`, `glossary`, `terminology`, `introduction`, `overview`

**Block when:** Evidence is drawn from a Scope, Purpose, or Definition section describing concepts or applicability rather than mandating specific execution.

**Allow when:** Evidence contains imperative language (shall, must) explicitly mandating the specific requirement within that section.

---

## Block External References and Pointers (170 examples)

**Pattern:** The LLM maps controls to evidence that merely references an external document, standard, or policy as an authority without containing the actual requirement text.

**Triggers:** `refer to`, `see the`, `accordance with`, `defined in`, `outlined in`, `comply with`, `ISO 27001`, `per the`, `policies includes`, `related documents`, `governed by`

**Block when:** Evidence relies on a pointer, citation, or list of external documents/standards (e.g., 'Refer to X', 'Compliance with ISO') without providing the specific criteria or procedures required by the control.

**Allow when:** Evidence explicitly summarizes the mandatory requirement or procedure alongside the reference.

---

## Block Illustrative Examples and Placeholders (164 examples)

**Pattern:** The LLM treats optional examples, templates, or placeholders as binding mandates.

**Triggers:** `e.g.`, `for example`, `such as`, `include`, `<FREQUENCY>`, `[insert]`, `template`, `sample`, `appendix`

**Block when:** Evidence is an illustrative example (e.g., 'such as X'), a template placeholder, or a non-binding list item.

**Allow when:** Evidence explicitly states the examples are mandatory minimum requirements.

---

## Distinguish User Behavioral Rules from System Enforcement (139 examples)

**Pattern:** The LLM maps user-facing behavioral prohibitions to controls requiring system-level technical enforcement.

**Triggers:** `prohibited`, `must not`, `user responsibility`, `code of conduct`, `users must`, `manual`, `lock your workstation`

**Block when:** Control requires technical enforcement, prevention, or system configuration AND Evidence relies on user behavioral rules or prohibitions.

**Allow when:** Evidence explicitly states the system enforces the control technically.

---

## Enforce Audience and Role Specificity (113 examples)

**Pattern:** The LLM maps controls targeting a specific audience (e.g., Customer, Staff) to evidence governing a different, non-equivalent audience.

**Triggers:** `customer`, `client`, `staff`, `employee`, `provider`, `user`, `responsible for`, `recorded by`

**Block when:** Control targets a specific Audience/Role AND Evidence targets a different Audience/Role.

**Allow when:** Evidence explicitly states the provision applies to the required audience or defines the terms synonymously.

---

## Enforce Specific Technical Attributes (108 examples)

**Pattern:** The LLM maps generic mandates (e.g., 'enable logging') to controls requiring specific attributes, standards, or sub-processes.

**Triggers:** `logging`, `encryption`, `change management`, `audit trails`, `cryptography`, `FIPS`

**Block when:** Control requires specific attributes (e.g., log fields), standards (e.g., FIPS), or sub-processes AND Evidence only mandates the general category.

**Allow when:** Evidence explicitly mentions the specific attribute, standard, or detailed sub-process required.

---

## Distinguish AI/Data Science from IT Security (106 examples)

**Pattern:** The LLM conflates AI-specific concepts (model drift, bias) with standard IT Security concepts (integrity, logging).

**Triggers:** `model`, `drift`, `bias`, `transparency`, `training data`, `accuracy`, `algorithm`, `data science`

**Block when:** Control requires IT security, infrastructure, or standard operational controls AND Evidence refers to AI/ML model performance or governance.

**Allow when:** Evidence explicitly links the AI concept to the required IT security infrastructure control.

---

## Distinguish Training from Operational Execution (103 examples)

**Pattern:** The LLM conflates the requirement to train personnel on a topic with the requirement to execute/implement that topic.

**Triggers:** `training`, `awareness`, `educate`, `understand`, `curriculum`, `knowledge`, `compliance policies`

**Block when:** Control requires execution of a process/control AND Evidence refers to training/awareness (or vice versa).

**Allow when:** Evidence explicitly mandates the execution of the process in addition to training.

---

## Block Non-Binding, Permissive, and Future Language (75 examples)

**Pattern:** The LLM maps controls to evidence using permissive modals (should, may), future intent (will establish), or non-binding guidance.

**Triggers:** `should`, `may`, `recommended`, `suggested`, `optional`, `will establish`, `intended to`, `aims to`, `if possible`, `where applicable`

**Block when:** Evidence relies on permissive modals, future-tense commitments without content, or discretionary qualifiers (e.g., 'should', 'if possible').

**Allow when:** Control explicitly permits a guideline/recommendation OR the modal is used in a restrictive phrase (e.g., 'may not').

---

## Require Specific Documentation Artifacts (75 examples)

**Pattern:** The LLM infers the existence of a formal static artifact (Inventory, Plan, List) solely from a mandate to perform a related dynamic activity.

**Triggers:** `communicate`, `track`, `monitor`, `list of`, `inventory`, `plan`, `document control`, `policy`, `review`

**Block when:** Control requires a specific static artifact (e.g., 'Inventory', 'Plan', 'List') AND Evidence only describes performing a dynamic activity or general policy review.

**Allow when:** Evidence explicitly mandates the creation, retention, or documentation of the specific artifact required.

---

## Distinguish Operational Execution from Oversight (70 examples)

**Pattern:** The LLM maps evidence of monitoring, auditing, or verifying a process (oversight) to a control requiring the actual execution of that process.

**Triggers:** `monitor`, `report on`, `audit`, `log`, `track`, `metrics`, `KPI`, `oversight`

**Block when:** Control requires Operational/Execution action AND Evidence describes a process of monitoring, auditing, or verifying (oversight).

**Allow when:** Control specifically requires the monitoring, logging, or auditing of that process.

---

## Distinguish Risk Assessment from Control Implementation (69 examples)

**Pattern:** The LLM maps controls requiring active remediation or technical verification to policies describing risk assessment or prioritization workflows.

**Triggers:** `risk evaluation`, `risk prioritization`, `risk assessment`, `identify threats`, `factors`, `considerations`

**Block when:** Control requires specific preventative or detective technical actions BUT Evidence only describes the administrative process of identifying or evaluating risks.

**Allow when:** Policy explicitly mandates the specific technical activity as a required step within the risk management process.

---

## Block Technical State as Governance Evidence (68 examples)

**Pattern:** The LLM accepts a statement of technical configuration or status as evidence of underlying management processes or governance.

**Triggers:** `is encrypted`, `configured to`, `default`, `must meet requirements`, `management system`, `effectiveness`

**Block when:** Control requires 'Policy', 'Governance', or 'Management Process' AND Evidence only states a technical configuration status or outcome.

**Allow when:** Evidence explicitly details the procedural management or governance framing for the control.

---

## Enforce Compound and Negative Logic (43 examples)

**Pattern:** The LLM fails to enforce compound requirements (AND), allows optional alternatives (OR), or infers prohibitions from positive mandates.

**Triggers:** `and`, `including`, `or`, `alternatively`, `must support`, `approved`, `minimize`, `reasonably necessary`

**Block when:** Control requires a compound (AND) requirement, strict prohibition, or specific constraint AND Evidence provides only a subset, an optional alternative, or a general principle.

**Allow when:** Evidence explicitly addresses all distinct components, prohibits the specific item, or mandates the strict requirement.

---
