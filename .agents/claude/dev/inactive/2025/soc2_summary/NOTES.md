# SOC2 Summary Management Response Prompt Fix

## Date: 2025-11-17

## Problem

The `management_response` prompt was consistently failing with a `KeyError: 'relevant_excerpts_indices'`. Investigation revealed the LLM was calling the `parse_soc2_management_responses` tool with **completely empty arguments**:

```json
{
    "arguments": {},
    "id": "toolu_bdrk_017eGSpRz95RkKYM8DomM17X",
    "name": "parse_soc2_management_responses",
    "state": "FULFILLED"
}
```

Not even empty arrays - just `{}`. This caused a KeyError when trying to access `structured.input["relevant_excerpts_indices"]` in `prompt.py:49`.

## Investigation

### Initial Theories

1. **Context exhaustion**: Original prompts had 12 massive document excerpts, potentially overwhelming the LLM
2. **Conditional instructions**: Phrases like "if any" made tool calls seem optional
3. **Missing explicit instructions**: No clear instruction to always return both fields

### What We Tried (Didn't Work)

1.  Added explicit instruction: "Return empty arrays if none are found"
2.  Changed "if any" to "ALWAYS call" - made tool call mandatory
3.  Reduced context to single relevant excerpt
4.  Updated all similar prompts (exceptions, cuec, opinion) with same fixes

**Even with just ONE excerpt and explicit instructions, the LLM still returned empty arguments!**

## Root Cause

The real problem was **structural ambiguity** combined with **token generation burden**:

### The Structural Issue

The management response in test documents grouped multiple CC IDs together:
```
CC1.4.2, CC1.5.1, and CC5.3.4  annual employee evaluations  [response text]
CC2.2.2 and CC5.3.3  Security Manual acknowledgement  [response text]
CC3.1.2, CC3.2.1, CC3.3.1, CC3.4.1, CC4.1.1, CC4.2.1, CC5.1.2, CC7.5.2, CC8.1.8, and CC9.1.2  risk assessment  [response text]
```

But the schema had:
```json
{
  "common_criteria_id": {
    "type": ["string", "null"]
  }
}
```

The LLM faced a dilemma:
- Schema says: single string or null
- Instructions said: extract separate entries for each CC ID
- Document structure: groups multiple CC IDs together

**The LLM needed to create 15 separate entries** (one per CC ID), each duplicating the full response text. This would require generating **3000-5000 tokens** just for the tool call arguments.

### The Failure Mode

When faced with this complexity:
1. LLM recognized it needed to call the tool (per "ALWAYS call" instruction)
2. Started constructing the response
3. Realized the output would be massive and structurally ambiguous
4. Gave up and returned empty `{}` as a fallback

## Solution

### 1. Changed Schema to Array

**Before:**
```json
"common_criteria_id": {
  "type": ["string", "null"]
}
```

**After:**
```json
"common_criteria_ids": {
  "type": "array",
  "items": {"type": "string"}
}
```

### 2. Added Grouping Instruction

Updated instruction 4 in user prompt:
```
- If a single management response statement addresses multiple CC IDs together
  (e.g., "CC1.4.2, CC1.5.1, and CC5.3.4 - annual employee evaluations"),
  group them into ONE entry with all applicable CC IDs in the array
```

### 3. Updated All Downstream Code

- `prompt.py`: `common_criteria_id: str | None` ’ `common_criteria_ids: list[str]`
- `schema.py`: Updated `SOCType2ManagementResponse` dataclass
- `dto.py`: Updated `SOCType2ManagementResponseDTO` TypedDict
- `run.py`: Updated object creation code
- `dummy_management_responses.json`: Updated test data

## Result

The LLM can now create **3 concise entries** instead of 15 duplicative ones:

```json
{
  "management_responses": [
    {
      "common_criteria_ids": ["CC1.4.2", "CC1.5.1", "CC5.3.4"],
      "response_text": "processes will be implemented to ensure...",
      "page_number": "56"
    },
    {
      "common_criteria_ids": ["CC2.2.2", "CC5.3.3"],
      "response_text": "automated processes for acknowledgement...",
      "page_number": "56"
    },
    {
      "common_criteria_ids": ["CC3.1.2", "CC3.2.1", ..., "CC9.1.2"],
      "response_text": "risk assessment process has been reworked...",
      "page_number": "56"
    }
  ],
  "relevant_excerpts_indices": ["5"]
}
```

This reduces token generation from ~3000-5000 tokens to ~500-800 tokens, while accurately representing the structure of actual SOC2 management responses.

## Key Lessons

1. **Empty tool arguments indicate structural/generation issues**, not just missing instructions
2. **Token generation burden** can cause LLM to fail silently by returning empty arguments
3. **Schema should match document structure** - when documents naturally group items, the schema should support that
4. **Simplify output requirements** - reducing from 15 entries to 3 fixed the issue
5. **Test with minimal examples** - stripping down to one excerpt helped isolate the real problem

## Files Modified

- `prompts/management_response/response.json`
- `prompts/management_response/user`
- `prompts/management_response/prompt.py`
- `ai_services/shared/schema/artifact/documents/soc_type2/schema.py`
- `ai_services/shared/schema/dto.py`
- `ai_services/vellum/support/.../run.py`
- `files/dummy_management_responses.json`

## Status

 **FIXED** - Prompt now works reliably with management responses that cover multiple CC IDs.
