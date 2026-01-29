# Rare Pattern Explosion Problem

## Summary

The map-reduce reason aggregator has a potential scalability issue: **rare patterns accumulate across rounds**, potentially causing prompt sizes to explode in later rounds.

## Background

Our aggregator uses a binary tree reduction:
```
Round 1: 37 policies → 19 outputs (18 pairs + 1 solo)
Round 2: 19 outputs → 10 outputs
Round 3: 10 → 5
Round 4: 5 → 3
Round 5: 3 → 2
Round 6: 2 → 1 (final)
```

Each `RoundOutput` contains:
- `universal_patterns`: Patterns observed in multiple original sources
- `rare_patterns`: Patterns observed in only one original source

## The Problem

### How Consolidation Works

At each round, the LLM sees **all patterns** from both inputs:
```
SOURCE_1_UNIVERSAL_PATTERNS
SOURCE_1_RARE_PATTERNS
SOURCE_2_UNIVERSAL_PATTERNS
SOURCE_2_RARE_PATTERNS
```

The LLM can:
1. **Merge patterns** → creates new universal pattern
2. **Pass through universal unchanged** → stays universal
3. **Rare patterns not merged** → automatically stay rare

### Why Rare Patterns Accumulate

Rare patterns only disappear if they merge with something. Otherwise, they persist through every round.

**Example accumulation (pessimistic ~20% merge rate):**
```
Round 1: ~15 patterns per output (5 universal, 10 rare)
Round 2: 15 + 15 - 6 merged = 24 patterns
Round 3: 24 + 24 - 10 = 38 patterns
Round 4: 38 + 38 - 15 = 61 patterns
Round 5: 61 + 61 - 24 = 98 patterns
Round 6: 98 + 98 - 39 = 157 patterns per input!
```

By Round 6, the prompt could contain **200-400 patterns** with full descriptions.

### Prompt Size Impact

Each pattern in the prompt includes:
```
U1_0: Pattern Name
  Description: Full description text (100-300 chars)
  Evidence Types: explicit_mandate, procedural_definition
  Mapping Patterns: direct_terminology_match
```

**Round 6 worst case:**
- 400 patterns × 300 chars = ~120,000 chars of pattern content
- Plus JSON schema with ~400 enum values
- **Total: ~130,000-150,000 chars (~35,000-40,000 tokens)**

## Why We Show Rare Patterns

The design is intentional: rare patterns from one branch might find matches when branches merge.

```
Round 1: Policy A + Policy B
         Pattern X only in A → rare

Round 2: (A+B) + (C+D)
         Pattern X (from A) meets similar Pattern Z (from C)
         → X + Z merge into universal pattern!
```

**The tradeoff:** We carry rare patterns forward hoping they'll match when branches converge.

## The Core Assumption

The map-reduce approach assumes:
1. There's a small set of universal patterns that will emerge
2. Most rare patterns will eventually find matches
3. The LLM will merge aggressively

**If these assumptions hold:** Pattern counts converge, prompts stay manageable.

**If they don't hold:** Pattern counts explode, prompts become huge.

## Potential Mitigations

### 1. Accept and Monitor
Run the aggregation and observe actual behavior. Maybe the LLM merges aggressively enough.

### 2. Compact Representation for Rares
In later rounds, represent rare patterns as just name + index (no full description). Only expand if LLM wants to merge.

### 3. Drop Rare After N Rounds
If a rare pattern hasn't merged by Round 3-4, drop it. Accept some loss.

### 4. Cap Rare Patterns Per Output
Keep only top-K rare patterns per RoundOutput based on some heuristic.

### 5. Two-Phase Approach
- Phase 1: Discover universals only (ignore rares)
- Phase 2: Check if any rares match discovered universals

### 6. Smarter Tree Construction
Cluster similar policies together so matches happen earlier in the tree.

## Next Steps

1. **Add observability**: Log universal/rare counts at each round
2. **Run real aggregation**: See actual pattern growth behavior
3. **Decide on mitigation**: Based on observed data, choose appropriate fix

## Open Questions

1. What merge rate does the LLM actually achieve?
2. How many patterns are truly unique vs. finding matches?
3. What's the acceptable prompt size limit for our model?
4. Is losing some rare patterns acceptable for the use case?
