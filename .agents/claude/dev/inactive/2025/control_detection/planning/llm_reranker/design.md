# Multi-Dimensional LLM Reranker Design

## Date: 2025-12-20

## Confirmed Decisions

- **Model**: Gemini 2.0 Flash (fastest, cheapest, best vision)
- **Dimensions**: 5 dimensions (DIRECT_TOPIC, GOVERNANCE_SCOPE, EVIDENCE_POTENTIAL, COMPLIANCE_LINK, REGULATORY_MATCH)
- **Weights**: Compliance-heavy (55% compliance vs 15% semantic)

---

## Problem Statement

ColModernVBERT scores are excellent for **ranking** but terrible for **thresholding**:
- GT and non-GT score distributions overlap heavily
- At 100% recall, 97%+ of controls pass the threshold
- **Root cause**: Semantic similarity ≠ compliance association

### The Core Example

| Control | Policy | Semantic Overlap | Compliance Association |
|---------|--------|------------------|------------------------|
| "PowerShell Constrained Language Mode" | Change Management Policy | ZERO | HIGH (config changes need change control) |

An auditor would expect PowerShell settings to be governed by change management, but there's no text overlap. We need dimensions that capture this compliance reasoning.

---

## Multi-Dimensional Scoring Design

### The Five Dimensions

| Dimension | What It Measures | Why It Matters |
|-----------|------------------|----------------|
| **DIRECT_TOPIC** | Does the page text directly discuss this control's topic? | Captures semantic matches (what embeddings already do) |
| **GOVERNANCE_SCOPE** | Does this control fall under governance processes described on this page? | **KEY**: Captures "config changes need change control" reasoning |
| **EVIDENCE_POTENTIAL** | Could this page serve as evidence the control is implemented? | Practical relevance for auditors |
| **COMPLIANCE_LINK** | Would an auditor expect this control addressed by this document type? | **KEY**: Captures compliance framework associations |
| **REGULATORY_MATCH** | Does the page mention regulations/frameworks related to this control? | Bonus signal for framework-specific controls |

### Dimension Weights

Compliance dimensions weighted HIGHER than semantic:

```python
DIMENSION_WEIGHTS = {
    "direct_topic": 0.15,       # 15% - semantic (embeddings already capture)
    "governance_scope": 0.30,   # 30% - compliance reasoning (HIGH)
    "evidence_potential": 0.20, # 20% - practical relevance
    "compliance_link": 0.25,    # 25% - auditor expectation (HIGH)
    "regulatory_match": 0.10,   # 10% - regulatory bonus
}
# Total: 55% compliance-related, 15% semantic, 30% practical
```

### Example Scoring

**Case 1: PowerShell control in Change Management Policy (should KEEP)**
```
direct_topic: 2/10      (no semantic overlap)
governance_scope: 8/10  (config changes require change control)
evidence_potential: 3/10
compliance_link: 9/10   (auditors expect this association)
regulatory_match: 0/10

Final = 0.15*2 + 0.30*8 + 0.20*3 + 0.25*9 + 0.10*0 = 5.55/10 ✓ KEEP
```

**Case 2: Physical Security control in Software Dev Policy (should FILTER)**
```
direct_topic: 0/10
governance_scope: 1/10
evidence_potential: 0/10
compliance_link: 1/10
regulatory_match: 0/10

Final = 0.15*0 + 0.30*1 + 0.20*0 + 0.25*1 + 0.10*0 = 0.55/10 ✗ FILTER
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Broad Semantic Retrieval (ColModernVBERT)                          │
│   - Threshold: 0.20 (low, high recall)                                      │
│   - Output: ~500-600 candidate controls per page                            │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 2: Multi-Dimensional LLM Reranking (Gemini 2.0 Flash)                 │
│   - Input: Page image + batches of 50 control names/descriptions            │
│   - Process: Score each control on 5 dimensions (0-10 each)                 │
│   - Output: Weighted scores + reasoning                                     │
│   - Filter: Keep controls with weighted_score >= threshold                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Final Classification (Smart LLM - optional)                        │
│   - Input: Page image + ~50-100 filtered controls with full descriptions    │
│   - Output: Final control predictions with evidence                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Prompt Design

### System Prompt

```
You are a compliance auditor reviewing policy documents against security controls.

For each control, score it on 5 dimensions (0-10 scale):

1. DIRECT_TOPIC (0-10): Does this page directly discuss this control's specific topic?
   - 10: Page explicitly covers this exact control topic
   - 5: Page mentions related concepts
   - 0: No topical overlap whatsoever

2. GOVERNANCE_SCOPE (0-10): Does this control fall under governance processes described here?
   - 10: This control type is explicitly governed by processes on this page
   - 5: The governance process might apply to this control
   - 0: Governance processes here don't apply to this control type

3. EVIDENCE_POTENTIAL (0-10): Could this page serve as evidence the control is implemented?
   - 10: Page shows direct implementation or proof
   - 5: Page shows policy/process that supports the control
   - 0: Page provides no evidence value

4. COMPLIANCE_LINK (0-10): Would an auditor expect this control addressed by this document type?
   - 10: Standard compliance practice to find this control in this doc type
   - 5: Possible but not typical
   - 0: Would be unusual to find this control here

5. REGULATORY_MATCH (0-10): Does the page mention regulations/frameworks related to this control?
   - 10: Explicit mention of frameworks this control satisfies
   - 5: Related regulatory language
   - 0: No regulatory context
```

### User Prompt

```
Score each control against this policy page.

Controls to evaluate:
{controls_json}

Return JSON array:
[
  {
    "id": "control_id",
    "direct_topic": 0-10,
    "governance_scope": 0-10,
    "evidence_potential": 0-10,
    "compliance_link": 0-10,
    "regulatory_match": 0-10,
    "reasoning": "Brief explanation"
  },
  ...
]
```

---

## Implementation

### File Structure

```
ai_services/scripts/experiments/control_detection/llm_reranker/
├── __init__.py
├── dimensions.py          # Dimension definitions and weights
├── prompts.py             # Prompt templates
├── reranker.py            # MultiDimensionalReranker class
├── run_experiment.py      # Experiment runner
└── README.md              # Documentation
```

### Key Classes

```python
@dataclass(frozen=True, slots=True)
class DimensionScores:
    direct_topic: int          # 0-10
    governance_scope: int      # 0-10
    evidence_potential: int    # 0-10
    compliance_link: int       # 0-10
    regulatory_match: int      # 0-10

    def weighted_score(self, weights: dict[str, float]) -> float:
        return (
            weights["direct_topic"] * self.direct_topic +
            weights["governance_scope"] * self.governance_scope +
            weights["evidence_potential"] * self.evidence_potential +
            weights["compliance_link"] * self.compliance_link +
            weights["regulatory_match"] * self.regulatory_match
        )

@dataclass(frozen=True, slots=True)
class ControlScore:
    control_id: str
    scores: DimensionScores
    reasoning: str
    weighted_score: float

@dataclass
class RerankerConfig:
    model: str = "gemini-2.0-flash"
    batch_size: int = 50
    score_threshold: float = 3.0  # Tune based on results
    weights: dict = field(default_factory=lambda: {
        "direct_topic": 0.15,
        "governance_scope": 0.30,
        "evidence_potential": 0.20,
        "compliance_link": 0.25,
        "regulatory_match": 0.10,
    })
```

---

## Cost & Performance Estimates

| Metric | Estimate |
|--------|----------|
| Batch size | 50 controls |
| Batches per page | ~12 (for 600 candidates) |
| Cost per batch | ~$0.003 (Flash) |
| Cost per page | ~$0.036 |
| Latency per batch | ~1-2 seconds |
| Latency per page | ~15-25 seconds (sequential) or ~3-5 seconds (parallel) |

---

## Experiment Protocol

1. **Baseline**: ColModernVBERT @ 0.48 threshold
   - Current: 92% recall, 32% filtered

2. **Experiment A**: LLM reranker with equal weights
   - All dimensions at 0.20 weight
   - Measure: recall, candidate size, dimension distributions

3. **Experiment B**: LLM reranker with compliance-weighted dimensions
   - Weights as designed above
   - Compare: recall improvement on compliance-only controls

4. **Experiment C**: Threshold tuning
   - Test thresholds: 2.0, 3.0, 4.0, 5.0
   - Find optimal for 95%+ recall

5. **Analysis**: Per-dimension contribution
   - Correlation of each dimension with GT
   - Identify which dimensions discriminate best

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Recall @ top-100 | ≥ 95% |
| Candidate reduction | ≥ 50% (vs embedding-only at same recall) |
| Cost per page | ≤ $0.05 |
| Latency per page | ≤ 10 seconds (with parallelization) |

---

## Why This Approach Works

### The Key Insight

The GOVERNANCE_SCOPE and COMPLIANCE_LINK dimensions are specifically designed to capture what semantic embeddings miss:

| Scenario | DIRECT_TOPIC | GOVERNANCE_SCOPE | COMPLIANCE_LINK |
|----------|--------------|------------------|-----------------|
| PowerShell in Change Mgmt Policy | LOW (2) | HIGH (8) | HIGH (9) |
| Physical Security in SW Dev Policy | LOW (0) | LOW (1) | LOW (1) |

The LLM can reason: "Configuration changes should go through change control" even when there's no text overlap.

### Benefits of Multi-Dimensional Scoring

1. **Interpretability**: We know WHY a control scored high/low
2. **Tunability**: Adjust weights without changing prompts
3. **Debuggability**: If recall drops, check which dimension failed
4. **Analyzability**: Measure dimension correlations with GT

---

## Next Steps

1. Implement `dimensions.py` with dataclasses and weights
2. Implement `prompts.py` with system/user prompts
3. Implement `reranker.py` with Gemini Flash integration
4. Implement `run_experiment.py` for testing
5. Run experiments A, B, C on Asset Management Policy (Row 4)
6. Analyze results and tune weights/threshold
