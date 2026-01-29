# Experiment 4 vs Experiment 5 Comparison

## Overview

| Aspect | Experiment 4 | Experiment 5 | Delta |
|--------|--------------|--------------|-------|
| **Prompts** | `control_centric_expanded` | `control_centric_false_negatives` | New IR-1 to IR-10 rules |
| **Documents** | 36 | 37 | +1 |
| **GT Controls** | 582 | 585 | +3 |

## Primary Metrics

| Metric | Exp 4 | Exp 5 | Delta | Change |
|--------|-------|-------|-------|--------|
| **Recall** | 86.1% | 94.0% | **+7.9%** | Improved |
| **Precision** | 18.3% | 9.4% | **-8.9%** | Degraded |
| **F1** | 30.2% | 17.1% | **-13.1%** | Degraded |

## Detailed Counts

| Count | Exp 4 | Exp 5 | Delta | Change |
|-------|-------|-------|-------|--------|
| **Predicted** | 2,741 | 5,837 | +3,096 | +113% |
| **True Positives** | 501 | 550 | +49 | +9.8% |
| **False Positives** | 2,240 | 5,287 | +3,047 | +136% |
| **False Negatives** | 81 | 35 | **-46** | **-56.8%** |

## Retrieval Stage (unchanged)

| Metric | Exp 4 | Exp 5 |
|--------|-------|-------|
| Embedding Recall | 98.5% | 98.3% |
| Sent to LLM | 97.1% | 96.9% |

## Analysis

### What Worked: False Negative Reduction

The primary goal of the `control_centric_false_negatives` prompts was achieved:
- **False negatives dropped 56.8%** (81 → 35)
- **Recall improved 7.9%** (86.1% → 94.0%)
- The Interpretive Rules (IR-1 to IR-10) and Pre-Rejection Recovery Checklist successfully prevented the LLM from rejecting valid mappings

### What Broke: Precision Collapse

The prompts swung too far in the opposite direction:
- **Predictions more than doubled** (2,741 → 5,837)
- **False positives increased 136%** (2,240 → 5,287)
- **Precision dropped 48.6%** relative (18.3% → 9.4%)

### Root Cause Hypothesis

The Interpretive Rules are being applied too liberally:
1. **IR-1 (Hierarchical Scope)**: May be matching overly broad policy scope to specific controls
2. **IR-2 (Tech→Abstract)**: Accepting abstract mandates when specific tech requirements aren't met
3. **IR-4 (Governance→Procedure)**: Accepting governance statements as full control coverage
4. **IR-8 (Binding Inheritance)**: Over-interpreting binding preambles

### Recommendations

1. **Add specificity constraints** to IR rules - require stronger evidence for MAPPED
2. **Raise the bar for MAPPED** - currently the prompt says "if policy mandates Strategic What/Who, it maps" which may be too permissive
3. **Consider confidence-based filtering** - only count HIGH confidence as MAPPED
4. **Analyze false positives** - examine which IR rules are being cited for incorrect MAPPEDs

## Conclusion

The experiment proved the concept: the Interpretive Rules can reduce false negatives. However, the current implementation trades too much precision for recall. The prompts need calibration to find a better balance point.

**Next step**: Analyze false positive patterns to identify which IR rules need tightening.
