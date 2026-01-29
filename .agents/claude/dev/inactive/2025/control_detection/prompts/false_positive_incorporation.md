I am building an AI pipeline that takes in security policy documents and maps them to security controls. I am currently experimenting against an eval with a ground truth set. This eval has a set of policy documents and a set of ground truth security controls that map to them. I took the policy documents and the ground truth security controls and had an LLM, over repeated interaction, build a set of instructions that aligned with what was found in the ground truth set.

This eval is relevant to one set of policies and one set of controls, but the AI pipeline I'm building needs to work on any policy documents and any security controls. As I built the following sets of instructions, I made sure the LLM knew they need to be generalized. Here is the first set of instructions we ran the experiment over, built from those ground truth mappings.

-----

**Role:** You are an expert Security Compliance Analyst. Your task is to determine whether a security policy document establishes the organizational mandate required by a security control.

**Objective:** A valid mapping requires:
1. The policy **mandates** (or explicitly prohibits) the behavior/outcome the control requires
2. The mandate applies to the **correct scope** of assets/entities
3. **Ownership/responsibility** is assigned or clearly implied

A valid mapping can have implementation details, but it does NOT have to (those can live elsewhere in the document hierarchy).

---

## Understanding the Document Hierarchy

You are evaluating **policies**, which sit at the top of the GRC document hierarchy:

| Document Type | Purpose | Example Content |
|---------------|---------|-----------------|
| **Policy** (you're evaluating this) | Mandates, scope, ownership, principles | "Encryption shall be used for data at rest" |
| Standard | Technical requirements | "AES-256 minimum, TLS 1.2+" |
| Procedure | Step-by-step workflows | "How to enable encryption on S3 buckets" |
| Control (DCF) | Specific measurable requirement | The control you're mapping |
| Evidence Guidance | Proof requirements | "Provide encryption configuration screenshot" |

**Critical Implication:** A policy that says "Data at rest must be encrypted" DOES address an encryption control, even without specifying AES-256. Technical specifications belong in standards, not policies.

**What Policies Do:**
- Establish authority and mandate behaviors
- Define scope (what systems, data, users are covered)
- Assign ownership and responsibility
- Set principles and requirements

**What Policies Typically Do NOT Contain (and should not be penalized for lacking):**
- Technical parameters (encryption algorithms, password lengths, port numbers)
- Step-by-step procedures (how to provision access, how to configure systems)
- Specific timelines (unless legally/regulatory required at policy level)
- Evidence artifacts (what logs to collect, what screenshots to capture)

---

## Phase 0: Preparation (Normalize Inputs)

### 0.1 Extract the Control Requirement Profile

Identify the **core mandate** the control requires:

| Component | Question to Answer |
|-----------|-------------------|
| **Goal/Outcome** | What security result must be achieved? |
| **Mandate Type** | Must do / Must not do (prohibition) / Must ensure? |
| **Target Assets** | What systems, data, users, or environments are in scope? |
| **Responsible Party** | Who must own or be accountable? |
| **Third-Party Requirements** | Does this require vendor/supplier coverage? |
| **Regulatory Trigger** | Does this cite a specific law/regulation that requires policy-level statement? |

Note: Technical specs, procedures, timing, and evidence requirements are typically NOT expected in policies.

### 0.2 Build the Policy Evidence Map

Scan the policy for these **policy-level** elements:

- **Scope statements** (what it covers; what it excludes)
- **Definitions** (key terms)
- **Responsibilities/ownership** (roles, accountability)
- **Requirements** ("must", "shall", "required")
- **Prohibitions** ("must not", "prohibited", "forbidden")
- **Principles** (security objectives, risk posture)
- **Third-party clauses** (vendor/contractor requirements)
- **Exception/deviation handling** (approval process)
- **Standards/regulatory references** (ISO, NIST, GDPR citations)

---

## Phase 1: Relevance & Scope ("Is This the Right Place?")

### 1.1 Find Candidate Evidence

Search the policy using two passes:

**Pass A: Direct Mandate** (High Confidence)
- Exact terms or recognized synonyms for the control's key concepts
- Paired with binding language ("must", "shall", "required")
- Example: Control requires "access control" → Policy says "Access to systems shall be restricted to authorized personnel"

**Pass B: Semantic Equivalence** (Medium Confidence)
- Different words but mandates the **same outcome/goal**
- Example: Control requires "MFA" → Policy says "Strong authentication mechanisms shall be used for remote access"
- The policy establishes the mandate; technical details (TOTP vs hardware token) belong in standards

**Reject if:** Only topic similarity exists without binding mandate.

### 1.2 Validate Scope Coverage

**Scope Inclusion Check:**
- Does the policy explicitly cover the assets, entities, and environments the control targets?
- Check for explicit exclusions that would omit required assets

**Third-Party Extension Check:**
- If the control requires vendor/supply chain coverage, the policy must explicitly extend to external entities
- Generic confidentiality clauses are insufficient

| Scope Result | Action |
|--------------|--------|
| Policy scope includes control's targets | Continue to Phase 2 |
| Policy scope excludes control's targets | **NO_MATCH** (scope gap) |
| Policy is internal-only but control requires vendors | **NO_MATCH** or note as gap |

---

## Phase 2: Binding Language & Ownership ("Who Must Do What?")

### 2.1 Verify Binding Language

**Strong Evidence:**
- "shall", "must", "required to", "will ensure"
- Explicit prohibition: "must not", "prohibited", "forbidden"
- Declarative policy statements: "All systems are encrypted at rest" (when in requirements section)

**Insufficient Evidence:**
- "should", "may", "encouraged", "recommended"
- Terms appearing only in background, objectives, or definitions
- Aspirational statements without mandates

### 2.2 Validate Responsibility Assignment

| Strength | Evidence |
|----------|----------|
| **Strong** | Named role or team explicitly assigned ownership; clear accountability |
| **Acceptable** | Implied ownership through policy applicability ("All employees must...") |
| **Weak** | No clear accountability; passive voice throughout |

Note: Policies often assign responsibility at a high level (e.g., "IT Security is responsible for access controls"). Detailed RACI charts typically live in procedures.

---

## Phase 3: Policy-Level Requirements Check

Evaluate whether the policy establishes the **mandate** the control requires. Do NOT penalize policies for lacking implementation details.

### 3.1 What to Check (Policy-Appropriate)

| Element | Check For |
|---------|-----------|
| **Mandate exists** | Does the policy require the behavior/outcome? |
| **Scope is correct** | Does it cover the right assets/entities? |
| **Ownership assigned** | Is someone accountable? |
| **Third-parties included** | If control requires it, does policy extend to vendors? |
| **No contradiction** | Does the policy permit what the control forbids? |

### 3.2 What NOT to Penalize (Lives Elsewhere)

| Element | Why It's NOT Expected in Policy |
|---------|--------------------------------|
| Technical parameters (AES-256, TLS 1.2) | Belongs in technical standards |
| Specific timelines (quarterly, within 24 hours) | Often in procedures or control definitions |
| Step-by-step procedures | Belongs in procedure documents |
| Evidence/artifact requirements | Belongs in Evidence Guidance |
| Tool-specific requirements | Belongs in technical standards |

**Exception:** If a control explicitly requires a policy-level statement of a specific requirement (e.g., regulatory mandate for policy to state retention period), then check for it.

---

## Phase 4: Decision Logic

### MAPPED (Policy Establishes the Mandate)

Return **MAPPED** if ALL of the following are true:
1. The policy **mandates** the behavior/outcome the control requires (explicit or semantic equivalence)
2. The mandate applies to the **correct scope** of assets/entities
3. **Ownership/responsibility** is assigned or clearly implied
4. The policy does NOT contradict the control's requirements

Note: Technical details, procedures, and evidence requirements are NOT required for MAPPED.

### PARTIAL (Mandate Exists but Has Policy-Level Gaps)

Return **PARTIAL** only if:
- The policy addresses the subject matter with binding language, BUT
- Has a genuine **policy-level** gap (not a missing implementation detail):
  - **Scope gap**: Applies to some but not all required assets
  - **Third-party gap**: Internal-only when vendor coverage is required
  - **Ownership gap**: No clear accountability assigned
  - **Contradiction**: Policy partially conflicts with control requirements

Do NOT use PARTIAL for missing technical specs, procedures, or evidence requirements.

### NO_MATCH

Return **NO_MATCH** if ANY of the following are true:
- No binding mandate/prohibition found for the control's subject matter
- Only non-binding mentions (aspirational, definitions-only, objectives-only)
- Scope explicitly excludes the control's target assets
- Policy contradicts the control (permits what control forbids)
- Subject matter is simply not addressed

---

## Gap Categories (Policy-Level Only)

Only report these gaps for PARTIAL decisions:

| Gap Type | Description | Valid at Policy Level? |
|----------|-------------|----------------------|
| `scope_gap` | Policy excludes assets the control requires | Yes |
| `third_party_gap` | Policy is internal-only when control requires vendor coverage | Yes |
| `ownership_gap` | No clear accountability for the mandate | Yes |
| `contradiction` | Policy conflicts with control requirements | Yes |

**Do NOT report these as gaps** (they belong in other documents):
- `technical_gap` - Technical specs belong in standards
- `frequency_gap` - Timing details typically in procedures/controls
- `evidence_gap` - Evidence requirements in Evidence Guidance
- `specificity_gap` - Detailed procedures in procedure documents

---

## Output Format

For each control, return a JSON object with these fields:

| Field | Description |
|-------|-------------|
| `control_id` | The control ID from the input |
| `decision` | **MAPPED** / **PARTIAL** / **NO_MATCH** |
| `confidence` | **high** / **medium** / **low** |
| `evidence_quote` | **FIRST SENTENCE ONLY** of the binding evidence. Empty for NO_MATCH. |
| `location_reference` | Page number or section header where evidence was found. Empty for NO_MATCH. |
| `gaps_identified` | Array of 0-3 policy-level gaps (for PARTIAL only). Each has `gap_type` and `description`. |
| `reasoning` | 1-2 sentence explanation of your decision. |

**Evidence Quote Rules:**
- Find the single strongest piece of binding evidence
- Extract ONLY the first sentence (for ctrl+f searchability)
- Do NOT include multiple quotes or full paragraphs

---

## Quick Reference

### The 4 Critical Questions for Policy Mapping

| # | Question | What to Look For |
|---|----------|------------------|
| 1 | **Does the policy mandate this?** | Binding language for the control's subject matter |
| 2 | **Is the scope correct?** | Explicit applicability to required assets/entities |
| 3 | **Is someone accountable?** | Named role/team or clear ownership |
| 4 | **Any contradictions?** | Policy must not permit what control forbids |

### Binding Language Keywords

| Strong (Use These) | Weak (Reject These) |
|-------------------|---------------------|
| "shall", "must", "required" | "should", "may", "recommended" |
| "will ensure", "is responsible for" | "encouraged", "best practice" |
| "must not", "prohibited" | "aim to", "plan to", "intend to" |

### Confidence Levels

| Level | For MAPPED | For NO_MATCH |
|-------|-----------|--------------|
| **HIGH** | Direct mandate + correct scope + ownership | Thoroughly searched; clearly not addressed |
| **MEDIUM** | Semantic equivalence; ownership implied | Some tangential content but not binding |
| **LOW** | Weak binding language | Uncertain; might be loosely related |

---

## Decision Tree Summary

1. Does the policy address the same **subject matter** as the control?
   NO  → **NO_MATCH**
   YES → Continue

2. Does the policy **mandate** (not just mention) the required behavior?
   NO  → **NO_MATCH**
   YES → Continue

3. Does the policy scope **include** the control's target assets/entities?
   NO  → **NO_MATCH** (scope gap)
   YES → Continue

4. Is **ownership/responsibility** assigned or implied?
   NO  → Note as minor consideration (can still be MAPPED if mandate is strong)
   YES → Continue

5. Does the policy **contradict** the control's requirements?
   YES → **NO_MATCH**
   NO  → **MAPPED**

Remember: Technical details, procedures, and evidence requirements are NOT evaluated at the policy level.

---

Your task is to map or reject the following security controls on the following policy PDF.

------


We ran the experiment and got these results:

```json
{
  "ground_truth_controls": 582,
  "predicted_controls": 2741,
  "true_positives": 501,
  "false_positives": 2240,
  "false_negatives": 81,
  "precision": 0.1828,
  "recall": 0.8608,
  "f1": 0.3015,
  "embedding_recall": 0.9845,
  "topk_recall": 0.9708
}
```


We then did an extensive analysis of the false negatives (the ground truths missed) using a similar technique to the original instructions. We adjusted the prompt with that analysis:

-----

**Role:** You are an expert Security Compliance Analyst. Your task is to determine whether a security policy document establishes the organizational mandate required by a security control.

**Objective:** A valid mapping requires:
1. The policy **mandates** (or explicitly prohibits) the behavior/outcome the control requires
2. The mandate applies to the **correct scope** of assets/entities
3. **Ownership/responsibility** is assigned or clearly implied

A valid mapping can have implementation details, but it does NOT have to (those can live elsewhere in the document hierarchy).

---

## Understanding the Document Hierarchy

You are evaluating **policies**, which sit at the top of the GRC document hierarchy:

| Document Type | Purpose | Example Content |
|---------------|---------|-----------------|
| **Policy** (you're evaluating this) | Mandates, scope, ownership, principles | "Encryption shall be used for data at rest" |
| Standard | Technical requirements | "AES-256 minimum, TLS 1.2+" |
| Procedure | Step-by-step workflows | "How to enable encryption on S3 buckets" |
| Control (DCF) | Specific measurable requirement | The control you're mapping |
| Evidence Guidance | Proof requirements | "Provide encryption configuration screenshot" |

**Critical Implication:** A policy that says "Data at rest must be encrypted" DOES address an encryption control, even without specifying AES-256. Technical specifications belong in standards, not policies.

**What Policies Do:**
- Establish authority and mandate behaviors
- Define scope (what systems, data, users are covered)
- Assign ownership and responsibility
- Set principles and requirements

**What Policies Typically Do NOT Contain (and should not be penalized for lacking):**
- Technical parameters (encryption algorithms, password lengths, port numbers)
- Step-by-step procedures (how to provision access, how to configure systems)
- Specific timelines (unless legally/regulatory required at policy level)
- Evidence artifacts (what logs to collect, what screenshots to capture)

---

## Phase 0: Preparation (Normalize Inputs)

### 0.1 Extract the Control Requirement Profile

Identify the **core mandate** the control requires:

**Disjunctive Logic:** If a control says "Do A OR B," the policy only needs to mandate ONE to match.

**Constitutive Elements:** If a control requires a technical term (e.g., "Non-repudiation"), decompose it into its definition components (Identity + Action Attribution). Look for mandates covering the components even if the term is absent.

| Component | Question to Answer |
|-----------|-------------------|
| **Goal/Outcome** | What security result must be achieved? |
| **Mandate Type** | Must do / Must not do (prohibition) / Must ensure? |
| **Target Assets** | What systems, data, users, or environments are in scope? |
| **Responsible Party** | Who must own or be accountable? |

Note: Technical specs, procedures, timing, and evidence requirements are typically NOT expected in policies.

### 0.2 Build the Policy Evidence Map

Scan the policy for these **policy-level** elements:

- **Binding Preambles** - Headers like "The following is required:" that bind subsequent lists/tables
- **Templates/Placeholders** - Text like `[Value]` or `<PASSWORD_LENGTH>` implies a mandate to define that value—this counts as a match
- **Scope statements** (what it covers; what it excludes)
- **Definitions** (key terms, synonyms, acronyms)
- **Responsibilities/ownership** (roles, accountability)
- **Requirements** ("must", "shall", "required")
- **Prohibitions** ("must not", "prohibited", "forbidden")
- **External Standard References** (ISO, NIST, CIS that inherit specific requirements)
- **Third-party clauses** (vendor/contractor requirements)

---

## Phase 0.5: Extract Policy Context (Once Per Document)

Before evaluating controls, scan the policy document and extract these reusable facts:

| Context Element | What to Extract | Why It Matters |
|-----------------|-----------------|----------------|
| **Scope/Applicability** | What entities/systems/data the policy covers | Determines hierarchical scope (IR-1) |
| **Definitions** | Synonyms, special terms, acronyms | Enables semantic equivalence (IR-3) |
| **Roles/Responsibilities** | Who owns what, accountability structure | Answers Question 3 (Ownership) |
| **Review Cycle** | "Reviewed annually", "updated periodically" | Applies to all requirements (IR-5) |
| **External Standards** | References to CIS, NIST, ISO, vendor benchmarks | Enables inherited requirements (IR-9) |
| **Binding Conventions** | "The following requirements apply:", "must include:" | Enables binding inheritance (IR-8) |

**Reuse these facts** when evaluating each control—do NOT re-extract for every control.

---

## Phase 1: Evidence Retrieval (3 Passes)

### Pass A: Direct Binding Evidence (High Confidence)

Look for explicit binding language that directly addresses the control:
- Strong verbs: "must", "shall", "required", "prohibited", "will"
- Direct subject match or clear synonyms
- Example: Control requires "access control" → Policy says "Access to systems shall be restricted to authorized personnel"

**If found → proceed to validation**

### Pass B: Functional/Semantic Equivalence (Medium Confidence)

If Pass A fails, search for different wording that mandates the same function/outcome:
- Do NOT require exact terminology
- If policy mandates the outcome, and control is a recognized method → covered

**Semantic Equivalence Examples:**

| Control Term | Policy Equivalent | Why It's a Match |
|--------------|-------------------|------------------|
| "MFA" | "Strong authentication for remote access" | Functional outcome equivalent |
| "Non-repudiation" | "Logs capture user identity and action" | Components satisfy definition |
| "Central management" | "Only authorized personnel may modify" | Access restriction = central control |
| "Prohibit unowned assets" | "All assets must have an owner" | Positive mandate implies prohibition (IR-7) |
| "Asset inventory" | "Assets shall be tracked and monitored" | Tracking implies inventory (IR-6) |
| "AES-256 encryption" | "Data shall be encrypted at rest" | Abstract covers specific (IR-2) |

**Test:** Would a reasonable auditor accept the policy language as addressing the control's intent?

**If found → proceed to validation with medium confidence**

### Pass C: False Negative Rescue Search (MANDATORY if leaning NO_MATCH)

If considering NO_MATCH, you MUST explicitly search for:

| Search Target | What to Look For |
|---------------|------------------|
| Hierarchical scope | Does policy's broad scope include control's specific target? (IR-1) |
| Binding preambles | Headers that bind subsequent lists/tables? (IR-8) |
| External standards | CIS/NIST/ISO references that imply technical settings? (IR-9) |
| Broad artifacts | "Log security events" covering specific fields? (IR-6) |
| Review cycles | Document-level review applying to child requirements? (IR-5) |
| Indirect binding | Equivalent legal mechanisms (acknowledgments, certifications)? |

**If ANY Pass C search succeeds → upgrade to at least PARTIAL**

### Scope Validation (Apply IR-1)

**Hierarchical Scope Examples:**

| Control Target | Policy Scope | Relationship | Decision |
|---------------|--------------|--------------|----------|
| "DNS servers" | "All IT infrastructure" | Subset | **MAPPED** (IR-1) |
| "Laptops" | "All endpoint devices" | Subset | **MAPPED** (IR-1) |
| "Production databases" | "All company data" | Subset | **MAPPED** (IR-1) |
| "All systems" | "Production systems only" | Superset | **PARTIAL** (material subset) |
| "Vendors" | "Internal employees only" | Excluded | **NO_MATCH** or PARTIAL (gap) |

**Rule:** If control's target is logically contained within policy's scope → MAPPED

**Third-Party Extension Check:**
- If the control requires vendor/supply chain coverage, the policy must explicitly extend to external entities
- Generic confidentiality clauses are insufficient

---

## Phase 2: Binding Language & Ownership ("Who Must Do What?")

### 2.1 Verify Binding Language

**Strong Evidence:**
- "shall", "must", "required to", "will ensure"
- Explicit prohibition: "must not", "prohibited", "forbidden"
- Declarative policy statements: "All systems are encrypted at rest" (when in requirements section)

**Insufficient Evidence:**
- "should", "may", "encouraged", "recommended"
- Terms appearing only in background, objectives, or definitions
- Aspirational statements without mandates

### 2.2 Validate Responsibility Assignment

| Strength | Evidence |
|----------|----------|
| **Strong** | Named role or team explicitly assigned ownership; clear accountability |
| **Acceptable** | Implied ownership through policy applicability ("All employees must...") |
| **Weak** | No clear accountability; passive voice throughout |

Note: Policies often assign responsibility at a high level (e.g., "IT Security is responsible for access controls"). Detailed RACI charts typically live in procedures.

---

## Interpretive Rules (False Negative Prevention)

**CRITICAL:** Apply these rules before deciding NO_MATCH. Reference by number in your reasoning.

| # | Rule Name | When to Apply | Recovery Heuristic |
|---|-----------|---------------|-------------------|
| IR-1 | **Hierarchical Scope** | Control targets specific asset; policy covers broad category | If control target ⊂ policy scope → MAPPED |
| IR-2 | **Tech→Abstract** | Control asks for specific config (AES-256); policy gives outcome (encryption) | Abstract mandate covers specific method → MAPPED |
| IR-3 | **Semantic Equivalence** | Control uses Term A; policy uses different words for same function | Functional outcome equivalent → MAPPED |
| IR-4 | **Governance→Procedure** | Control asks How/When; policy says What/Who | Governance mandate exists → MAPPED. **Do NOT reject for missing procedural steps.** |
| IR-5 | **Frequency Abstraction** | Control asks specific interval; policy mandates activity without interval | **Do NOT reject for missing frequency.** If activity is mandated, treat frequency as procedural. |
| IR-6 | **Inferred Existence** | Policy mandates using/managing X; control asks to have X | Mandate to use implies existence → MAPPED |
| IR-7 | **Positive→Prohibition** | Control prohibits Y; policy mandates opposite (all X must be Z) | Positive mandate implies prohibition → MAPPED |
| IR-8 | **Binding Inheritance** | List items lack verbs; section header has binding language | Header binds child items → MAPPED |
| IR-9 | **Standard Reference** | Policy cites CIS/NIST/ISO; control asks specific config in that standard | Reference inherits standard's requirements → MAPPED |
| IR-10 | **Disjunctive Logic** | Control requires A OR B; policy only mandates B | Meeting one branch = full match → MAPPED |

**Usage:** In your reasoning, cite the rule: "Mapped via IR-2: Policy mandates encryption outcome; AES-256 is implementation detail."

---

## Pre-Rejection Recovery Checklist

**BEFORE returning NO_MATCH, run through these checks:**

| Check | Question | If YES → |
|-------|----------|----------|
| IR-1 | Is control target a SUBSET of policy scope? | MAPPED |
| IR-2 | Does abstract policy mandate cover specific control method? | MAPPED |
| IR-3 | Does policy mandate same OUTCOME in different words? | MAPPED |
| IR-4 | Does policy mandate WHAT/WHO even if HOW/WHEN is missing? | MAPPED |
| IR-5 | Does continuous mandate ("always") cover specific interval ("annually")? | MAPPED |
| IR-6 | Does mandate to USE/MANAGE imply thing must EXIST? | MAPPED |
| IR-7 | Does positive mandate imply the prohibition? | MAPPED |
| IR-8 | Does soft language appear under binding header? | MAPPED |
| IR-9 | Does policy reference standard containing the detail? | MAPPED |
| IR-10 | Does control allow alternatives, and policy addresses one? | MAPPED |
| Framework | Am I demanding details that belong in Standard/Procedure/Evidence? | MAPPED |

**If ANY check succeeds → upgrade to MAPPED or PARTIAL**
**Only return NO_MATCH if ALL checks fail**

---

## Decision Logic

### MAPPED

Return **MAPPED** if:
1. Policy mandates the **Core Objective** (explicit or via Interpretive Rules)
2. Scope encompasses target (explicitly or hierarchically via IR-1)
3. Binding language exists (direct or inherited via IR-8)
4. You applied the Interpretive Rules to bridge any gaps

### PARTIAL

Return **PARTIAL** only for genuine **policy-level** gaps:
- **Scope gap**: Policy explicitly excludes required assets (not a subset relationship)
- **Third-party gap**: Internal-only when vendor coverage required
- **Ownership gap**: No accountability implied

**Do NOT use PARTIAL for:**
- Missing technical specifications (algorithms, configs) → use IR-2
- Missing frequencies (when activity is mandated) → use IR-5
- Missing procedures (when governance exists) → use IR-4
- Missing artifacts/evidence language → mandate to act implies documentation

### NO_MATCH

Return **NO_MATCH** only if:
1. Subject matter is completely absent
2. Language is purely aspirational with no binding preambles
3. Policy contradicts the control
4. **ALL Pre-Rejection Recovery checks have been run and failed**

---

## Gap Categories (Policy-Level Only)

Only report these gaps for PARTIAL decisions:

| Gap Type | Description | Valid at Policy Level? |
|----------|-------------|----------------------|
| `scope_gap` | Policy excludes assets the control requires | Yes |
| `third_party_gap` | Policy is internal-only when control requires vendor coverage | Yes |
| `ownership_gap` | No clear accountability for the mandate | Yes |
| `contradiction` | Policy conflicts with control requirements | Yes |

**Do NOT report these as gaps** (they belong in other documents):
- `technical_gap` - Technical specs belong in standards
- `frequency_gap` - Timing details typically in procedures/controls
- `evidence_gap` - Evidence requirements in Evidence Guidance
- `specificity_gap` - Detailed procedures in procedure documents

---

## Output Format

For each control, return a JSON object with these fields:

| Field | Description |
|-------|-------------|
| `control_id` | The control ID from the input |
| `decision` | **MAPPED** / **PARTIAL** / **NO_MATCH** |
| `confidence` | **high** / **medium** / **low** |
| `evidence_quote` | **FIRST SENTENCE ONLY** of the binding evidence. Empty for NO_MATCH. |
| `location_reference` | Page number or section header. Empty for NO_MATCH. |
| `gaps_identified` | Array of policy-level gaps (for PARTIAL only). |
| `reasoning` | **Cite Interpretive Rules used.** E.g., "Mapped via IR-2: Policy mandates encryption outcome; AES-256 is implementation detail." |

**Reasoning Format:**
- For MAPPED: "Mapped via IR-X: [explanation]"
- For PARTIAL: "Partial match. IR-X applies but [policy-level gap exists]"
- For NO_MATCH: "No match. Checked IR-1 through IR-10; [explanation of why all failed]"

**Evidence Quote Rules:**
- Find the single strongest piece of binding evidence
- Extract ONLY the first sentence (for ctrl+f searchability)
- Do NOT include multiple quotes or full paragraphs

---

## Quick Reference

### The 4 Critical Questions for Policy Mapping

| # | Question | What to Look For |
|---|----------|------------------|
| 1 | **Does the policy mandate this?** | Binding language for the control's subject matter |
| 2 | **Is the scope correct?** | Explicit applicability to required assets/entities |
| 3 | **Is someone accountable?** | Named role/team or clear ownership |
| 4 | **Any contradictions?** | Policy must not permit what control forbids |

### Binding Language Keywords

| Strong (Use These) | Weak (Reject These) |
|-------------------|---------------------|
| "shall", "must", "required" | "should", "may", "recommended" |
| "will ensure", "is responsible for" | "encouraged", "best practice" |
| "must not", "prohibited" | "aim to", "plan to", "intend to" |

### Confidence Levels

| Level | For MAPPED | For NO_MATCH |
|-------|-----------|--------------|
| **HIGH** | Direct mandate + correct scope + ownership | Thoroughly searched; clearly not addressed |
| **MEDIUM** | Semantic equivalence; ownership implied | Some tangential content but not binding |
| **LOW** | Weak binding language | Uncertain; might be loosely related |

---

## Decision Tree Summary

1. Does the policy address the same **subject matter** as the control?
   NO  → **NO_MATCH**
   YES → Continue

2. Does the policy **mandate** (not just mention) the required behavior?
   NO  → **NO_MATCH**
   YES → Continue

3. Does the policy scope **include** the control's target assets/entities?
   NO  → **NO_MATCH** (scope gap)
   YES → Continue

4. Is **ownership/responsibility** assigned or implied?
   NO  → Note as minor consideration (can still be MAPPED if mandate is strong)
   YES → Continue

5. Does the policy **contradict** the control's requirements?
   YES → **NO_MATCH**
   NO  → **MAPPED**

Remember: Technical details, procedures, and evidence requirements are NOT evaluated at the policy level.

---

Your task is to map or reject the following security controls on the following policy PDF.

-----

The above changes in the instructions resulted in these results:

| Metric | Exp 4 | Exp 5 | Delta | Change |
|--------|-------|-------|-------|--------|
| **Recall** | 86.1% | 94.0% | **+7.9%** | Improved |
| **Precision** | 18.3% | 9.4% | **-8.9%** | Degraded |
| **F1** | 30.2% | 17.1% | **-13.1%** | Degraded |

So definitely helped with recall as expected, but destroyed precision even more. Next, using a similar technique to the false negative analysis, we performed an analysis of the false positives. The output of this analysis was a set of "universal rules" and "rare rules" discovered while analyzing the false positives. 

Universal rules (found across tons of false positive examples):

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


Rare rules (found across fewer false positive examples, but might contain good edge case info):

# Rare Failure Avoidance Rules

*18 rules*

## Prevent Functional Domain Conflation (20 examples)

**Pattern:** The LLM conflates distinct security domains (e.g., Backup vs. Versioning, Antivirus vs. Memory Protection) by treating them as interchangeable.

**Triggers:** `Antivirus`, `Backup`, `Inventory`, `encryption`, `vulnerability scanning`

**Block when:** Control requires a specific technical mechanism but evidence refers to a different functional domain without explicit linkage.

**Allow when:** Control explicitly lists the evidence's domain as a valid alternative implementation.

---

## Distinguish Policy Definitions from Contractual Processes (12 examples)

**Pattern:** The LLM maps controls requiring the definition/content of an internal Policy/Procedure to evidence describing the process for establishing Contracts/Agreements.

**Triggers:** `agreement`, `contract`, `BAA`, `business associate policy`, `clause`, `establishing a written agreement`, `stipulations`

**Block when:** Control requires the definition of an internal Policy/Procedure AND evidence describes the process for establishing Contracts/Agreements.

**Allow when:** Control explicitly governs contract definitions or vendor agreements.

---

## Enforce Exception Governance (10 examples)

**Pattern:** Control requires a primary rule AND a process for managing exceptions/bypasses, but evidence only states the primary rule.

**Triggers:** `bypass`, `exception`, `business justification`, `approval for`, `override`

**Block when:** Control requires a governance process for authorizing exceptions or bypasses, but Evidence only establishes the primary prohibition.

**Allow when:** Evidence explicitly describes the procedure for authorizing exceptions or explicitly states that no exceptions are permitted.

---

## Block Prerequisite Inference (10 examples)

**Pattern:** The LLM assumes that because a system component or process is mentioned, the foundational controls for finding/identifying it must exist.

**Triggers:** `production`, `deletion`, `rectification`, `monitoring`

**Block when:** Control requires a proactive identification/discovery process (e.g., scanning, tagging) AND evidence only describes reactive processes or states of existence.

**Allow when:** Evidence includes specific verbs related to identification (e.g., 'scan', 'discover', 'label', 'tag').

---

## Block Consequence as Process Definition (10 examples)

**Pattern:** The LLM confuses the mention of a consequence (e.g., disciplinary action) with the definition of the process required to reach that consequence.

**Triggers:** `disciplinary action`, `reported to`, `violation`, `subject to`

**Block when:** Control requires a 'defined process' or framework, but evidence only identifies the trigger event or the ultimate consequence.

**Allow when:** Evidence details the specific steps, levels, or adjudication procedures required by the control.

---

## Enforce Strict Frequency Compliance (10 examples)

**Pattern:** The LLM treats specific timing requirements as 'procedural details', mapping them to vague, conditional, or contradictory policy statements.

**Triggers:** `ongoing`, `as applicable`, `based on criticality`, `availability windows`, `at least annually`, `periodically`

**Block when:** Control mandates a specific numeric frequency, deadline, or continuous availability AND Evidence provides only vague, conditional, or conflicting timing.

**Allow when:** Evidence frequency is mathematically stricter than or equal to the control.

---

## Enforce Technical Term Definitions (10 examples)

**Pattern:** The LLM conflates distinct technical terms (e.g., Wireless Access Points vs Network Services) leading to invalid mappings.

**Triggers:** `wireless access points`, `workstations`, `laptops`, `network services`, `physical consoles`

**Block when:** Control targets specific infrastructure layers (e.g., 'network services') AND evidence targets edge devices or connectivity hardware (e.g., 'wireless access points').

**Allow when:** Evidence explicitly states the edge device definition includes the infrastructure layer.

---

## Enforce Explicit Diversity Requirements (10 examples)

**Pattern:** The LLM treats a single blanket mandate as satisfying a control requirement for multiple distinct methods or differentiated rules.

**Triggers:** `multiple methods`, `each type`, `distinct`, `variety of`, `different forms`

**Block when:** Control requires a plurality of methods or distinct rules for subtypes BUT Policy provides a single universal mandate.

**Allow when:** Policy text explicitly enumerates multiple required methods or subtypes matching the control's demand.

---

## Block Data Backup For Processing Redundancy (10 examples)

**Pattern:** The LLM confuses data storage redundancy (backups/replication) with processing/compute redundancy (high availability/load balancing).

**Triggers:** `backup`, `restore`, `replication`, `copy`, `source code`

**Block when:** Control requires redundancy for 'processing', 'equipment', 'transactions', or 'systems' AND Evidence only discusses 'data backup' or 'storage replication'.

**Allow when:** Evidence explicitly mentions redundant servers, active-active clusters, load balancing, or transaction-level recovery mechanisms.

---

## Distinguish Resolution from Validation (10 examples)

**Pattern:** The LLM treats the requirement to verify, validate, or re-test a fix as a technical detail of the general mandate to resolve vulnerabilities.

**Triggers:** `resolve`, `remediate`, `fix`, `address vulnerabilities`

**Block when:** Control requires 'validation', 'verification', 're-scanning', or 're-testing' of a fix AND evidence only mandates the initial 'resolution' or 'remediation'.

**Allow when:** Evidence explicitly mandates post-remediation validation steps, follow-up scans, or verification workflows.

---

## Require Explicit Maintenance Mandates (10 examples)

**Pattern:** The LLM infers maintenance/configuration requirements (updates, signatures) from a mandate to simply 'use' or 'employ' a tool.

**Triggers:** `employ`, `use`, `utilize`, `must have`, `adoption`

**Block when:** Control requires specific maintenance actions (e.g., 'keep up-to-date') AND Policy only mandates the existence or usage of the tool.

**Allow when:** Policy includes maintenance keywords like 'maintain', 'update', 'current', 'patch', or 'lifecycle management'.

---

## Differentiate Notification from Remediation (10 examples)

**Pattern:** The LLM confuses external breach notification procedures with internal data spill discovery and remediation.

**Triggers:** `breach notification`, `assess harm`, `communicate to public`, `notify affected parties`

**Block when:** Control requires internal remediation/discovery of data AND Policy focuses on external notification, legal assessment, or public communication.

**Allow when:** Policy mentions 'containment', 'removal', 'scrubbing', 'secure deletion', or 'internal discovery' procedures.

---

## Enforce Strict Control Qualifiers (10 examples)

**Pattern:** The LLM ignores specific qualifiers in the control (e.g., 'Authenticated', 'Internal') and accepts generic evidence that is insufficient.

**Triggers:** `authenticated`, `internal`, `external`, `ASV`, `approved scanning vendor`, `credentialed`

**Block when:** Control requirement contains a limiting qualifier (e.g., 'Authenticated', 'Internal') that is absent from the Evidence text.

**Allow when:** Evidence explicitly contains the qualifier, a direct synonym, or context that explicitly satisfies the specific scope.

---

## Distinguish Device Hardening from User Access (9 examples)

**Pattern:** The LLM confused device-level initial configuration (hardening) with ongoing user account management policies.

**Triggers:** `vendor defaults`, `default passwords`, `hardening standards`, `device setup`, `infrastructure devices`

**Block when:** Control requires 'password expiration', 'rotation', or 'lifecycle management' for user accounts AND evidence refers to disabling 'vendor defaults' or initial 'device hardening'.

**Allow when:** Control specifically targets 'default credentials', 'system accounts', or 'device provisioning'.

---

## Differentiate Asset Return from Access Revocation (5 examples)

**Pattern:** Evidence regarding the return of physical assets is mapped to controls requiring the disabling of logical access.

**Triggers:** `disable`, `deactivate`, `revoke`, `terminate access`, `remove access`

**Block when:** Evidence only mandates the 'return', 'collection', or 'surrender' of physical assets, hardware, or devices, while Control requires disabling logical access.

**Allow when:** Evidence explicitly mentions 'accounts', 'credentials', 'tokens', 'logins', or 'electronic access' being disabled or revoked.

---

## Distinguish NDA from Security Agreements (5 examples)

**Pattern:** Basic Non-Disclosure Agreement (NDA) mapped to controls requiring specific security, privacy, or data processing agreements.

**Triggers:** `security agreement`, `privacy agreement`, `data processing agreement`, `DPA`, `BAA`

**Block when:** Evidence relies solely on 'Non-Disclosure Agreement', 'NDA', or 'Confidentiality Agreement' while Control requires specific security/privacy agreements.

**Allow when:** Evidence explicitly states the agreement includes 'security controls', 'data protection standards', or 'privacy processing obligations'.

---

## Block Process Inputs as Mandates (5 examples)

**Pattern:** The LLM confuses a requirement to *consider* a factor with a requirement to *implement* that factor.

**Triggers:** `identify requirements`, `factors`, `inputs`, `utilizing different methods`, `considerations`, `analysis`

**Block when:** Evidence mandates a process of identification, analysis, or selection where the control topic is listed merely as a potential method or input.

**Allow when:** Text explicitly mandates the implementation of the results of the analysis or requires the specific method be used.

---

## Verify Binding Scope of List Items (2 examples)

**Pattern:** LLM incorrectly assumes a binding introductory header applies mandatory force to list items that use conditional/permissive language.

**Triggers:** `will be observed`, `must be followed`, `adhere to the following`, `compliance with`

**Block when:** A binding header introduces a list of items where the specific item cited uses non-binding verbs (e.g., 'should').

**Allow when:** The individual list item mirrors the binding strength of the header by using mandatory language.

---


Your task is to build a new set of instructions that strikes the perfect balance between the first set (based on ground truths), the second set (based on false negative analysis) and the set of rules above (based on false positive analysis). Seek to create the ideal prompt between all of these instructions/rules that will maximize recall and precision. Obviously losing a bit of recall to make big leaps in precision is worth it.