# Universal Rules

**11 rules** distilled from 22 template policies.

*Rules are sorted by number of source policies (most universal first).*

## Rule 1: Verify Hierarchical Scope Inheritance

**Source Policy Count:** 9

**Description:** Policy scope definition encompasses the specific control subject as a subset

**Evidence Type:** scope_definition
**Decision Effect:** supports_mapping

**Control Triggers:** `specific system name`, `granular component`, `sub-entity`

**Policy Cues:** `broad scope definition`, `parent category`, `universal applicability`

**Failure Pattern:** The LLM fails to recognize that a control subject is covered because it looks for the specific subject name, ignoring that the policy scope explicitly covers the broader parent category or entity that includes the subject.

**Recovery Heuristic:** Check if the policy scope explicitly covers the parent category, broad entity, or system class that hierarchically includes the specific control subject.

**Dispute Categories:** NO_MATCH

**Source Policies:** Asset Management Policy, Breach Notification Policy, Change Management Policy, Data Protection Policy, Information Security Policy, Logging and Monitoring Policy, PCI DSS Compliance Policy, Vendor Management Policy, Vulnerability Management Policy

---

## Rule 2: Correlate Technical Implementations with Abstract Requirements

**Source Policy Count:** 8

**Description:** The technical specification is a recognized method for fulfilling the abstract requirement or strategic objective.

**Evidence Type:** technical_specification
**Decision Effect:** supports_mapping

**Control Triggers:** `Specific technical control`, `Configuration detail`, `Implementation method`

**Policy Cues:** `Strategic objective`, `Abstract requirement`, `Core activity mandate`

**Failure Pattern:** The LLM rejects mapping because the control requires a specific technical method or configuration, while the policy mandates the strategic objective or quality attribute that the method fulfills.

**Recovery Heuristic:** Map the specific technical control to the abstract policy objective if the technique is a recognized standard method for achieving that objective.

**Dispute Categories:** NO_MATCH

**Source Policies:** Asset Management Policy, Change Management Policy, Data Protection Policy, Encryption Policy, Logging and Monitoring Policy, Physical Security Policy, Software Development Life Cycle Policy, Vulnerability Management Policy

---

## Rule 3: Recognize Functional Semantic Equivalence

**Source Policy Count:** 7

**Description:** Policy describes a process or outcome that functionally mirrors the control requirement

**Evidence Type:** explicit_mandate
**Decision Effect:** supports_mapping

**Control Triggers:** `specific terminology`, `technical terms`, `exact phrasing`

**Policy Cues:** `functional description`, `outcome-based language`, `synonymous action`

**Failure Pattern:** The LLM rejects the mapping because it looks for strict string matching or exact terminology, failing to recognize that the policy language describes a process, outcome, or function that is semantically equivalent to the control requirement.

**Recovery Heuristic:** Identify if the policy language describes a process, outcome, or action that functionally mirrors the control requirement, even if the terminology differs.

**Dispute Categories:** NO_MATCH

**Source Policies:** Information Security Policy, PCI DSS Compliance Policy, Personal Data Management Policy, Public Cloud PII Protection Policy, Risk Assessment Policy, Vendor Management Policy, Vulnerability Management Policy

---

## Rule 4: Prioritize Governance Mandates Over Procedural Specifics

**Source Policy Count:** 6

**Description:** Presence of a binding governance statement covering the control's core objective

**Evidence Type:** procedural_definition
**Decision Effect:** supports_mapping

**Control Triggers:** `implementation steps`, `procedural details`, `specific workflow`

**Policy Cues:** `binding governance statement`, `high-level mandate`, `responsibility assignment`

**Failure Pattern:** The LLM rejects the mapping because specific procedural details (how/when) are missing, even though the policy explicitly mandates the core governance objective (what/who).

**Recovery Heuristic:** Validate that the policy mandates the core 'what' and 'who' (governance), accepting that implementation details ('how' and 'when') may live in downstream procedures.

**Dispute Categories:** NO_MATCH, PARTIAL

**Source Policies:** Change Management Policy, Disaster Recovery Plan, Password Policy, Public Cloud PII Protection Policy, Risk Assessment Policy, Vendor Management Policy

---

## Rule 5: Prioritize Activity Mandate Over Frequency

**Source Policy Count:** 5

**Description:** The core activity is mandated, even if the timing attribute is ambiguous

**Evidence Type:** frequency_timing
**Decision Effect:** supports_mapping

**Control Triggers:** `specific frequency`, `timing interval`, `periodic review`

**Policy Cues:** `continuous state mandate`, `activity requirement`, `periodic implication`

**Failure Pattern:** The LLM rejects the mapping due to missing, ambiguous, or implied frequency/timing attributes, even though the core control activity is explicitly mandated.

**Recovery Heuristic:** Confirm the core activity is mandated; treat frequency as a procedural detail or accept it as implicit in the existence of the mandate.

**Dispute Categories:** NO_MATCH, PARTIAL

**Source Policies:** Acceptable Use Policy, Asset Management Policy, Data Protection Policy, PCI DSS Compliance Policy, Physical Security Policy

---

## Rule 6: Validate Material Subset Coverage

**Source Policy Count:** 5

**Description:** Policy explicitly covers a material subset or instance of the control's scope

**Evidence Type:** scope_definition
**Decision Effect:** weak_support

**Control Triggers:** `universal scope`, `all assets`, `broad applicability`

**Policy Cues:** `specific asset class`, `material subset`, `relevant instance`

**Failure Pattern:** The LLM rejects the mapping because the policy explicitly covers only a material subset, specific instance, or relevant asset class of the control's scope, rather than the universal set.

**Recovery Heuristic:** Accept the mapping if the policy explicitly covers a material subset or relevant asset class of the control's scope, noting it as a partial or specific coverage match.

**Dispute Categories:** NO_MATCH, PARTIAL

**Source Policies:** Breach Notification Policy, Logging and Monitoring Policy, PCI DSS Compliance Policy, Software Development Life Cycle Policy, Vendor Management Policy

---

## Rule 7: Infer Entity Existence from Operational Mandates

**Source Policy Count:** 4

**Description:** Presence of mandatory component usage, governance, or action implies the existence and requirement of the overarching system or artifact.

**Evidence Type:** explicit_mandate
**Decision Effect:** supports_mapping

**Control Triggers:** `Requirement for specific resource`, `Requirement for specific artifact`, `System existence check`

**Policy Cues:** `Mandate to use component`, `Mandate to perform process`, `Operational usage requirements`

**Failure Pattern:** The LLM fails to infer the required existence of a system, resource, or artifact from a mandate to use, govern, or process it, treating the lack of an explicit "create X" statement as a gap.

**Recovery Heuristic:** If a policy mandates the usage, governance, or processing of an entity, treat the entity's existence as implicitly required.

**Dispute Categories:** NO_MATCH

**Source Policies:** Information Security Policy, Logging and Monitoring Policy, Maintenance Management Policy, Software Development Life Cycle Policy

---

## Rule 8: Validate Broad Artifact Content Coverage

**Source Policy Count:** 2

**Description:** Validation that the mandated artifact contains the required data points, regardless of file title

**Evidence Type:** artifact_reference
**Decision Effect:** supports_mapping

**Control Triggers:** `specific file name`, `exact data field`, `specific log event`

**Policy Cues:** `broad log definition`, `artifact content requirement`, `record retention mandate`

**Failure Pattern:** The LLM rejects the mapping because a specific file title or exact data point is not explicitly named, failing to recognize that the mandated artifact or log definition is broad enough to capture the requirement.

**Recovery Heuristic:** Validate that the mandated artifact, log, or record definition is broad enough to logically contain the required data points or specific control events.

**Dispute Categories:** NO_MATCH

**Source Policies:** PCI DSS Compliance Policy, Risk Assessment Policy

---

## Rule 9: Prioritize Core Objective Over Specific Sub-elements

**Source Policy Count:** 2

**Description:** The primary control objective is met, rendering the missing sub-steps or references a partial gap rather than a rejection.

**Evidence Type:** explicit_mandate
**Decision Effect:** supports_mapping

**Control Triggers:** `Missing external reference`, `Missing sub-step`, `Specific data point requirement`

**Policy Cues:** `Core subject matter`, `Primary control objective`, `Functional content`

**Failure Pattern:** The LLM rejects the mapping completely (No Match) when the core control objective is met but specific external references or sub-steps are missing, rather than classifying it as Partial.

**Recovery Heuristic:** If the primary control objective is satisfied, classify as Partial or Match rather than rejecting, treating missing details or references as gaps.

**Dispute Categories:** NO_MATCH, PARTIAL

**Source Policies:** Incident Response Plan, Physical Security Policy

---

## Rule 10: Validate Temporal Abstraction Coverage

**Source Policy Count:** 2

**Description:** Policy contains temporal generalization or continuous state mandate that covers the specific interval implied by the control.

**Evidence Type:** frequency_timing
**Decision Effect:** supports_mapping

**Control Triggers:** `specific interval`, `point-in-time`, `onboarding`, `annual review`

**Policy Cues:** `continuous`, `always`, `regularly`, `periodic`

**Failure Pattern:** LLM rejects mapping due to mismatched timing specificity, failing to see that continuous state mandates (e.g., 'always available') or general frequency terms in policy cover specific intervals (e.g., 'annually') or point-in-time requirements (e.g., 'at onboarding') in controls.

**Recovery Heuristic:** Assess if the policy's continuous or general timing requirement logically includes the specific interval or event trigger defined in the control.

**Dispute Categories:** NO_MATCH

**Source Policies:** AI Governance Policy, Incident Response Plan

---

## Rule 11: Validate Binding Preamble Inheritance

**Source Policy Count:** 2

**Description:** The mapping is accepted if the parent text explicitly binds the child content to a mandatory requirement.

**Evidence Type:** explicit_mandate
**Decision Effect:** supports_mapping

**Control Triggers:** `preamble`, `header`, `introduction`, `table`, `matrix`, `list`, `weak verb`, `colon`

**Policy Cues:** `shall`, `must`, `will`, `required`, `mandatory`, `applies to`

**Failure Pattern:** LLM fails to propagate the binding force of a strong preamble, header, or introductory clause to child content (such as weak verbs, list items, or tabular data), incorrectly treating the specific items as non-binding or structural only.

**Recovery Heuristic:** Identify if the parent section, header, or introduction contains binding language (e.g., 'must', 'shall') that explicitly governs the subsequent list items, table rows, or weak verbs.

**Dispute Categories:** NO_MATCH

**Source Policies:** Asset Management Policy, Encryption Policy

---
