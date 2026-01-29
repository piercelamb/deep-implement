# Implementation Splits: Ground Truth Control Mapping Reasons Generator

This document defines the sequential, isolated units of work for implementing the plan. Each split can be implemented and verified independently before moving to the next.

---

## Split 1: Foundation (Configuration + Domain Models)

**Purpose**: Establish the data structures and configuration that all other components depend on.

**Scope**:
- `config.py` - ReasonGeneratorConfig dataclass
- Domain models in `reason_generator.py` (just the dataclasses, not the class):
  - `ReasonWithEvidence`
  - `ControlReasons`
- `__init__.py` - Package initialization

**Dependencies**: None (pure Python dataclasses)

**Test File**: `test_config.py`

**Verification**: Unit tests pass, config can be instantiated with defaults and overrides.

---

## Split 2: Prompt Infrastructure

**Purpose**: Load and substitute prompt templates from disk.

**Scope**:
- `prompt_loader.py` - PromptBundle class
- `prompts/control_reasons/system` - System prompt file
- `prompts/control_reasons/user` - User prompt file with placeholders
- `prompts/control_reasons/response.json` - Structured output schema

**Dependencies**: Split 1 (config for prompts_dir path)

**Test File**: `test_prompt_loader.py`

**Verification**: PromptBundle.load() works with placeholder substitution, prompt files exist and are well-formed.

---

## Split 3: Output Writers

**Purpose**: Write results to disk (JSON and Markdown).

**Scope**:
- `json_writer.py` - JsonResponseWriter class
- `output_writer.py` - MarkdownOutputWriter class

**Dependencies**: Split 1 (domain models for type hints)

**Test Files**: `test_json_writer.py`, `test_output_writer.py`

**Verification**:
- JsonResponseWriter creates directories, saves JSON files with correct naming
- MarkdownOutputWriter creates files with headers, appends control reasons, handles missed controls section

---

## Split 4: Cache Manager (Gemini Integration)

**Purpose**: Manage Gemini context caching for PDFs.

**Scope**:
- `cache_manager.py` - GeminiCacheManager class
  - `upload_pdf()` - Upload PDF to cache
  - `delete_cache()` - Delete single cache
  - `cleanup_orphaned_caches()` - Delete caches by prefix

**Dependencies**: Split 1 (config for model name, cache_prefix)

**Test File**: `test_cache_manager.py`

**Verification**:
- Mock tests for upload/delete/cleanup
- (Optional) Integration test with real Gemini API

---

## Split 5: Reason Generator (Core Logic)

**Purpose**: Orchestrate LLM calls for a single policy's controls.

**Scope**:
- `reason_generator.py` - ReasonGenerator class
  - `generate_for_control()` - Single control LLM call
  - `_generate_with_retry()` - Retry logic with jitter
  - `_call_llm()` - Actual Gemini API call with cached PDF
  - `_parse_response()` - Parse raw JSON to domain model
  - `process_policy()` - Orchestrate all controls for one policy

**Dependencies**:
- Split 1 (config, domain models)
- Split 2 (prompt loader)
- Split 3 (writers)
- Split 4 (cache manager)

**Test File**: `test_reason_generator.py`

**Verification**:
- Mock tests for single control generation
- Mock tests for retry logic
- Mock tests for full policy processing

---

## Split 6: CLI Entry Point + Signal Handling

**Purpose**: Provide CLI interface and graceful shutdown.

**Scope**:
- `run.py` - Typer CLI app
  - CLI argument parsing
  - Ground truth mapping loading
  - Policy filtering logic
  - Signal handlers (SIGINT/SIGTERM)
  - `_active_caches` tracking
  - `cleanup_on_exit()` function
  - `run_cleanup()` - Orphaned cache cleanup mode
  - `run_dry_run()` - Preview mode
  - `run_generator()` - Main execution

**Dependencies**: All previous splits

**Test File**: `test_run.py`

**Verification**:
- CLI accepts all documented flags
- Single policy mode works
- All policies mode works
- Cleanup mode works
- Dry run mode works

---

## Implementation Order

```
Split 1: Foundation
    ↓
Split 2: Prompts ────────┐
    ↓                    │
Split 3: Writers ────────┤
    ↓                    │
Split 4: Cache Manager ──┤
    ↓                    │
Split 5: Reason Generator ← (depends on 2, 3, 4)
    ↓
Split 6: CLI Entry Point
```

**Notes**:
- Splits 2, 3, and 4 can be implemented in any order after Split 1 (they are independent of each other)
- Split 5 requires all of 2, 3, 4 to be complete
- Split 6 requires Split 5 to be complete

---

## Verification Gates

Before proceeding to the next split, ensure:

1. **All tests pass** for the current split
2. **No import errors** when importing the module
3. **Type checking passes** (mypy)
4. **Code is formatted** (ruff format)

---

## File Inventory by Split

| Split | Files Created |
|-------|---------------|
| 1 | `__init__.py`, `config.py`, domain models stub |
| 2 | `prompt_loader.py`, `prompts/control_reasons/{system,user,response.json}` |
| 3 | `json_writer.py`, `output_writer.py` |
| 4 | `cache_manager.py` |
| 5 | `reason_generator.py` (full implementation) |
| 6 | `run.py` |

| Split | Test Files Created |
|-------|-------------------|
| 1 | `test_config.py` |
| 2 | `test_prompt_loader.py` |
| 3 | `test_json_writer.py`, `test_output_writer.py` |
| 4 | `test_cache_manager.py` |
| 5 | `test_reason_generator.py` |
| 6 | `test_run.py` |
