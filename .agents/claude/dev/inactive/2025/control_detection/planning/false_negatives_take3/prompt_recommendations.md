# Prompt Recommendations: Boosting Recall to 80-85%

**Current Recall**: 72.82%
**Target Recall**: 80-85%
**FNs to Recover**: ~42-72 of 141

**Strategy**: Make surgical changes to recover the most FNs with minimal FP increase. Focus on G-10, PARTIAL→MAPPED, and G-17 refinements.

---

## Priority 1: Fix G-10 Frequency Qualifier Over-Application (Est. +5-7pp recall)

### Problem
The G-10/G-16 Qualifier Gap Rule (lines 267-278) already says:
> "If control has (1) ARTIFACT/MECHANISM + (2) OPERATIONAL QUALIFIER, and Component 1 is satisfied → Return MAPPED"

But the LLM is NOT applying this consistently for frequency qualifiers. 47 G-10 rejections, ~30 are frequency-related.

### Root Cause
1. The rule is buried in the PARTIAL section (lines 267-278)
2. It conflicts with earlier language in G-10 definition (line 182): "hard qualifiers absent from evidence (no inference allowed)"
3. Line 186 lists "numeric frequencies" as hard qualifiers

### Solution: Restructure G-10 to Distinguish Primary vs Secondary Qualifiers

**REPLACE lines 180-186:**

```markdown
### Category D: Qualifier & Artifact Requirements

| ID | Block When | Example |
|----|-----------|---------|
| **G-10** | Control has **primary qualifiers** absent from evidence. Primary qualifiers define WHAT/WHO/WHERE, not HOW OFTEN or HOW EXACTLY. | Control: "FIPS validated encryption" / Evidence: "Data shall be encrypted" |
| **G-11** | Control requires static ARTIFACT but evidence only mandates dynamic ACTIVITY | Control: "Maintain asset inventory" / Evidence: "Track and monitor assets" |
| **G-16** | Control requires operational characteristics (how something is configured/managed) but evidence only mandates presence/use. If control has qualifiers like "automatically", "configured to", "default", "hardened", "rotated", "on insert", those must appear in evidence. | Control: "Auto-update signatures" / Evidence: "Install antivirus". Control: "Firewall configured to deny inbound by default" / Evidence: "Enable firewall" |

**Primary Qualifiers (G-10 blocks if missing):**
- Domain: FIPS, authenticated, credentialed, tamper-evident, immutable
- Audience: third-party, privileged, external
- Scope: production, cardholder data, CUI, PII (specific data types)
- Specific named mechanisms: SCA tool, SIEM, IPAM, MDM, CSPM

**Secondary Qualifiers (DO NOT block—use MAPPED if core mandate exists):**
- Frequencies: daily, weekly, monthly, annually, quarterly
- Numeric thresholds: "within 30 days", "at least 12 months"
- Configuration details: "deny by default", "centrally managed"
- Review/update cadences: "reviewed annually", "updated periodically"

**The Core Mandate Test**: If the policy mandates the ARTIFACT or MECHANISM, and the control adds a frequency or operational detail, the policy satisfies the control at the governance level. Frequency gaps are implementation details, not policy failures.
```

### Additional Change: Move Qualifier Gap Rule to G-10 Section

**ADD after the G-10 table (new lines ~188-200):**

```markdown
**Qualifier Gap Examples (MAPPED, not NO_MATCH):**

| Control | Policy Says | Decision | Why |
|---------|-------------|----------|-----|
| "Asset inventory reviewed annually" | "Asset inventory shall be maintained" | **MAPPED** | Core artifact mandated; annual is secondary |
| "Patches installed within 30 days" | "Security patches shall be applied" | **MAPPED** | Core activity mandated; timing is secondary |
| "Logs reviewed weekly" | "Audit logs shall be reviewed" | **MAPPED** | Core activity mandated; frequency is secondary |
| "Anti-malware centrally managed" | "Anti-malware shall be deployed and updated" | **MAPPED** | Core mechanism mandated; "centrally" is operational detail |
| "Discovery tool runs daily" | "Automated discovery tool implemented" | **MAPPED** | Core mechanism mandated; "daily" is secondary |

**Counter-examples (still NO_MATCH):**

| Control | Policy Says | Decision | Why |
|---------|-------------|----------|-----|
| "FIPS-validated encryption" | "Data shall be encrypted" | **NO_MATCH** | FIPS is primary qualifier (standard compliance) |
| "Third-party penetration test" | "Penetration tests conducted" | **NO_MATCH** | "Third-party" is primary qualifier (independence) |
| "CUI inventory maintained" | "Asset inventory maintained" | **NO_MATCH** | CUI is primary qualifier (specific data type) |
```

### Delete Conflicting Language

**REMOVE from line 186:**
```markdown
~~**Hard qualifiers requiring explicit match:** authenticated, internal, external, privileged, production, FIPS, credentialed, specific log fields, numeric frequencies/retention periods~~
```

**REPLACE with:**
```markdown
**See Primary vs Secondary Qualifiers above for what blocks vs what doesn't.**
```

---

## Priority 2: Convert PARTIAL scope_gap → MAPPED (Est. +2-3pp recall)

### Problem
18 PARTIAL decisions, 15 are `scope_gap`. The LLM correctly finds binding evidence but downgrades because scope is limited.

Examples:
- "Exit strategies for cloud providers" (not all vendors) → PARTIAL
- "Acknowledgment at onboarding" (not annually) → PARTIAL

### Root Cause
The current PARTIAL definition (lines 259-265) encourages scope_gap for any subset limitation.

### Solution: Redefine When scope_gap Applies

**REPLACE lines 259-278:**

```markdown
### PARTIAL

Return **PARTIAL** only for **material policy-level gaps** that would require a policy rewrite to fix:

| Gap Type | Use When | Do NOT Use When |
|----------|----------|-----------------|
| `scope_gap` | Policy explicitly excludes required scope: "Internal systems only" when control requires external. Policy says "does not apply to X" where X is required. | Policy covers a subset but doesn't exclude others. Policy covers "cloud vendors" for a control about "all vendors"—cloud IS a vendor. |
| `third_party_gap` | Control requires vendor action, policy only governs internal. | Policy governs a vendor subset (cloud providers vs all vendors). |
| `ownership_gap` | Control requires explicit accountability assignment, policy is silent on ownership. | |
| `contradiction` | Policy actively contradicts control requirement. | |

**The Subset Rule**: If policy mandates behavior for a SUBSET of the control's scope, and that subset is INCLUDED in (not excluded from) the control's scope → **MAPPED**.

- "Exit strategies for cloud providers" → Control: "Exit strategies for suppliers" → Cloud providers ARE suppliers → **MAPPED**
- "MFA for privileged accounts" → Control: "MFA for all accounts" → Privileged IS a subset → **MAPPED** (not scope_gap)
- "Acknowledgment at onboarding" → Control: "Acknowledgment at onboarding and annually" → Onboarding IS part of the requirement → **MAPPED** (frequency gap, not scope gap)

**PARTIAL is rare.** Most gaps are either:
- Missing core mandate → NO_MATCH
- Secondary qualifier gap → MAPPED
- Legitimate subset → MAPPED

Reserve PARTIAL for explicit exclusions or contradictions.
```

---

## Priority 3: Refine G-17 (Input vs Program) (Est. +1-2pp recall)

### Problem
16 G-17 FNs. Some are legitimate (report incidents ≠ IR plan), but others are over-applied.

Over-rejected examples:
- "Security team assigned" rejected because ISM is "a component"
- "Unauthorized software process" rejected because "facilitates" is utility

### Solution: Add Policy-Level Sufficiency Test to G-17

**REPLACE line 157:**

```markdown
| **G-17** | Control requires a formal program/plan/procedure but evidence only describes an input or component of that program. Reporting INTO a program ≠ the program itself. Policy existence ≠ training delivery. **Exception**: If the component IS the policy-level requirement (governance, not operations), it may satisfy. | Control: "Incident response plan" / Evidence: "Users must report incidents" (input only). Control: "Security awareness training provided" / Evidence: Policy document exists (existence ≠ delivery). **But**: Control: "Security team assigned" / Evidence: "ISM responsible for security policies" → MAPPED (role assignment IS policy-level). |
```

**ADD after G-17 in the table (new row):**

```markdown
| **G-17 Policy Test** | Before applying G-17, ask: "Is this control asking for a PROGRAM (operations) or a GOVERNANCE requirement (policy)?" If governance, the policy component may suffice. | Control: "Risk management program with documented procedures" → Needs program (G-17 applies). Control: "Roles and responsibilities defined" → Governance (policy assignment suffices). |
```

---

## Priority 4: Add IR-8 for Mechanism Subsumption (Est. +1pp recall)

### Problem
13 G-4 FNs where the mechanism "differs" but the policy's mechanism arguably INCLUDES the control's mechanism.

Examples:
- "Vulnerability scanning" arguably includes SCA
- "Network equipment access restricted" arguably includes network jacks

### Solution: Add New Interpretive Rule

**ADD to IR table (after IR-7, line 225):**

```markdown
| **IR-8** | **Mechanism Subsumption** | Policy mandates a broader mechanism that necessarily includes the control's specific mechanism. The broader mechanism cannot be implemented without covering the specific. | Control specifies a DIFFERENT mechanism (not a subset). Or control's specific mechanism could be excluded from the broader implementation. |
```

**ADD examples section after IR table:**

```markdown
**IR-8 Examples:**

| Control | Policy | Apply IR-8? | Reasoning |
|---------|--------|-------------|-----------|
| "Restrict access to network jacks" | "Restrict access to network equipment" | **Yes** | Network jacks are network equipment. Cannot restrict equipment without restricting jacks. |
| "Software Composition Analysis" | "Vulnerability scanning" | **No** | SCA is a specific technique; general vuln scanning could exclude dependency analysis. |
| "Cloud security posture management" | "Vulnerability scanning" | **No** | CSPM is configuration monitoring, not vulnerability scanning. Different mechanism. |
| "Anti-malware centrally managed" | "Anti-malware deployed" | **No** | Deployment doesn't require central management. Different operational model. |
```

---

## Priority 5: Strengthen Soft Blocker Exception (Minor)

### Problem
Some FNs cite "should" as blocker when binding language exists elsewhere in the same section.

### Solution: Make the Exception More Prominent

**REPLACE lines 108-111:**

```markdown
- **Soft blockers** (context-dependent): should, where applicable, as appropriate
  - **CRITICAL**: Before rejecting for "should", check if the CORE OBJECTIVE has binding language (must/shall) elsewhere in the SAME SECTION.
  - If "should" modifies only the METHOD (not the objective), core mandate may still satisfy.
  - Example: "Code must be reviewed. Automation should be used where possible." → The review mandate is binding; "should" on automation doesn't block.
  - Example: "Security controls should be implemented" → Check same section for "Access must be restricted" or similar binding statement on the same topic.
```

---

## Summary of Changes

### System Prompt Changes

| Section | Lines | Change Type | Est. Impact |
|---------|-------|-------------|-------------|
| G-10 definition | 180-186 | REPLACE: Primary vs Secondary qualifiers | +5-7pp |
| After G-10 | NEW ~188-200 | ADD: Qualifier Gap Examples | (part of above) |
| PARTIAL definition | 259-278 | REPLACE: Subset Rule | +2-3pp |
| G-17 definition | 157 | REPLACE: Policy-level test | +1-2pp |
| IR table | 225 | ADD: IR-8 Mechanism Subsumption | +1pp |
| Soft blockers | 108-111 | REPLACE: Stronger exception | +0.5pp |

**Total Estimated Impact**: +9.5-13.5pp recall → **82-86% recall**

### Expected Precision Impact

| Change | Precision Risk | Mitigation |
|--------|---------------|------------|
| Relax G-10 frequencies | Medium (+10-15 FPs) | Stage 3 verification catches operational gaps |
| PARTIAL→MAPPED subsets | Low (+3-5 FPs) | Subset logic is sound; explicit exclusions still NO_MATCH |
| Refine G-17 | Low (+2-3 FPs) | Policy-level test preserves input vs program distinction |
| IR-8 subsumption | Low (+1-2 FPs) | Conservative examples; different mechanisms still blocked |

**Net Precision Impact**: -5 to -8pp (from ~35% to ~27-30%)

**Why This Is Acceptable**: Stage 3 verification will filter FPs. The goal is to send more true positives to Stage 3, accepting higher FP rate at Stage 2.

---

## User Prompt Changes

**ADD to `<hard_rules>` section:**

```markdown
- **Frequency gaps are not blockers.** If policy mandates the artifact/mechanism but lacks frequency (annual, daily, weekly), return MAPPED.
- **Subset scope is not scope_gap.** If policy covers a subset (cloud vendors) for a control about a superset (all vendors), return MAPPED—cloud vendors ARE vendors.
```

---

## Full Diff: Key Sections

### G-10 Section (BEFORE)

```markdown
| **G-10** | Control has hard qualifiers absent from evidence (no inference allowed) | Control: "FIPS validated encryption" / Evidence: "Data shall be encrypted" |

**Hard qualifiers requiring explicit match:** authenticated, internal, external, privileged, production, FIPS, credentialed, specific log fields, numeric frequencies/retention periods
```

### G-10 Section (AFTER)

```markdown
| **G-10** | Control has **primary qualifiers** absent from evidence. Primary qualifiers define WHAT/WHO/WHERE, not HOW OFTEN or HOW EXACTLY. | Control: "FIPS validated encryption" / Evidence: "Data shall be encrypted" |

**Primary Qualifiers (G-10 blocks if missing):**
- Domain: FIPS, authenticated, credentialed, tamper-evident, immutable
- Audience: third-party, privileged, external
- Scope: production, cardholder data, CUI, PII (specific data types)
- Specific named mechanisms: SCA tool, SIEM, IPAM, MDM, CSPM

**Secondary Qualifiers (DO NOT block—use MAPPED if core mandate exists):**
- Frequencies: daily, weekly, monthly, annually, quarterly
- Numeric thresholds: "within 30 days", "at least 12 months"
- Configuration details: "deny by default", "centrally managed"
- Review/update cadences: "reviewed annually", "updated periodically"

**Qualifier Gap Examples (MAPPED, not NO_MATCH):**

| Control | Policy Says | Decision | Why |
|---------|-------------|----------|-----|
| "Asset inventory reviewed annually" | "Asset inventory shall be maintained" | **MAPPED** | Core artifact mandated; annual is secondary |
| "Patches installed within 30 days" | "Security patches shall be applied" | **MAPPED** | Core activity mandated; timing is secondary |
| "Anti-malware centrally managed" | "Anti-malware shall be deployed" | **MAPPED** | Core mechanism mandated; "centrally" is operational detail |

**Counter-examples (still NO_MATCH):**

| Control | Policy Says | Decision | Why |
|---------|-------------|----------|-----|
| "FIPS-validated encryption" | "Data shall be encrypted" | **NO_MATCH** | FIPS is primary (standard compliance) |
| "Third-party penetration test" | "Penetration tests conducted" | **NO_MATCH** | "Third-party" is primary (independence) |
```

---

## Testing Recommendation

Before full experiment:
1. Run on 5 documents that had high FN rates in Exp 7
2. Manually verify the recovered FNs are legitimate
3. Sample 20 new MAPPEDs to estimate FP increase
4. Adjust if FP rate exceeds 75%

---

## Files to Create

New prompt directory: `prompts/control_centric_false_negatives_take3/`
- Copy from `take2`
- Apply changes above
- Run experiment_8
