# Flipping the Scoring Direction: From Page Coverage to Control Coverage

## Date: 2025-12-20

## Executive Summary

We implemented a fundamental change to how ColModernVBERT similarity scores are computed. The original approach measured "how much of the page looks like this control" (page coverage). The new approach measures "how much of this control is supported by the page" (control coverage). We also implemented a bidirectional mode that combines both.

This change addresses a key limitation: the original scoring was dominated by page noise, producing a compressed score range (0.12-0.40) where even perfect semantic matches only scored ~38% of theoretical maximum.

---

## The Problem: Why Original Scoring Produced Low, Compressed Scores

### How ColBERT-Style Scoring Works

ColBERT uses "late interaction" scoring via MaxSim:
1. Both query and document are encoded into sequences of token embeddings
2. For each query token, find the maximum similarity to any document token
3. Sum these maximum similarities across all query tokens

The key question is: **which side is the "query" and which is the "document"?**

### Original Approach: Page as Query (Page Coverage)

In our original implementation:
- **Query**: Page token embeddings (hundreds of tokens from the page image)
- **Document**: Control token embeddings (tens of tokens from control description)

The scoring formula was:
```
score(page, control) = Σ over page_tokens [ max over control_tokens ( sim(page_token, control_token) ) ]
```

**What this measures**: "For each part of the page, how well does any part of the control match it?"

**The problem**: A policy page contains much more than any single control could ever match:
- Headers, footers, logos
- Table of contents
- General policy boilerplate ("This policy applies to all employees...")
- Company-specific information
- Procedural details unrelated to any specific control
- Formatting and structural elements

Even a **perfect** semantic match between control and page content only covers perhaps 30-40% of the page's tokens. The other 60-70% of page tokens still contribute to the denominator (via self-similarity normalization), dragging down the normalized score.

### Why the Score Range Was Compressed (0.12 - 0.40)

**Floor (~0.12)**: Every page shares generic policy language that appears in every control description. Words like "organization", "security", "procedures", "maintain", "ensure" create a baseline similarity even for completely unrelated controls.

**Ceiling (~0.40)**: Even when a control perfectly matches a section of the page, most page tokens have no corresponding control tokens. When we normalize by page self-similarity, we're dividing by the total information content of the page, most of which is irrelevant to any single control.

**Result**: A 0.28 score range (0.40 - 0.12) to distinguish between 779 controls. This is why we needed such a low threshold (0.20-0.22) to capture all ground truth controls.

---

## The Solution: Control as Query (Control Coverage)

### Flipping the Direction

In the new approach:
- **Query**: Control token embeddings (the control description)
- **Document**: Page token embeddings (the page image)

The scoring formula becomes:
```
score(page, control) = Σ over control_tokens [ max over page_tokens ( sim(control_token, page_token) ) ]
```

**What this measures**: "For each concept in the control, is there supporting evidence somewhere on the page?"

### Why This Should Improve Discrimination

**Controls are short and specific**: A control description is typically 50-200 words containing specific concepts like:
- "asset inventory"
- "encryption key rotation"
- "PowerShell constrained language mode"
- "incident response procedures"

**Each control token must find a match**: With control coverage, every token in the control description needs to find its best match somewhere on the page. If the page doesn't contain content related to the control, even generic tokens won't score well because they're competing against the full page content.

**Boilerplate no longer inflates scores**: In page coverage mode, page boilerplate tokens each find matches in control descriptions (generic policy language). In control coverage mode, control tokens that match boilerplate will score similarly across all pages, providing no discrimination. But specific control tokens will only score highly against pages that actually contain that content.

### Expected Score Behavior

**For semantically-related pairs**: A control about "asset inventory" should score highly against an Asset Management Policy because:
- "asset" tokens find strong matches in asset management content
- "inventory" tokens find strong matches in inventory sections
- "register" tokens find strong matches in asset register descriptions

**For semantically-unrelated pairs**: A control about "asset inventory" should score poorly against an Incident Response Plan because:
- "asset" tokens only find weak matches in generic mentions
- "inventory" tokens find no good matches
- "register" tokens find no good matches

**The key difference**: Control coverage doesn't get fooled by page noise. It only scores highly when the **specific concepts in the control** are supported by the page.

---

## Normalization: Control Self-Similarity

### Original: Page Self-Similarity

We normalized page coverage scores by the page's self-similarity:
```
normalized = raw_score / page_self_similarity
```

This answered: "What fraction of the page's information content is captured by this control?"

### New: Control Self-Similarity

For control coverage, we normalize by the control's self-similarity:
```
normalized = raw_score / control_self_similarity
```

This answers: "What fraction of the control's concepts are supported by this page?"

**Key advantage**: Control self-similarity can be precomputed once (controls are fixed), making this computationally efficient.

### Expected Score Range

With control coverage normalization:
- **1.0** = Every concept in the control is fully supported by page content
- **0.0** = No concepts in the control are supported
- **High scores (0.7+)** should indicate strong semantic alignment
- **Low scores (<0.3)** should indicate weak or no semantic relationship

The useful score range should be wider than 0.12-0.40, making threshold selection easier.

---

## Bidirectional Scoring: Best of Both Worlds

### The Insight

Both directions capture different aspects of relevance:
- **Page coverage**: Does the page discuss this control's domain?
- **Control coverage**: Does the control's specific requirements appear on the page?

A strong match should score well in **both** directions:
- High page coverage: The page is about this topic
- High control coverage: The specific control requirements are addressed

### Harmonic Mean

We combine both scores using harmonic mean:
```
bidirectional = 2 * (page_coverage * control_coverage) / (page_coverage + control_coverage)
```

**Why harmonic mean?** It penalizes cases where one score is high but the other is low. Both scores must be reasonably high for the combined score to be high.

**Expected behavior**:
- Generic control + generic page language → Medium page coverage, low control coverage → Low bidirectional
- Specific control + relevant page → High page coverage, high control coverage → High bidirectional
- Specific control + irrelevant page → Low both → Low bidirectional

---

## Implications for the Semantic vs Compliance Problem

### The Original Problem

Configuration Management controls (Windows hardening settings like "PowerShell Constrained Language Mode") were associated with Change Management Policy for compliance reasons, but the policy document contains no semantic content about Windows configuration.

With page coverage scoring:
- The Change Management Policy page contains lots of generic change management language
- This generic language weakly matches tokens in any control description
- Result: Even unrelated controls score 0.20+ against Change Management Policy
- The semantic mismatch controls (DCF-935 etc.) score just barely above the floor

### How Control Coverage Might Help

With control coverage scoring:
- "PowerShell Constrained Language Mode" contains specific tokens: "PowerShell", "constrained", "language", "mode"
- These tokens must find matches on the Change Management Policy pages
- If the policy doesn't mention PowerShell, those tokens get weak matches
- Result: The control scores poorly because its specific requirements aren't addressed

**Expected outcome**: Controls that are semantically unrelated to a document should score much lower with control coverage, potentially allowing higher thresholds.

### What It Won't Solve

Control coverage doesn't change the fundamental tension between:
- **Semantic relevance**: What the document actually discusses
- **Compliance mapping**: What controls the document can satisfy for audit purposes

If a control really has no semantic relationship to its mapped document, no amount of scoring improvement will make it retrievable. The question is whether better scoring can:
1. Improve the usable threshold for semantically-related controls
2. Make the distinction clearer between semantic matches and mismatches
3. Reduce candidate set sizes while maintaining recall for semantically-retrievable controls

---

## Three Scoring Modes

### PAGE_COVERAGE (Original)
- Direction: Sum over page tokens, max over control tokens
- Normalization: Page self-similarity
- Question answered: "How much of the page looks like this control?"
- Use case: Backwards compatibility, baseline comparison

### CONTROL_COVERAGE (New)
- Direction: Sum over control tokens, max over page tokens
- Normalization: Control self-similarity (precomputed)
- Question answered: "How much of this control is supported by the page?"
- Use case: Testing flipped direction hypothesis

### BIDIRECTIONAL (Recommended)
- Computation: Harmonic mean of page coverage and control coverage
- Question answered: "Is this a strong match in both directions?"
- Use case: Production scoring, should have best discrimination

---

## Evaluation Plan

1. **Run ground truth analysis with each scoring mode** on template_policies experiment
2. **Compare score distributions**:
   - What is the min/max/median score for GT controls?
   - Is the useful range wider?
3. **Determine optimal thresholds** for each mode:
   - What threshold gives 100% GT recall?
   - How does candidate set size compare at equivalent recall levels?
4. **Analyze bottleneck controls**:
   - Are the same controls bottlenecks across modes?
   - Do semantically-mismatched controls score differently?

---

## References

- Original ColBERT paper: Khattab & Zaharia, "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT" (2020)
- ColModernVBERT: Multimodal adaptation for image-text late interaction
- Previous research: `colmodernvbert_score_normalization.md` documents the original scoring approach and its limitations
