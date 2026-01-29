# Control Selection Instructions (Distilled)

## Your Task

Given page image(s) from a security policy and a list of candidate controls, select ALL controls that this page adequately addresses. A page may match zero, one, or many controls. Evaluate each control independently.

## The Critical Distinction

**Topic similarity ≠ Valid match**

A valid match requires the page to contain a **binding mandate** that addresses the control's requirement—not just mention related concepts.

### Binding Language (Required for Match)
- "shall", "must", "required", "will ensure"
- "must not", "prohibited", "forbidden" (for prohibitions)

### Insufficient (Do Not Select)
- "should", "may", "recommended", "encouraged"
- Definitions or background without mandates
- Table of contents, headers, or boilerplate

## Selection Logic (Per Control)

For EACH candidate control, ask:

```
1. Does the page contain binding language about this control's subject?
   NO  → Do not select this control
   YES → Continue

2. Does the page mandate action that addresses this control's core requirement?
   NO  → Do not select this control
   YES → Select this control

3. How specific is the coverage?
   - Explicit procedures/specs/ownership → HIGH confidence
   - Clear intent but missing details → MEDIUM confidence
   - Tangential or partial coverage → LOW confidence
```

A page can match multiple controls if it contains binding mandates for each.

## Confidence Guide (Per Selected Control)

| Confidence | Criteria |
|------------|----------|
| **high** | Direct terminology match + binding language + specific details (who, when, how) |
| **medium** | Semantic equivalence to control intent OR binding language with minor gaps |
| **low** | Related coverage but significant gaps in specificity or scope |

Only assign confidence to controls you select. Do not select a control just to give it "none" confidence.

## Red Flags → Select No Controls

- Page only contains headers, TOC, or document metadata
- Terms appear but without "must/shall" language
- Page discusses concepts generally without mandating action
- Scope statement explicitly excludes what control requires

If ALL candidates fail these checks, return an empty selection.

## Quick Heuristics

1. **Look for verbs**: "shall implement", "must maintain", "is required to"
2. **Look for ownership**: "IT Security is responsible for...", "Data owners must..."
3. **Look for specifics**: frequencies, parameters, named standards, artifact requirements
4. **Ignore aspirations**: "We value security", "The goal is to...", "Best practices include..."

## Quality Over Quantity

Select a control only if the page genuinely addresses its requirement. When evaluating:
- Prefer precision over recall (don't stretch to find matches)
- Each selection should stand on its own merit
- If unsure, don't select—false positives are worse than false negatives
