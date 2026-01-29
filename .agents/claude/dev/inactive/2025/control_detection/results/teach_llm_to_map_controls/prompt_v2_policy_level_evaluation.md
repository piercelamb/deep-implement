# Prompt V2: Policy-Level Evaluation

**Date:** 2025-12-26
**Prompt Location:** `prompts/control_centric_expanded/system`

---

## Problem Discovery

### Initial Expanded Prompt Results

We created an extensive system prompt with detailed evaluation criteria. Expected it to reduce false positives by being more rigorous. Instead:

| Metric | Before (Simple Prompt) | After (Expanded Prompt) |
|--------|----------------------|------------------------|
| Predicted | 84 | 174 |
| True Positives | 6 | 7 |
| False Positives | 78 | 167 |
| Precision | 7.1% | 4.0% |
| Recall | 75.0% | 87.5% |

**The expanded prompt made things worse, not better.**

### Root Cause Analysis

1. **PARTIAL as an escape hatch**: The expanded prompt introduced a three-way decision (MAPPED/PARTIAL/NO_MATCH). The LLM used PARTIAL for any tangentially related content.
   - 44 MAPPED decisions
   - 130 PARTIAL decisions (almost all false positives)

2. **Semantic/Procedural Equivalence encouraged weak matches**: The prompt told the LLM to look for "different words but same outcome" and "procedures that functionally achieve the goal" - too permissive.

3. **Missing "when unsure, prefer NO_MATCH" guidance**: The old binary prompt had "When unsure, prefer false (precision over recall)". The new prompt lacked this.

4. **Gap categories gave vocabulary to justify weak matches**: 10 specific gap types let the LLM say "PARTIAL because [gap]" instead of "NO_MATCH".

---

## Fix 1: PARTIAL No Longer Counts as Prediction

Changed `addresses_control` property in `control_centric_decider.py`:

```python
# Before
@property
def addresses_control(self) -> bool:
    """Return True if decision is MAPPED or PARTIAL (backwards compatibility)."""
    return self.decision in (Decision.MAPPED, Decision.PARTIAL)

# After
@property
def addresses_control(self) -> bool:
    """Return True only if decision is MAPPED (fully addresses the control)."""
    return self.decision == Decision.MAPPED
```

**Result:** Only MAPPED decisions count toward precision/recall. PARTIAL is still recorded for analysis but doesn't inflate predictions.

---

## Fix 2: GRC Expert Feedback Integration

### The Insight

GRC expert reviewed the prompt and noted:

> "The doc assumes policies may sometimes contain procedural or technical detail, whereas it's been our practice to increasingly push those specifics into DCFs and Evidence Guidance - we generally only offer guidance at the policy level, not the procedural, standard or supporting document level."

### The Document Hierarchy

In mature GRC programs:

```
┌─────────────────────────────────────────────────────────────────┐
│ POLICY (What must be done - high-level mandate)                 │
│   "Access to systems must be controlled and monitored"          │
├─────────────────────────────────────────────────────────────────┤
│ STANDARD (How it must be done - technical requirements)         │
│   "MFA required using TOTP or hardware tokens"                  │
├─────────────────────────────────────────────────────────────────┤
│ PROCEDURE (Step-by-step implementation)                         │
│   "1. Submit access request via Jira 2. Manager approves..."    │
├─────────────────────────────────────────────────────────────────┤
│ DCF CONTROL (Specific measurable requirement)                   │
│   "DCF-342: Multi-factor authentication is required..."         │
├─────────────────────────────────────────────────────────────────┤
│ EVIDENCE GUIDANCE (How we prove compliance)                     │
│   "Screenshot of MFA configuration, access logs showing..."     │
└─────────────────────────────────────────────────────────────────┘
```

### The Problem with V1 Prompt

The V1 prompt penalized policies for not containing information that **correctly lives elsewhere**:
- Technical parameters (AES-256, TLS 1.2, 14-char passwords)
- Step-by-step procedures
- Specific timelines (quarterly, within 24 hours)
- Evidence artifacts (logs, screenshots)

---

## Fix 3: System Prompt Rewrite

### Key Changes

| Aspect | V1 (Expanded) | V2 (Policy-Level) |
|--------|---------------|-------------------|
| **Objective** | "sufficient implementation detail (roles, timing, procedures, artifacts, technical specs)" | "establishes the organizational mandate" |
| **Document Hierarchy** | Not mentioned | Explicit section explaining Policy → Standard → Procedure → Control → Evidence |
| **Phase 0 Profile** | 11 components including timing, artifacts, technical specs | 6 components: mandate, scope, ownership, third-party, regulatory trigger |
| **Phase 3** | "Evidence & Technical Requirements" with checks for artifacts, specs, automation | "Policy-Level Requirements Check" with "What NOT to Penalize" section |
| **MAPPED Criteria** | Required ALL: timing, ownership, artifacts, technical requirements, approvals, verification | Requires: mandate + scope + ownership + no contradictions |
| **PARTIAL Criteria** | Missing: timing, technical specs, artifacts, verification | Only policy-level gaps: scope, third-party, ownership, contradiction |
| **Gap Categories** | 10 gaps | 4 policy-level gaps. Explicit list of gaps NOT to report |
| **Decision Tree** | 7 steps with implementation detail checks | 5 steps: subject matter → mandate → scope → ownership → contradiction |
| **Length** | 400 lines | ~290 lines |

### New Core Question

**V1:** "Does the policy fully specify how to implement this control?"

**V2:** "Does the policy establish the organizational mandate that enables this control to be implemented?"

### New MAPPED Criteria

```markdown
Return **MAPPED** if ALL of the following are true:
1. The policy **mandates** the behavior/outcome the control requires
2. The mandate applies to the **correct scope** of assets/entities
3. **Ownership/responsibility** is assigned or clearly implied
4. The policy does NOT contradict the control's requirements

Note: Technical details, procedures, and evidence requirements are NOT required for MAPPED.
```

### Gap Categories (Policy-Level Only)

**Valid gaps to report:**
- `scope_gap` - Policy excludes assets the control requires
- `third_party_gap` - Policy is internal-only when control requires vendor coverage
- `ownership_gap` - No clear accountability for the mandate
- `contradiction` - Policy conflicts with control requirements

**Invalid gaps (do NOT report - they belong elsewhere):**
- `technical_gap` - Belongs in standards
- `frequency_gap` - Belongs in procedures/controls
- `evidence_gap` - Belongs in Evidence Guidance
- `specificity_gap` - Belongs in procedure documents

### New Decision Tree

```
1. Does the policy address the same subject matter as the control?
   NO  → NO_MATCH
   YES → Continue

2. Does the policy mandate (not just mention) the required behavior?
   NO  → NO_MATCH
   YES → Continue

3. Does the policy scope include the control's target assets/entities?
   NO  → NO_MATCH (scope gap)
   YES → Continue

4. Is ownership/responsibility assigned or implied?
   NO  → Note as minor consideration (can still be MAPPED)
   YES → Continue

5. Does the policy contradict the control's requirements?
   YES → NO_MATCH
   NO  → MAPPED
```

---

## Analysis Script Created

Created `analyze_ground_truth.py` to debug what happened with ground truth controls:

```bash
python ai_services/scripts/experiments/control_detection/analyze_ground_truth.py <row> <timestamp>

# Example:
python analyze_ground_truth.py 0 20251226_150103
```

Output shows:
- Which GT controls are in dcf_controls.csv
- Which were sent to LLM
- Breakdown by decision (MAPPED/PARTIAL/NO_MATCH)
- Detailed reasoning for each

---

## Expected Impact

| Metric | V1 Expanded | V2 Policy-Level (Expected) |
|--------|-------------|---------------------------|
| False PARTIAL (technical/procedural gaps) | High (130) | Lower (should be policy-level only) |
| False NO_MATCH (missing procedures) | Some | Lower (won't penalize for missing procedures) |
| True MAPPED | ~5-7/8 | Should increase |
| Precision | ~12% | Should improve |

---

## Files Modified

1. **`prompts/control_centric_expanded/system`** - Complete rewrite with policy-level evaluation
2. **`control_centric_decider.py`** - Changed `addresses_control` to only count MAPPED
3. **`analyze_ground_truth.py`** - New script for debugging GT control decisions

---

## Next Steps

1. Run experiment with V2 prompt on same document
2. Compare MAPPED/PARTIAL/NO_MATCH distributions
3. Analyze GT control decisions with `analyze_ground_truth.py`
4. Iterate on prompt if needed based on results
