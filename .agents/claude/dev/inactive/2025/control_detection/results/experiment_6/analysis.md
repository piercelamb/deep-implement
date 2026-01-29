# Experiment 6: False-Positive Focused Prompt Tuning

**Date**: 2025-12-31
**Experiment ID**: `experiment_6`
**Run Timestamp**: `20251231_201430`

---

## Executive Summary

Experiment 6 represents a **major breakthrough in precision** for the control-centric mapping pipeline. By replacing the permissive "false negative prevention" prompts with a strict "auditor skeptic" prompt design, we achieved:

| Metric | Before (Exp 5) | After (Exp 6) | Change |
|--------|----------------|---------------|--------|
| **Precision** | 9.4% | **48.9%** | **+420%** |
| **Recall** | 94.0% | 66.2% | -30% |
| **F1** | 17.1% | **56.2%** | **+229%** |
| **False Positives** | 5,287 | **267** | **-95%** |

This is the first experiment to achieve near-production-viable precision (~50%) while maintaining meaningful recall (66%). The precision/recall tradeoff is now in a workable range for downstream verification (Stage 3).

---

## Background: Why This Experiment

### The Problem

Experiments 3-5 explored the precision/recall tradeoff:
- **Exp 3-4**: Default prompts yielded ~17-18% precision with ~74-86% recall
- **Exp 5**: "False negative prevention" prompts (IR-1 to IR-10) achieved 94% recall but collapsed precision to 9.4%

The Interpretive Rules (IR-1 through IR-10) were designed to prevent false negatives by allowing the LLM to bridge gaps between abstract policy language and specific control requirements. However, they were applied too liberally, resulting in a 136% increase in false positives.

### The Hypothesis

The LLM was using the Interpretive Rules as a "rescue mission" rather than a "bridge." We hypothesized that reframing the prompt with:
1. **Skeptical default stance** ("NO_MATCH unless irrefutable")
2. **Strict guardrails** (G-1 through G-17) that gate IR application
3. **Explicit anti-patterns** to prevent mass mapping
4. **Binary confidence** (High = MAPPED, anything else = NO_MATCH)

...would restore precision while sacrificing some recall.

---

## Experimental Setup

### Configuration

```json
{
  "mode": "control_centric",
  "scoring_mode": "control_coverage",
  "score_threshold": 0.48,
  "model": "gemini-3-flash-preview",
  "prompts_dir": "control_centric_false_positive_additions2",
  "batch_strategy": "coherent",
  "max_calls_per_document": 50
}
```

### Dataset

| Metric | Value |
|--------|-------|
| Experiment | `template_policies_v2` |
| Documents evaluated | 17 |
| Ground truth controls | 385 |

**Note**: Experiment 6 evaluated 17 documents (vs 37 in Exp 5). This is due to different policy availability during the run. The per-document metrics are comparable.

### Prompt Changes: The "Strict Auditor" Approach

The new prompt (`control_centric_false_positive_additions2/system`) introduced several key changes:

#### 1. Role Reframing
**Before (Exp 5):**
> "You are an expert Security Compliance Analyst..."

**After (Exp 6):**
> "You are a **Strict External Auditor**. Your job is to audit a policy document against security controls. You are **skeptical by default**. Your default position is **NO_MATCH**."

#### 2. Golden Rule
New: "It is better to return **NO_MATCH** (a finding) than to falsely credit a control (a security risk). **Do not 'read between the lines.'**"

#### 3. Precision Guardrails (G-1 through G-17)
Added 17 explicit guardrails that **block mapping** when violated:

| Category | Guardrails |
|----------|------------|
| **Type Mismatch** | G-1 (Admin for Technical), G-2 (User rule for system), G-3 (Detection for Prevention), G-17 (Input for Program) |
| **Domain/Scope** | G-4 (Domain mismatch), G-5 (Scope limitation), G-6 (Vendor vs internal), G-7 (Audience mismatch), G-15 (Wrong artifact type) |
| **Lifecycle/Temporal** | G-8 (Wrong lifecycle phase), G-9 (Event-driven vs periodic) |
| **Qualifier/Artifact** | G-10 (Hard qualifiers), G-11 (Activity for Artifact), G-16 (Presence for Configuration) |
| **Evidence Quality** | G-12 (External reference only), G-13 (Risk assessment for implementation), G-14 (General for specific) |

#### 4. Gated Interpretive Rules
The IRs from Exp 5 were kept but **gated**:
> "Apply these rules ONLY if: 1. You have admissible, binding evidence, AND 2. No Precision Guardrail (G-1 through G-17) is violated"

#### 5. Binary Confidence
Eliminated medium/low confidence MAPPED:
> "Confidence is BINARY: High = MAPPED, Not High = NO_MATCH. There is no 'medium confidence MAPPED.'"

#### 6. Anti-Pattern Warnings
Explicit warnings against common over-mapping errors:
- "One Quote → Many Controls" anti-pattern
- "Mass Mapping" anti-pattern with realistic expectations (5-15 controls for typical policy)

---

## Results

### Aggregate Metrics

| Metric | Exp 5 | Exp 6 | Change | Direction |
|--------|-------|-------|--------|-----------|
| **Documents** | 37 | 17 | -20 | (subset) |
| **GT Controls** | 585 | 385 | -200 | (subset) |
| **Predicted** | 5,837 | **522** | -91% | Better |
| **True Positives** | 550 | **255** | -54% | Expected |
| **False Positives** | 5,287 | **267** | **-95%** | Much Better |
| **False Negatives** | 35 | **130** | +271% | Tradeoff |

### Precision/Recall/F1

| Metric | Exp 5 (Micro) | Exp 6 (Micro) | Change |
|--------|---------------|---------------|--------|
| **Precision** | 9.4% | **48.9%** | **+420%** |
| **Recall** | 94.0% | 66.2% | -30% |
| **F1** | 17.1% | **56.2%** | **+229%** |

### Retrieval Stage (Unchanged)

| Metric | Exp 5 | Exp 6 |
|--------|-------|-------|
| Embedding Recall | 98.3% | 98.7% |
| Top-K Recall | 96.9% | 96.9% |

The retrieval stage remains consistent, confirming the LLM prompt is the variable.

---

## Comparison Across All Experiments

| Exp | Mode | Prompt Focus | Precision | Recall | F1 | FPs |
|-----|------|--------------|-----------|--------|-----|-----|
| 1 | per-page | baseline | 42.0% | 34.3% | 37.7% | 325 |
| 2 | per-page | top-K=100 | 36.4% | 30.5% | 33.2% | 273 |
| 3 | control_centric | baseline | 17.4% | 73.9% | 28.2% | 2,171 |
| 4 | control_centric | clean GT | 18.3% | 86.1% | 30.2% | 2,240 |
| 5 | control_centric | **FN prevention** | 9.4% | **94.0%** | 17.1% | **5,287** |
| **6** | control_centric | **FP prevention** | **48.9%** | 66.2% | **56.2%** | **267** |

### Key Observations

1. **Precision Recovery**: Exp 6 achieves the highest precision of any control-centric experiment (48.9%), 2.6x higher than the baseline (18.3%).

2. **Acceptable Recall Tradeoff**: While recall dropped from 94% to 66%, this is a reasonable tradeoff for 5x precision improvement. 66% recall means we're capturing 2/3 of true mappings.

3. **Dramatic FP Reduction**: False positives dropped from 5,287 (Exp 5) to 267 (Exp 6)—a 95% reduction. This is the key success metric.

4. **F1 Score Peak**: The F1 score of 56.2% is the highest achieved, indicating the best balance of precision and recall.

---

## Analysis: What Worked

### 1. Skeptical Default Stance
Framing the LLM as a "strict auditor" who starts from "NO_MATCH" fundamentally changed its behavior. Instead of looking for reasons to map, it looks for reasons to reject.

### 2. Guardrails as Hard Blockers
The G-1 through G-17 guardrails provide **explicit rejection criteria**. The LLM can cite a specific guardrail when rejecting, making decisions more principled and less arbitrary.

### 3. Gated Interpretive Rules
By requiring admissible evidence AND no guardrail violations before applying IRs, we prevented the "rescue mission" behavior that caused FP explosion in Exp 5.

### 4. Binary Confidence
Eliminating "medium confidence MAPPED" forced the LLM to commit fully or reject. This removed the gray zone where false positives accumulated.

### 5. Anti-Pattern Awareness
Explicit warnings about "mass mapping" and "one quote → many controls" helped the LLM recognize when it was being too permissive.

### 6. Document Type Awareness (G-15)
The guardrail requiring artifact type match (e.g., Acceptable Use Policy ≠ Information Security Policy) prevented a common source of false positives.

---

## Analysis: What Could Be Better

### 1. Recall Drop
130 false negatives means 34% of true mappings are being missed. Some of these may be:
- Legitimate semantic equivalences being rejected by strict synonym matching
- Over-aggressive application of guardrails to borderline cases
- Document context not being fully utilized

### 2. Single-Document Testing During Development
The prompt was developed testing on 1-2 documents, which didn't reveal the full picture. The E2E run exposed behaviors that weren't apparent in small-scale tests.

### 3. Potential Over-Strictness
Some guardrails may be too aggressive:
- G-15 (artifact type) might reject valid "section-as-policy" patterns
- G-2 (user rule for system) might reject legitimate administrative controls

---

## Implications for Three-Stage Pipeline

This experiment validates the approach for the three-stage pipeline:

1. **Stage 2 Baseline**: 48.9% precision is a reasonable starting point for Stage 3 verification.

2. **Stage 3 Opportunity**: With ~267 FPs, Stage 3 has a clear target. If Stage 3 can reject 80% of FPs while preserving TPs, final precision would be ~80%.

3. **Manageable Verification Load**: 522 predicted controls across 17 documents means ~30 controls/doc sent to Stage 3, which is within budget.

4. **Quote Hallucination Signal**: Stage 3's first check—"Can the evidence quote be found in the document?"—should catch hallucinated evidence from Stage 2.

---

## Conclusions

### Experiment 6 Achievements

1. **First production-viable precision** (48.9%) in control-centric mode
2. **95% reduction in false positives** compared to Exp 5
3. **Highest F1 score** (56.2%) of all experiments
4. **Validated hypothesis**: Skeptical framing + guardrails > permissive IRs

### Recommended Next Steps

1. **Run Stage 3 Verification**: Apply the three-stage pipeline to see if precision can reach 80%+

2. **Analyze False Negatives**: Review the 130 FNs to identify patterns—are they:
   - Overly strict guardrail application?
   - Missing semantic equivalences?
   - True ambiguities in the ground truth?

3. **Guardrail Calibration**: Consider softening specific guardrails (G-15, G-2) based on FN analysis

4. **Scale Testing**: Run on full document set (37 docs) to confirm results at scale

---

## Appendix: Experiment Timeline

| Date | Exp | Focus | Key Finding |
|------|-----|-------|-------------|
| 2025-12-23 | 1 | Baseline (top-50) | 42% precision, 34% recall |
| 2025-12-23 | 2 | Top-100 | More candidates hurt LLM |
| 2025-12-27 | 3 | Control-centric baseline | 17% precision, 74% recall |
| 2025-12-27 | 4 | Clean ground truth | 18% precision, 86% recall |
| 2025-12-28 | 5 | FN prevention (IRs) | 9% precision, 94% recall - FP explosion |
| 2025-12-31 | **6** | **FP prevention (guardrails)** | **49% precision, 66% recall - breakthrough** |
