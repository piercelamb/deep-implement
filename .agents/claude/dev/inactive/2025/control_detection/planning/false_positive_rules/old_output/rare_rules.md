# Rare Failure Avoidance Rules

*14 rules*

## Distinguish AI/Data Science from IT Security (0 examples)

**Pattern:** The LLM conflates AI-specific concepts (model drift, transparency, bias) with standard IT Security concepts (integrity, logging, access control).

**Triggers:** `model`, `drift`, `bias`, `transparency`, `training data`, `accuracy`, `explainability`

**Block when:** Control requires IT security, infrastructure, or standard operational controls AND Evidence refers to AI/ML model performance or data science metrics.

**Allow when:** Evidence explicitly links the AI concept to the required IT security infrastructure control.

---

## Distinguish Training from Operational Execution (0 examples)

**Pattern:** The LLM conflates the requirement to train personnel on a topic with the requirement to execute/implement that topic.

**Triggers:** `training`, `awareness`, `educate`, `understand`, `curriculum`, `knowledge`

**Block when:** Control requires execution of a process/control AND Evidence refers to training/awareness (or vice versa).

**Allow when:** Evidence explicitly mandates the execution of the process in addition to training.

---

## Block Prerequisite Inference (0 examples)

**Pattern:** The LLM assumes that because a system component or process (e.g., Deletion) is mentioned, the foundational controls for finding/identifying it must exist.

**Triggers:** `production`, `deletion`, `rectification`, `monitoring`

**Block when:** Control requires a proactive identification/discovery process (e.g., scanning, tagging) AND the evidence only describes reactive processes or states of existence.

**Allow when:** Evidence includes specific verbs related to identification (e.g., 'scan', 'discover', 'label', 'tag').

---

## Block Metadata Artifacts as Policy Evidence (0 examples)

**Pattern:** The LLM cites document metadata (e.g., a revision table) as evidence of a policy mandating document control procedures.

**Triggers:** `Revision History`, `Version`, `Document Control`, `Approved By`, `Date`

**Block when:** The evidence is a table header, footer, or metadata section describing the document's own history rather than a policy statement.

**Allow when:** The evidence is a complete sentence explicitly mandating the maintenance of document history or version control procedures.

---

## Enforce Specific Regulatory and Training Topics (0 examples)

**Pattern:** The LLM treats generic compliance or training goals as satisfying requirements for specific regulations (PCI DSS) or curriculum topics (phishing).

**Triggers:** `educate employees`, `compliance policies`, `data protection`, `training`, `relevant regulations`

**Block when:** Control requires specific regulations (e.g., PCI DSS) or specific curriculum topics AND Evidence only cites generic compliance or training goals.

**Allow when:** Evidence explicitly references the specific regulation, standard, or topic required by the control.

---

## Distinguish Resolution from Validation (0 examples)

**Pattern:** The LLM treats the requirement to verify, validate, or re-test a fix as a technical detail of the general mandate to resolve vulnerabilities.

**Triggers:** `resolve`, `remediate`, `fix`, `address vulnerabilities`

**Block when:** Control requires 'validation', 'verification', 're-scanning', or 're-testing' of a fix AND evidence only mandates the initial 'resolution' or 'remediation'.

**Allow when:** Evidence explicitly mandates post-remediation validation steps, follow-up scans, or verification workflows.

---

## Require Explicit Maintenance Mandates (0 examples)

**Pattern:** The LLM infers maintenance/configuration requirements (updates, signatures) from a mandate to simply 'use' or 'employ' a tool.

**Triggers:** `employ`, `use`, `utilize`, `must have`, `adoption`

**Block when:** Control requires specific maintenance actions (e.g., 'keep up-to-date') AND Policy only mandates the existence or usage of the tool.

**Allow when:** Policy includes maintenance keywords like 'maintain', 'update', 'current', 'patch', or 'lifecycle management'.

---

## Differentiate Notification from Remediation (0 examples)

**Pattern:** The LLM confuses external breach notification procedures with internal data spill discovery and remediation.

**Triggers:** `breach notification`, `assess harm`, `communicate to public`, `notify affected parties`

**Block when:** Control requires internal remediation/discovery of data AND Policy focuses on external notification, legal assessment, or public communication.

**Allow when:** Policy mentions 'containment', 'removal', 'scrubbing', 'secure deletion', or 'internal discovery' procedures.

---

## Enforce Strict Control Qualifiers (0 examples)

**Pattern:** The LLM ignores specific qualifiers in the control (e.g., 'Authenticated', 'Internal') and accepts generic evidence that is insufficient.

**Triggers:** `authenticated`, `internal`, `external`, `ASV`, `approved scanning vendor`

**Block when:** Control requirement contains a limiting qualifier (e.g., 'Authenticated', 'Internal') that is absent from the Evidence text.

**Allow when:** Evidence explicitly contains the qualifier, a direct synonym, or context that explicitly satisfies the specific scope.

---

## Enforce Exception Governance (0 examples)

**Pattern:** Control requires a primary rule AND a process for managing exceptions/bypasses, but evidence only states the primary rule.

**Triggers:** `bypass`, `exception`, `business justification`, `approval for`, `override`

**Block when:** Control requires a governance process for authorizing exceptions or bypasses, but Evidence only establishes the primary prohibition.

**Allow when:** Evidence explicitly describes the procedure for authorizing exceptions or explicitly states that no exceptions are permitted.

---

## Differentiate Asset Return from Access Revocation (0 examples)

**Pattern:** Evidence regarding the return of physical assets is mapped to controls requiring the disabling of logical access.

**Triggers:** `disable`, `deactivate`, `revoke`, `terminate access`, `remove access`

**Block when:** Evidence only mandates the 'return', 'collection', or 'surrender' of physical assets, hardware, or devices, while Control requires disabling logical access.

**Allow when:** Evidence explicitly mentions 'accounts', 'credentials', 'tokens', 'logins', or 'electronic access' being disabled or revoked.

---

## Distinguish NDA from Security Agreements (0 examples)

**Pattern:** Basic Non-Disclosure Agreement (NDA) mapped to controls requiring specific security, privacy, or data processing agreements.

**Triggers:** `security agreement`, `privacy agreement`, `data processing agreement`, `DPA`, `BAA`

**Block when:** Evidence relies solely on 'Non-Disclosure Agreement', 'NDA', or 'Confidentiality Agreement' while Control requires specific security/privacy agreements.

**Allow when:** Evidence explicitly states the agreement includes 'security controls', 'data protection standards', or 'privacy processing obligations'.

---

## Distinguish Responsibility from Access Control (0 examples)

**Pattern:** The LLM confuses the assignment of operational responsibility (who performs a task) with access control restrictions (who is allowed to view the data).

**Triggers:** `recorded by`, `stored by`, `reported by`, `responsibility`, `assigned to`

**Block when:** Control requires restricting read/write access to specific personnel. Evidence only designates which role performs the creation, recording, or maintenance tasks.

**Allow when:** Evidence explicitly states that access is limited/restricted to the designated role.

---

## Block Process Inputs as Mandates (0 examples)

**Pattern:** The LLM confuses a requirement to *consider* a factor (during requirements analysis) with a requirement to *implement* that factor.

**Triggers:** `identify requirements`, `factors`, `inputs`, `considerations`, `analysis`

**Block when:** The evidence mandates a process of identification, analysis, or selection where the control topic is listed merely as a potential method, factor, or input to be evaluated.

**Allow when:** The text explicitly mandates the implementation of the results of the analysis or requires the specific method be used.

---
