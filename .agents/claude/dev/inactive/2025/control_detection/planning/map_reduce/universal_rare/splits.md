# Implementation Splits

The implementation plan is divided into **7 sequential, isolated splits**. Each split:
- Can be implemented and verified independently
- Leaves the system in a working state (all tests pass)
- Has clear verification criteria

**Reference:** See [plan.md](./plan.md) for full implementation details and TDD test examples.

## Split Dependency Graph

```
Split 1: Data Model Foundation
    │
    ├──► Split 2: Configuration + Prompt Assets (parallel-safe)
    │
    ├──► Split 3: Helper Functions
    │         │
    │         ▼
    │    Split 4: Response Parsing
    │         │
    │         ▼
    └──► Split 5: Round Behavior Changes ◄─────┘
              │
              ▼
         Split 6: Output Writer
              │
              ▼
         Split 7: Robustness & Observability
```

---

## Split 1: Data Model Foundation

**Scope:** Foundational data model changes that all other splits depend on.

**Includes:**
- Step 1: Add `pattern_id` field to `AggregatedPattern` with auto-generation
- Step 1: Add `merge_key` property to `AggregatedPattern`
- Step 2: Replace `RoundOutput.patterns` with `universal_patterns` and `rare_patterns`
- Step 2: Add `RoundOutput.all_patterns` property for backward compatibility
- Step 2: Update `to_dict()` and `from_dict()` methods
- **Migration**: Update all existing code referencing `RoundOutput.patterns`
- **Migration**: Update all existing tests to use new data model

**Files Modified:**
- `models.py`
- `aggregator.py` (update pattern references)
- `output_writer.py` (update pattern references)
- `test_models.py`
- `test_aggregator.py`
- `test_output_writer.py`

**Verification Criteria:**
- [ ] All existing tests pass (after migration)
- [ ] `pattern_id` is auto-generated and stable across instances
- [ ] `merge_key` returns canonical `(frozenset, frozenset)`
- [ ] `RoundOutput` serialization roundtrips correctly with both pattern lists
- [ ] `all_patterns` returns `universal_patterns + rare_patterns`

**Exit State:** System works exactly as before, but with new data model structure. All patterns currently go to `rare_patterns` (backward-compatible default).

---

## Split 2: Configuration + Prompt Assets

**Scope:** Non-breaking additions of configuration fields and prompt files.

**Includes:**
- Step 8: Add `consolidation_prompts_dir` path to config
- Step 8: Add `consolidation_temperature: float = 0.3`
- Step 8: Add `max_retry_on_invalid: int = 1`
- Step 9: Create `prompts/consolidate_patterns/` directory
- Step 9: Write `system` prompt
- Step 9: Write `user` prompt template with placeholders
- Step 9: Write `response.json` schema template with enum placeholders

**Files Modified:**
- `config.py`
- `test_config.py`

**Files Created:**
- `prompts/consolidate_patterns/system`
- `prompts/consolidate_patterns/user`
- `prompts/consolidate_patterns/response.json`

**Verification Criteria:**
- [ ] `config.consolidation_prompts_dir` points to valid directory
- [ ] `config.consolidation_temperature` defaults to 0.3
- [ ] `config.max_retry_on_invalid` defaults to 1
- [ ] All prompt files exist and are valid
- [ ] `response.json` contains placeholders: `VALID_INDICES`, `VALID_UNIVERSAL_INDICES`, `TOTAL_INDEX_COUNT`, `TOTAL_UNIVERSAL_COUNT`

**Exit State:** Configuration and prompts ready for Round 2+ logic. No behavioral changes yet.

---

## Split 3: Helper Functions

**Scope:** Pure utility functions for Round 2+ processing. No integration yet.

**Includes:**
- Step 3: Add `_inject_schema_enums(schema_template, all_indices, universal_indices)` function
- Step 4: Add `_format_indexed_patterns(patterns, prefix, source_num)` function
- Step 4: Add `_build_pattern_index_map(left_output, right_output)` function

**Files Modified:**
- `aggregator.py` (add helper functions)
- `test_aggregator.py` (add unit tests for helpers)

**Verification Criteria:**
- [ ] `_inject_schema_enums()` replaces all 4 placeholder types correctly
- [ ] `_inject_schema_enums()` handles nested structures
- [ ] `_inject_schema_enums()` handles empty universal indices (Round 2 from Round 1)
- [ ] `_format_indexed_patterns()` produces correct `U{source}_{idx}` and `R{source}_{idx}` format
- [ ] `_build_pattern_index_map()` correctly maps indices to patterns from both sources

**Exit State:** Helper functions available but not wired into main flow. Existing behavior unchanged.

---

## Split 4: Consolidation Response Parsing

**Scope:** Core parsing logic for Round 2+ LLM responses.

**Includes:**
- Step 5: Add `_parse_consolidation_response(response, index_map, input_indices)` function
- Implements coverage invariant (no pattern loss)
- Implements invalid index handling (warning + ignore)
- Implements leftover computation (still-rare = input - consumed)

**Files Modified:**
- `aggregator.py` (add parsing function)
- `test_aggregator.py` (add parsing tests)

**Verification Criteria:**
- [ ] Merged patterns have correctly merged `source_policy_ids`
- [ ] `unchanged_universal` patterns pass through verbatim
- [ ] Leftover rare patterns computed correctly as `input_indices - consumed`
- [ ] Invalid indices logged and ignored (no crash)
- [ ] Coverage invariant: `len(output_universal) + len(output_rare) == len(input_patterns)`

**Exit State:** Parsing function available but not wired into main flow. Existing behavior unchanged.

---

## Split 5: Round Behavior Changes

**Scope:** Core behavioral changes for Round 1 and Round 2+.

**Includes:**
- Step 6: Update `aggregate_pair()` to place all Round 1 patterns in `rare_patterns`
- Wire up Round 2+ prompt selection in `build_prompt()` (Round 1 vs Round 2+)
- Wire up schema injection for Round 2+ prompts
- Wire up consolidation response parsing in `aggregate_pair()` for Round 2+
- Update `prompts/aggregate_reasons/user` to remove anti-consolidation language

**Files Modified:**
- `aggregator.py` (main logic changes)
- `prompts/aggregate_reasons/user` (remove "DO NOT discard" language)
- `test_aggregator.py` (update and add Round behavior tests)

**Verification Criteria:**
- [ ] Round 1 produces `universal_patterns=()`, `rare_patterns=(all extracted patterns)`
- [ ] Round 1 patterns have `len(source_policy_ids) == 1`
- [ ] Round 2+ uses `consolidate_patterns` prompt
- [ ] Round 2+ schema has injected enum values for indices
- [ ] Round 2+ correctly parses merged patterns, unchanged universals, and computes rare leftovers
- [ ] End-to-end test with mock LLM passes for both Round 1 and Round 2+

**Exit State:** Full Round 1 + Round 2+ behavior implemented. System functionally complete.

---

## Split 6: Output Writer Enhancements

**Scope:** Enhanced output formatting with separate files.

**Includes:**
- Step 7: Update `write_final_output()` to produce three files:
  - `final_output.json` (complete RoundOutput)
  - `universal_patterns.md` (human-readable, sorted by source count)
  - `rare_patterns.md` (human-readable edge cases)
- Add `_format_universal_patterns_md()` method
- Add `_format_rare_patterns_md()` method

**Files Modified:**
- `output_writer.py`
- `test_output_writer.py`

**Verification Criteria:**
- [ ] `final_output.json` contains complete serialized RoundOutput
- [ ] `universal_patterns.md` contains only universal patterns
- [ ] `rare_patterns.md` contains only rare patterns
- [ ] Universal patterns sorted by `len(source_policy_ids)` descending
- [ ] Each markdown file has appropriate header with counts
- [ ] No pattern appears in both files

**Exit State:** Output writer produces all required files. Phase 1 output complete.

---

## Split 7: Robustness & Observability

**Scope:** Error handling, retry logic, and monitoring.

**Includes:**
- Step 10: Add validation check for invalid index rate (>20% triggers retry)
- Step 10: Add retry logic with error message
- Step 10: Proceed with best-effort after retry exhausted
- Step 11: Add structured logging for pattern counts (universal + rare)
- Step 11: Add structured logging for merge rate
- Step 11: Add structured logging for invalid index rate

**Files Modified:**
- `aggregator.py` (validation, retry, logging)
- `test_aggregator.py` (retry and logging tests)

**Verification Criteria:**
- [ ] High invalid index rate (>20%) triggers single retry
- [ ] Retry includes error context in prompt
- [ ] System proceeds with best-effort after retry exhausted (no crash)
- [ ] Logs contain `universal_count`, `rare_count` per round
- [ ] Logs contain `merge_rate` (consumed/total)
- [ ] Logs contain `invalid_index_rate` when applicable

**Exit State:** System is robust and observable. Implementation complete.

---

## Split Summary Table

| Split | Name | Plan Steps | Est. Size | Dependencies |
|-------|------|------------|-----------|--------------|
| 1 | Data Model Foundation | 1, 2 | Large | None |
| 2 | Configuration + Prompts | 8, 9 | Small | Split 1 (for prompt schema types) |
| 3 | Helper Functions | 3, 4 | Medium | Split 1 |
| 4 | Response Parsing | 5 | Medium | Split 1, 3 |
| 5 | Round Behavior Changes | 6 + integration | Large | Split 1, 2, 3, 4 |
| 6 | Output Writer | 7 | Medium | Split 1, 5 |
| 7 | Robustness & Observability | 10, 11 | Medium | Split 5 |

---

## Recommended Execution Order

1. **Split 1** - Must be first (all others depend on it)
2. **Split 2** - Can be done immediately after Split 1
3. **Split 3** - Can be done immediately after Split 1
4. **Split 4** - Requires Split 3
5. **Split 5** - Requires Splits 2, 3, 4 (the integration point)
6. **Split 6** - Requires Split 5 (needs working system to format output)
7. **Split 7** - Last (enhancements to working system)

---

## Notes for Implementation

### Parallelization Opportunity
Splits 2 and 3 can be worked on in parallel after Split 1 completes, as they have no dependencies on each other.

### Breaking Change in Split 1
Split 1 is the only split with a breaking change (`patterns` → `universal_patterns`/`rare_patterns`). All migration work is contained in this split to minimize disruption.

### Testing Strategy
Each split should follow TDD as outlined in `plan.md`:
1. Write failing tests first
2. Implement to make tests pass
3. Verify all existing tests still pass
4. Commit
