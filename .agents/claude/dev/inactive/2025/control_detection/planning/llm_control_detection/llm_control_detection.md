# Control Detection: LLM Decision Layer

## Overview

Add a Gemini-based final decision layer to the control detection experiment. ColModernVBERT serves as a retrieval mechanism to score controls against policy pages, then an LLM analyzes each qualifying page + its candidate controls to make page-level decisions, which are aggregated into a document-level prediction.

**Multi-Select:** Each page can match zero, one, or many controls. The LLM evaluates each candidate independently and selects all controls that the page adequately addresses with binding mandates.

**Prompt Instructions:** The LLM is guided by distilled control mapping instructions derived from analysis of 37 security policies. See: `planning/llm_control_detection/distilled_mapping_instructions.md`

```
Policy PDF Pages → ColModernVBERT Scoring → Per-Page Threshold Filter →
→ Parallel LLM Calls (1 per qualifying page) → Aggregate → Final Control Selection(s)
```

## Architecture: Page-Level LLM Calls

**Problem:** Documents can have 10s-100s of pages and 10s-100s of controls above threshold. A single LLM call with all data would be:
- Too many tokens (context limits)
- Too expensive
- Less accurate (information overload)

**Solution:** Each page that has at least one control scoring above threshold gets its own LLM call, with intelligent inclusion of neighboring pages for context.

```
For each page in document:
    controls_for_page = [c for c in controls if c.score_on_page >= threshold]
    if controls_for_page:
        context_images = get_context_images(page, neighbors, controls_for_page)
        page_decision = llm_call(context_images, controls_for_page)
        page_decisions.append(page_decision)

document_decision = aggregate(page_decisions)
```

**Benefits:**
- **Bounded context**: Each call has 1-5 images + N controls (N typically small due to threshold)
- **Parallelizable**: All page calls can run concurrently
- **Clear provenance**: "Page 3 matched DCF-182 with high confidence"
- **Natural unit**: ColModernVBERT already scores at page level
- **Context awareness**: Neighboring pages included when semantically related

## Intelligent Neighbor Page Inclusion

**Problem:** Policy content often spans multiple pages. A qualifying page might be mid-section, with important context on adjacent pages (headers, continued paragraphs, tables).

**Solution:** Intelligently include neighboring pages based on control relatedness hierarchy.

### Hierarchical Control Relatedness

Include a neighbor page if it has a meaningful score for a **related** control. Relatedness is checked in order (most to least strict):

| Level | Check | Threshold | Example |
|-------|-------|-----------|---------|
| 1. Same Control ID | Neighbor has same control | `neighbor_threshold * 0.7` | Both have DCF-4 |
| 2. Same Domain | Neighbor has control in same domain | `neighbor_threshold` (full) | Both have "Change Management" controls |

**Note:** Classification (e.g., "Protect") is intentionally excluded - it's too broad and would match unrelated pages (e.g., "Firewalls" vs "HR Background Checks" both classified as "Protect").

**DCF Control Hierarchy (from `dcf_controls.csv`):**
```
Control ID: DCF-4, DCF-5, DCF-6
     └── Domain: "Change Management"
```

### Behavior Examples

**Example 1: Same control ID (lenient threshold)**
```
Page 5 qualifies: DCF-4 (Change Management) @ 120, threshold=100, neighbor_threshold=50
Page 4 scores:    DCF-4 @ 40, DCF-999 @ 45
→ Include page 4: Same control ID (DCF-4), score 40 > (50 * 0.7 = 35)
```

**Example 2: Same domain match**
```
Page 5 qualifies: DCF-4 (Change Management) @ 120
Page 4 scores:    DCF-5 (Change Management) @ 55, DCF-999 @ 45
→ Include page 4: DCF-5 shares domain with DCF-4, score 55 > neighbor_threshold 50
```

**Example 3: No match (different domain)**
```
Page 5 qualifies: DCF-182 (Cryptography) @ 120
Page 6 scores:    DCF-8 (Incident Management) @ 80, DCF-9 (Incident Management) @ 70
→ Don't include page 6: Different domain, no shared control IDs
```

**Example 4: Missing domain (falls back to control ID only)**
```
Page 5 qualifies: DCF-999 (no domain) @ 120
Page 4 scores:    DCF-999 @ 40, DCF-888 @ 60
→ Include page 4: Same control ID (DCF-999), score 40 > lenient threshold 35
```

### Edge Cases

| Scenario | Handling |
|----------|----------|
| Page 1 qualifies | No previous page - only check next |
| Last page qualifies | No next page - only check previous |
| Adjacent pages both qualify | Each gets own LLM call; may share context images |
| Neighbor has no domain | Only matches on control ID level |
| No neighbors match | Primary page only (cleaner context) |

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Policy Document (N pages)                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              ColModernVBERT: Score all 779 controls per page         │
│              Output: PagePrediction[] with ScoredControl[]           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Per-Page Threshold Filter                               │
│              Keep pages where ANY control scored >= threshold        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Intelligent Neighbor Inclusion                          │
│              Add context pages based on control relatedness          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
     ┌──────────┐        ┌──────────┐        ┌──────────┐
     │  Page 1  │        │ Page 2,3 │        │  Page 7  │
     │ (primary)│        │ (3=prim) │        │ (primary)│
     │ + 3 ctrl │        │ + 5 ctrl │        │ + 2 ctrl │
     └────┬─────┘        └────┬─────┘        └────┬─────┘
          │                   │                   │
          ▼                   ▼                   ▼
     ┌──────────┐        ┌──────────┐        ┌──────────┐
     │ Gemini   │        │ Gemini   │        │ Gemini   │
     │ 1 image  │        │ 2 images │        │ 1 image  │
     └────┬─────┘        └────┬─────┘        └────┬─────┘
          │                   │                   │
          ▼                   ▼                   ▼
     ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
     │ PageDecision │    │ PageDecision │    │ PageDecision │
     │ DCF-182 high │    │ DCF-182 med  │    │ DCF-305 low  │
     │ DCF-4 medium │    │ (none other) │    │ DCF-306 low  │
     └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                │
                                ▼
                      ┌─────────────────────┐
                      │     Aggregation     │
                      │ → DCF-182 (2 pages) │
                      │ → DCF-4 (1 page)    │
                      │ → DCF-305,306 (1pg) │
                      └─────────────────────┘
```

## Requirements

1. **Per-page LLM calls**: Each page with controls above threshold gets its own LLM call
2. **Score thresholding**: Filter controls per page by configurable score threshold
3. **Intelligent neighbor inclusion**: Include adjacent pages when they have related controls (same ID, domain, or classification)
4. **Multimodal LLM**: Send page image(s) + filtered controls to Vertex AI Gemini 3 Pro
5. **Direct API calls**: Use `google-genai` SDK directly, no existing codebase infrastructure
6. **Prompts from disk**: Load system/user/response.json from flat files with runtime context insertion
7. **Aggregation**: Combine page-level decisions into document-level prediction

---

## TDD Implementation Plan

### Test File Structure

```
tests/scripts/experiments/control_detection/
├── test_dcf_controls.py          # Cycle 1: DCFControl domain field
├── test_prompt_loader.py         # Cycle 2: Prompt loading utilities
├── test_llm_decider_config.py    # Cycle 3: Configuration dataclasses
├── test_neighbor_inclusion.py    # Cycle 4: Neighbor inclusion logic
├── test_candidate_building.py    # Cycle 5: Candidate list building
├── test_triggered_pages.py       # Cycle 6: Page triggering logic
├── test_aggregation.py           # Cycle 7: Decision aggregation
├── test_llm_decider.py           # Cycle 8: LLM decider (mocked LLM)
└── test_llm_decider_integration.py  # Cycle 9: Integration test
```

---

## Cycle 1: DCFControl Domain Field

### 1.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_dcf_controls.py`

```python
"""Tests for DCFControl with domain field."""

import pytest
from pathlib import Path

from ai_services.scripts.experiments.control_detection.dcf_controls import (
    DCFControl,
    load_controls,
)


class TestDCFControlDomain:
    """Test DCFControl includes domain field."""

    def test_dcf_control_has_domain_field(self):
        """DCFControl should have a domain field."""
        control = DCFControl(
            control_id="DCF-4",
            name="Version Control System",
            description="Test description",
            domain="Change Management",
        )
        assert control.domain == "Change Management"

    def test_dcf_control_domain_can_be_none(self):
        """Domain field should allow None for controls without domain."""
        control = DCFControl(
            control_id="DCF-999",
            name="Test Control",
            description="Test description",
            domain=None,
        )
        assert control.domain is None

    def test_dcf_control_is_frozen(self):
        """DCFControl should be immutable."""
        control = DCFControl(
            control_id="DCF-4",
            name="Test",
            description="Test",
            domain="Change Management",
        )
        with pytest.raises(AttributeError):
            control.domain = "Something Else"


class TestLoadControlsWithDomain:
    """Test load_controls parses domain from CSV."""

    def test_load_controls_includes_domain(self, tmp_path: Path):
        """load_controls should parse Control Domain column."""
        csv_content = '''Control ID,Control Name,Control Description,Control Domain
DCF-4,Version Control System,Uses version control,Change Management
DCF-182,Encryption at Rest,Data encrypted,Cryptography
'''
        csv_file = tmp_path / "test_controls.csv"
        csv_file.write_text(csv_content)

        controls = load_controls(csv_file)

        assert len(controls) == 2
        assert controls[0].domain == "Change Management"
        assert controls[1].domain == "Cryptography"

    def test_load_controls_handles_missing_domain(self, tmp_path: Path):
        """load_controls should handle empty domain gracefully."""
        csv_content = '''Control ID,Control Name,Control Description,Control Domain
DCF-999,No Domain Control,Test description,
'''
        csv_file = tmp_path / "test_controls.csv"
        csv_file.write_text(csv_content)

        controls = load_controls(csv_file)

        assert len(controls) == 1
        assert controls[0].domain is None
```

### 1.2 Implement to Pass (GREEN)

**File:** `ai_services/scripts/experiments/control_detection/dcf_controls.py`

Modify `DCFControl` dataclass:
```python
@dataclass(frozen=True, slots=True, kw_only=True)
class DCFControl:
    """A single DCF control with hierarchy information."""
    control_id: str           # "DCF-4"
    name: str                 # "Version Control System"
    description: str          # Full description text
    domain: str | None        # "Change Management" (Control Domain column)
```

Modify `load_controls()` to parse the "Control Domain" column.

### 1.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_dcf_controls.py -v
```

---

## Cycle 2: Prompt Loader

### 2.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_prompt_loader.py`

```python
"""Tests for prompt loading utilities."""

import json
import pytest
from pathlib import Path

from ai_services.scripts.experiments.control_detection.prompt_loader import (
    load_response_schema,
    PromptBundle,
)


class TestLoadResponseSchema:
    """Test dynamic enum replacement in response schema."""

    def test_replaces_string_enum_with_context_value(self, tmp_path: Path):
        """String enum values should be replaced with context dict values."""
        schema = {
            "type": "object",
            "properties": {
                "selected_control_id": {
                    "type": "string",
                    "enum": "CONTROL_IDS",
                }
            }
        }
        (tmp_path / "response.json").write_text(json.dumps(schema))

        context = {"CONTROL_IDS": ["DCF-4", "DCF-5", "NONE"]}
        result = load_response_schema(tmp_path, context)

        assert result["properties"]["selected_control_id"]["enum"] == ["DCF-4", "DCF-5", "NONE"]

    def test_preserves_array_enum_values(self, tmp_path: Path):
        """Array enum values should be preserved unchanged."""
        schema = {
            "type": "object",
            "properties": {
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low", "none"],
                }
            }
        }
        (tmp_path / "response.json").write_text(json.dumps(schema))

        context = {}
        result = load_response_schema(tmp_path, context)

        assert result["properties"]["confidence"]["enum"] == ["high", "medium", "low", "none"]

    def test_handles_nested_objects(self, tmp_path: Path):
        """Should handle nested object structures."""
        schema = {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string", "enum": "VALUES"}
                    }
                }
            }
        }
        (tmp_path / "response.json").write_text(json.dumps(schema))

        context = {"VALUES": ["a", "b", "c"]}
        result = load_response_schema(tmp_path, context)

        assert result["properties"]["nested"]["properties"]["value"]["enum"] == ["a", "b", "c"]

    def test_ignores_missing_context_keys(self, tmp_path: Path):
        """String enum with missing context key should be left unchanged."""
        schema = {
            "properties": {
                "field": {"enum": "MISSING_KEY"}
            }
        }
        (tmp_path / "response.json").write_text(json.dumps(schema))

        context = {}
        result = load_response_schema(tmp_path, context)

        assert result["properties"]["field"]["enum"] == "MISSING_KEY"


class TestPromptBundle:
    """Test PromptBundle loading and template substitution."""

    def test_load_substitutes_placeholders(self, tmp_path: Path):
        """User prompt placeholders should be substituted from context."""
        (tmp_path / "system").write_text("You are a compliance expert.")
        (tmp_path / "user").write_text("Page {page_num}. Controls: {controls}")
        (tmp_path / "response.json").write_text('{"type": "object"}')

        context = {
            "page_num": 5,
            "controls": "DCF-4, DCF-5",
        }
        bundle = PromptBundle.load(tmp_path, context)

        assert bundle.system == "You are a compliance expert."
        assert bundle.user == "Page 5. Controls: DCF-4, DCF-5"

    def test_load_raises_on_missing_placeholder(self, tmp_path: Path):
        """Missing placeholder should raise KeyError."""
        (tmp_path / "system").write_text("System prompt")
        (tmp_path / "user").write_text("Missing {undefined_placeholder}")
        (tmp_path / "response.json").write_text('{"type": "object"}')

        context = {"page_num": 5}

        with pytest.raises(KeyError, match="undefined_placeholder"):
            PromptBundle.load(tmp_path, context)

    def test_load_includes_response_schema(self, tmp_path: Path):
        """Response schema should be loaded and available."""
        (tmp_path / "system").write_text("System")
        (tmp_path / "user").write_text("User")
        schema = {"type": "object", "properties": {"field": {"enum": "IDS"}}}
        (tmp_path / "response.json").write_text(json.dumps(schema))

        context = {"IDS": ["a", "b"]}
        bundle = PromptBundle.load(tmp_path, context)

        assert bundle.response_schema["properties"]["field"]["enum"] == ["a", "b"]
```

### 2.2 Implement to Pass (GREEN)

**File:** `ai_services/scripts/experiments/control_detection/prompt_loader.py`

```python
"""Simple prompt loader for loading prompts from disk with context insertion."""

import json
from pathlib import Path
from typing import Any


def load_response_schema(prompt_dir: Path, context: dict[str, Any]) -> dict:
    """Load response.json and replace dynamic enum values.

    Replaces "enum": "VARIABLE" with "enum": context["VARIABLE"].
    """
    schema_text = (prompt_dir / "response.json").read_text()
    schema = json.loads(schema_text)

    def replace_enums(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "enum" in obj and isinstance(obj["enum"], str):
                enum_key = obj["enum"]
                if enum_key in context:
                    obj["enum"] = context[enum_key]
            return {k: replace_enums(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_enums(item) for item in obj]
        return obj

    return replace_enums(schema)


class PromptBundle:
    """Bundle of loaded prompts ready for LLM call."""

    def __init__(self, system: str, user: str, response_schema: dict):
        self.system = system
        self.user = user
        self.response_schema = response_schema

    @classmethod
    def load(cls, prompt_dir: Path, context: dict[str, Any]) -> "PromptBundle":
        """Load and prepare prompts from a directory.

        Uses .format(**context) for placeholder substitution.
        Raises KeyError if any placeholder is missing from context.
        """
        system = (prompt_dir / "system").read_text()
        user_template = (prompt_dir / "user").read_text()
        user = user_template.format(**context)  # Raises KeyError if placeholder missing
        response_schema = load_response_schema(prompt_dir, context)
        return cls(system=system, user=user, response_schema=response_schema)
```

### 2.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_prompt_loader.py -v
```

---

## Cycle 3: Configuration Dataclasses

### 3.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_llm_decider_config.py`

```python
"""Tests for LLM decider configuration dataclasses."""

import pytest
from dataclasses import FrozenInstanceError

from ai_services.scripts.experiments.control_detection.llm_decider import (
    NeighborInclusionConfig,
    LLMDeciderConfig,
    PageLLMInput,
    ControlSelection,
    PageLLMDecision,
    DocumentLLMDecision,
)


class TestNeighborInclusionConfig:
    """Test NeighborInclusionConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = NeighborInclusionConfig()
        assert config.enabled is True
        assert config.threshold_ratio == 0.5
        assert config.max_total_pages == 5

    def test_is_frozen(self):
        """Should be immutable."""
        config = NeighborInclusionConfig()
        with pytest.raises(FrozenInstanceError):
            config.enabled = False

    def test_custom_values(self):
        """Should accept custom values."""
        config = NeighborInclusionConfig(
            enabled=False,
            threshold_ratio=0.7,
            max_total_pages=3,
        )
        assert config.enabled is False
        assert config.threshold_ratio == 0.7
        assert config.max_total_pages == 3


class TestLLMDeciderConfig:
    """Test LLMDeciderConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = LLMDeciderConfig()
        assert config.model == "gemini-3.0-pro"
        assert config.temperature == 0.1
        assert config.trigger_threshold == 100.0
        assert config.candidate_threshold == 60.0
        assert config.max_candidates == 10
        assert config.max_concurrent == 10
        assert config.neighbor_config.enabled is True

    def test_nested_neighbor_config(self):
        """Should allow nested NeighborInclusionConfig."""
        config = LLMDeciderConfig(
            neighbor_config=NeighborInclusionConfig(enabled=False)
        )
        assert config.neighbor_config.enabled is False

    def test_is_frozen(self):
        """Should be immutable."""
        config = LLMDeciderConfig()
        with pytest.raises(FrozenInstanceError):
            config.model = "other-model"


class TestPageLLMInput:
    """Test PageLLMInput dataclass."""

    def test_required_fields(self):
        """Should require all fields."""
        input_data = PageLLMInput(
            primary_page_num=5,
            images=((5, b"image_bytes"),),
            controls=(),
            context_page_nums=(),
        )
        assert input_data.primary_page_num == 5
        assert input_data.images == ((5, b"image_bytes"),)

    def test_with_context_pages(self):
        """Should track context page numbers."""
        input_data = PageLLMInput(
            primary_page_num=5,
            images=((4, b"ctx"), (5, b"primary"), (6, b"ctx")),
            controls=(),
            context_page_nums=(4, 6),
        )
        assert input_data.context_page_nums == (4, 6)


class TestControlSelection:
    """Test ControlSelection dataclass."""

    def test_all_fields(self):
        """Should have control_id, confidence, and reasoning."""
        selection = ControlSelection(
            control_id="DCF-182",
            confidence="high",
            reasoning="Page describes encryption policy",
        )
        assert selection.control_id == "DCF-182"
        assert selection.confidence == "high"
        assert selection.reasoning == "Page describes encryption policy"


class TestPageLLMDecision:
    """Test PageLLMDecision dataclass (multi-select)."""

    def test_single_selection(self):
        """Should support single control selection."""
        decision = PageLLMDecision(
            page_num=5,
            selected_controls=(
                ControlSelection(
                    control_id="DCF-182",
                    confidence="high",
                    reasoning="Page describes encryption policy",
                ),
            ),
            candidate_control_ids=("DCF-182", "DCF-183"),
            context_page_nums=(4, 6),
        )
        assert decision.page_num == 5
        assert len(decision.selected_controls) == 1
        assert decision.selected_controls[0].control_id == "DCF-182"

    def test_multiple_selections(self):
        """Should support multiple control selections."""
        decision = PageLLMDecision(
            page_num=5,
            selected_controls=(
                ControlSelection(control_id="DCF-182", confidence="high", reasoning="Encryption"),
                ControlSelection(control_id="DCF-4", confidence="medium", reasoning="Change mgmt"),
            ),
            candidate_control_ids=("DCF-182", "DCF-4", "DCF-5"),
            context_page_nums=(),
        )
        assert len(decision.selected_controls) == 2

    def test_empty_selection(self):
        """Should allow empty selection (no matches)."""
        decision = PageLLMDecision(
            page_num=3,
            selected_controls=(),  # Empty tuple - no controls matched
            candidate_control_ids=("DCF-4", "DCF-5"),
            context_page_nums=(),
        )
        assert len(decision.selected_controls) == 0


class TestDocumentLLMDecision:
    """Test DocumentLLMDecision dataclass (multi-select)."""

    def test_aggregated_decision(self):
        """Should aggregate page decisions with union of controls."""
        page_decisions = (
            PageLLMDecision(
                page_num=1,
                selected_controls=(
                    ControlSelection(control_id="DCF-182", confidence="high", reasoning="Page 1"),
                    ControlSelection(control_id="DCF-4", confidence="medium", reasoning="Page 1"),
                ),
                candidate_control_ids=("DCF-182", "DCF-4"),
                context_page_nums=(),
            ),
            PageLLMDecision(
                page_num=3,
                selected_controls=(
                    ControlSelection(control_id="DCF-182", confidence="medium", reasoning="Page 3"),
                ),
                candidate_control_ids=("DCF-182",),
                context_page_nums=(),
            ),
        )
        doc_decision = DocumentLLMDecision(
            selected_controls=(
                ControlSelection(control_id="DCF-182", confidence="high", reasoning="2 pages"),
                ControlSelection(control_id="DCF-4", confidence="medium", reasoning="1 page"),
            ),
            page_decisions=page_decisions,
            aggregation_method="union_with_max_confidence",
        )
        assert len(doc_decision.selected_controls) == 2
        assert len(doc_decision.page_decisions) == 2
        assert doc_decision.aggregation_method == "union_with_max_confidence"
```

### 3.2 Implement to Pass (GREEN)

**File:** `ai_services/scripts/experiments/control_detection/llm_decider.py` (partial - dataclasses only)

```python
"""LLM decision layer for control detection."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, kw_only=True)
class NeighborInclusionConfig:
    """Configuration for intelligent neighbor page inclusion."""
    enabled: bool = True
    threshold_ratio: float = 0.5  # neighbor_threshold = score_threshold * ratio
    max_total_pages: int = 5      # Hard cap on total pages per LLM call


@dataclass(frozen=True, slots=True, kw_only=True)
class LLMDeciderConfig:
    """Configuration for LLM decision layer."""
    model: str = "gemini-3.0-pro"
    temperature: float = 0.1

    # Dual threshold strategy
    trigger_threshold: float = 100.0   # Page must have control >= this to trigger LLM call
    candidate_threshold: float = 60.0  # Controls >= this are shown to LLM as candidates
    max_candidates: int = 10           # Cap candidates to avoid overwhelming LLM

    # Neighbor inclusion
    neighbor_config: NeighborInclusionConfig = field(default_factory=NeighborInclusionConfig)

    # Concurrency
    max_concurrent: int = 10  # Avoid rate limiting


@dataclass(frozen=True, slots=True, kw_only=True)
class PageLLMInput:
    """Input for a single page's LLM call."""
    primary_page_num: int
    images: tuple[tuple[int, bytes], ...]  # (page_num, image_bytes)
    controls: tuple  # tuple[ScoredControl, ...] - using tuple to avoid circular import
    context_page_nums: tuple[int, ...]     # Which pages are context (not primary)


@dataclass(frozen=True, slots=True, kw_only=True)
class ControlSelection:
    """A single control selection with confidence and reasoning."""
    control_id: str
    confidence: str  # "high", "medium", "low"
    reasoning: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PageLLMDecision:
    """LLM decision for a single page. Can select zero, one, or many controls."""
    page_num: int
    selected_controls: tuple[ControlSelection, ...]  # Empty tuple if no matches
    candidate_control_ids: tuple[str, ...]  # Controls that were considered
    context_page_nums: tuple[int, ...]      # Neighbor pages included for context


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentLLMDecision:
    """Aggregated LLM decision for entire document."""
    selected_controls: tuple[ControlSelection, ...]  # All controls found across pages
    page_decisions: tuple[PageLLMDecision, ...]
    aggregation_method: str  # e.g., "union_with_max_confidence"
```

### 3.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_llm_decider_config.py -v
```

---

## Cycle 4: Neighbor Inclusion Logic

### 4.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_neighbor_inclusion.py`

```python
"""Tests for intelligent neighbor page inclusion."""

import pytest

from ai_services.scripts.experiments.control_detection.dcf_controls import DCFControl
from ai_services.scripts.experiments.control_detection.predictor import (
    ScoredControl,
    PagePrediction,
)
from ai_services.scripts.experiments.control_detection.llm_decider import (
    should_include_neighbor,
)


# Test fixtures
@pytest.fixture
def change_mgmt_control():
    """DCF-4: Change Management control."""
    return DCFControl(
        control_id="DCF-4",
        name="Version Control",
        description="Test",
        domain="Change Management",
    )


@pytest.fixture
def change_mgmt_control_5():
    """DCF-5: Another Change Management control."""
    return DCFControl(
        control_id="DCF-5",
        name="Change Review",
        description="Test",
        domain="Change Management",
    )


@pytest.fixture
def crypto_control():
    """DCF-182: Cryptography control."""
    return DCFControl(
        control_id="DCF-182",
        name="Encryption",
        description="Test",
        domain="Cryptography",
    )


@pytest.fixture
def incident_control():
    """DCF-8: Incident Management control."""
    return DCFControl(
        control_id="DCF-8",
        name="Incident Response",
        description="Test",
        domain="Incident Management",
    )


@pytest.fixture
def no_domain_control():
    """Control without domain."""
    return DCFControl(
        control_id="DCF-999",
        name="No Domain",
        description="Test",
        domain=None,
    )


class TestShouldIncludeNeighbor:
    """Test should_include_neighbor function."""

    def test_same_control_id_lenient_threshold(self, change_mgmt_control):
        """Same control ID uses lenient threshold (70% of neighbor_threshold)."""
        # Page 5 qualifies with DCF-4 @ 120
        qualifying = [ScoredControl(control=change_mgmt_control, score=120.0)]

        # Page 4 has DCF-4 @ 40 (above 50 * 0.7 = 35)
        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_control, score=40.0)],
        )

        assert should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_same_control_id_below_lenient_threshold(self, change_mgmt_control):
        """Same control ID below lenient threshold should not include."""
        qualifying = [ScoredControl(control=change_mgmt_control, score=120.0)]

        # Page 4 has DCF-4 @ 30 (below 50 * 0.7 = 35)
        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_control, score=30.0)],
        )

        assert not should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_same_domain_full_threshold(self, change_mgmt_control, change_mgmt_control_5):
        """Same domain uses full neighbor_threshold."""
        # Page 5 qualifies with DCF-4 (Change Management)
        qualifying = [ScoredControl(control=change_mgmt_control, score=120.0)]

        # Page 4 has DCF-5 (Change Management) @ 55 (above threshold 50)
        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_control_5, score=55.0)],
        )

        assert should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_same_domain_below_threshold(self, change_mgmt_control, change_mgmt_control_5):
        """Same domain below threshold should not include."""
        qualifying = [ScoredControl(control=change_mgmt_control, score=120.0)]

        # Page 4 has DCF-5 (Change Management) @ 45 (below threshold 50)
        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_control_5, score=45.0)],
        )

        assert not should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_different_domain_not_included(self, crypto_control, incident_control):
        """Different domain should not be included."""
        # Page 5 qualifies with DCF-182 (Cryptography)
        qualifying = [ScoredControl(control=crypto_control, score=120.0)]

        # Page 6 has DCF-8 (Incident Management) @ 80
        neighbor_pred = PagePrediction(
            page_num=6,
            top_controls=[ScoredControl(control=incident_control, score=80.0)],
        )

        assert not should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_no_domain_falls_back_to_control_id(self, no_domain_control):
        """Control without domain only matches on control ID."""
        qualifying = [ScoredControl(control=no_domain_control, score=120.0)]

        # Same control ID, above lenient threshold
        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=no_domain_control, score=40.0)],
        )

        assert should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_no_domain_different_id_not_included(self, no_domain_control):
        """Different control ID with no domain should not match."""
        qualifying = [ScoredControl(control=no_domain_control, score=120.0)]

        other_control = DCFControl(
            control_id="DCF-888",
            name="Other",
            description="Test",
            domain=None,
        )
        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=other_control, score=80.0)],
        )

        assert not should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_empty_neighbor_controls(self, change_mgmt_control):
        """Empty neighbor controls should not match."""
        qualifying = [ScoredControl(control=change_mgmt_control, score=120.0)]

        neighbor_pred = PagePrediction(page_num=4, top_controls=[])

        assert not should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)

    def test_multiple_qualifying_controls(self, change_mgmt_control, crypto_control):
        """Should check against all qualifying controls."""
        # Multiple qualifying controls
        qualifying = [
            ScoredControl(control=change_mgmt_control, score=120.0),
            ScoredControl(control=crypto_control, score=110.0),
        ]

        # Neighbor matches crypto domain
        other_crypto = DCFControl(
            control_id="DCF-183",
            name="Key Management",
            description="Test",
            domain="Cryptography",
        )
        neighbor_pred = PagePrediction(
            page_num=6,
            top_controls=[ScoredControl(control=other_crypto, score=55.0)],
        )

        assert should_include_neighbor(qualifying, neighbor_pred, neighbor_threshold=50.0)
```

### 4.2 Implement to Pass (GREEN)

**Add to** `ai_services/scripts/experiments/control_detection/llm_decider.py`:

```python
def should_include_neighbor(
    qualifying_controls: list[ScoredControl],
    neighbor_prediction: PagePrediction,
    neighbor_threshold: float,
) -> bool:
    """
    Include neighbor if it has meaningful score for a related control.

    Checks in order (most to least strict):
    1. Same control ID (lenient threshold - 70% of neighbor_threshold)
    2. Same domain (full neighbor_threshold required)
    """
    qualifying_ids = {c.control.control_id for c in qualifying_controls}
    qualifying_domains = {c.control.domain for c in qualifying_controls if c.control.domain}

    # Lenient threshold for same control ID (content spanning pages)
    same_id_threshold = neighbor_threshold * 0.7

    for neighbor_control in neighbor_prediction.top_controls:
        ctrl = neighbor_control.control

        # Level 1: Same control ID (lenient threshold - indicates content spanning pages)
        if ctrl.control_id in qualifying_ids and neighbor_control.score >= same_id_threshold:
            return True

        # Level 2: Same domain (full threshold required - domain can be broad)
        if ctrl.domain and ctrl.domain in qualifying_domains and neighbor_control.score >= neighbor_threshold:
            return True

    return False
```

### 4.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_neighbor_inclusion.py -v
```

---

## Cycle 5: Candidate List Building

### 5.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_candidate_building.py`

```python
"""Tests for candidate list building with neighbor expansion."""

import pytest

from ai_services.scripts.experiments.control_detection.dcf_controls import DCFControl
from ai_services.scripts.experiments.control_detection.predictor import (
    ScoredControl,
    PagePrediction,
)
from ai_services.scripts.experiments.control_detection.llm_decider import (
    build_candidate_list,
)


@pytest.fixture
def change_mgmt_controls():
    """Change Management domain controls."""
    return [
        DCFControl(control_id="DCF-4", name="Version Control", description="Test", domain="Change Management"),
        DCFControl(control_id="DCF-5", name="Change Review", description="Test", domain="Change Management"),
        DCFControl(control_id="DCF-6", name="Change Approval", description="Test", domain="Change Management"),
    ]


@pytest.fixture
def crypto_controls():
    """Cryptography domain controls."""
    return [
        DCFControl(control_id="DCF-182", name="Encryption", description="Test", domain="Cryptography"),
        DCFControl(control_id="DCF-183", name="Key Management", description="Test", domain="Cryptography"),
    ]


class TestBuildCandidateList:
    """Test build_candidate_list function."""

    def test_primary_controls_always_included(self, change_mgmt_controls):
        """Primary controls should always be included."""
        primary = [
            ScoredControl(control=change_mgmt_controls[0], score=120.0),
            ScoredControl(control=change_mgmt_controls[1], score=80.0),
        ]

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=[],
            candidate_threshold=60.0,
            max_candidates=10,
        )

        assert len(candidates) == 2
        assert candidates[0].control.control_id == "DCF-4"  # Highest score first
        assert candidates[1].control.control_id == "DCF-5"

    def test_neighbor_same_domain_included(self, change_mgmt_controls):
        """Neighbor controls with same domain should be included."""
        primary = [ScoredControl(control=change_mgmt_controls[0], score=120.0)]

        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_controls[1], score=70.0)],
        )

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=[neighbor_pred],
            candidate_threshold=60.0,
            max_candidates=10,
        )

        assert len(candidates) == 2
        control_ids = {c.control.control_id for c in candidates}
        assert "DCF-4" in control_ids
        assert "DCF-5" in control_ids

    def test_neighbor_different_domain_excluded(self, change_mgmt_controls, crypto_controls):
        """Neighbor controls with different domain should not be included."""
        primary = [ScoredControl(control=change_mgmt_controls[0], score=120.0)]

        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=crypto_controls[0], score=90.0)],
        )

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=[neighbor_pred],
            candidate_threshold=60.0,
            max_candidates=10,
        )

        assert len(candidates) == 1
        assert candidates[0].control.control_id == "DCF-4"

    def test_neighbor_below_threshold_excluded(self, change_mgmt_controls):
        """Neighbor controls below candidate threshold should not be included."""
        primary = [ScoredControl(control=change_mgmt_controls[0], score=120.0)]

        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_controls[1], score=50.0)],  # Below 60
        )

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=[neighbor_pred],
            candidate_threshold=60.0,
            max_candidates=10,
        )

        assert len(candidates) == 1

    def test_duplicate_control_ids_deduplicated(self, change_mgmt_controls):
        """Same control ID should not appear twice."""
        primary = [ScoredControl(control=change_mgmt_controls[0], score=120.0)]

        # Same control in neighbor
        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_controls[0], score=90.0)],
        )

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=[neighbor_pred],
            candidate_threshold=60.0,
            max_candidates=10,
        )

        assert len(candidates) == 1

    def test_sorted_by_score_descending(self, change_mgmt_controls):
        """Candidates should be sorted by score descending."""
        primary = [
            ScoredControl(control=change_mgmt_controls[0], score=80.0),
            ScoredControl(control=change_mgmt_controls[1], score=120.0),
        ]

        neighbor_pred = PagePrediction(
            page_num=4,
            top_controls=[ScoredControl(control=change_mgmt_controls[2], score=100.0)],
        )

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=[neighbor_pred],
            candidate_threshold=60.0,
            max_candidates=10,
        )

        assert len(candidates) == 3
        assert candidates[0].score == 120.0
        assert candidates[1].score == 100.0
        assert candidates[2].score == 80.0

    def test_max_candidates_respected(self, change_mgmt_controls, crypto_controls):
        """Should cap at max_candidates."""
        # Create many controls
        all_controls = change_mgmt_controls + crypto_controls
        primary = [ScoredControl(control=c, score=100.0 - i * 5) for i, c in enumerate(all_controls)]

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=[],
            candidate_threshold=60.0,
            max_candidates=3,
        )

        assert len(candidates) == 3

    def test_multiple_neighbor_predictions(self, change_mgmt_controls):
        """Should process multiple neighbor predictions."""
        primary = [ScoredControl(control=change_mgmt_controls[0], score=120.0)]

        neighbor_preds = [
            PagePrediction(
                page_num=4,
                top_controls=[ScoredControl(control=change_mgmt_controls[1], score=70.0)],
            ),
            PagePrediction(
                page_num=6,
                top_controls=[ScoredControl(control=change_mgmt_controls[2], score=65.0)],
            ),
        ]

        candidates = build_candidate_list(
            primary_controls=primary,
            neighbor_predictions=neighbor_preds,
            candidate_threshold=60.0,
            max_candidates=10,
        )

        assert len(candidates) == 3
```

### 5.2 Implement to Pass (GREEN)

**Add to** `ai_services/scripts/experiments/control_detection/llm_decider.py`:

```python
def build_candidate_list(
    primary_controls: list[ScoredControl],
    neighbor_predictions: list[PagePrediction],
    candidate_threshold: float,
    max_candidates: int,
) -> list[ScoredControl]:
    """
    Build candidate list from primary + neighbor controls.

    Neighbor controls are included if they:
    - Score above candidate_threshold
    - Share domain with any primary control
    """
    candidates = list(primary_controls)
    seen_ids = {c.control.control_id for c in candidates}

    primary_domains = {c.control.domain for c in primary_controls if c.control.domain}

    for neighbor_pred in neighbor_predictions:
        for nc in neighbor_pred.top_controls:
            if nc.control.control_id in seen_ids:
                continue
            if nc.score < candidate_threshold:
                continue
            # Include if same domain as any primary control
            if nc.control.domain and nc.control.domain in primary_domains:
                candidates.append(nc)
                seen_ids.add(nc.control.control_id)

    # Sort by score, cap at max
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_candidates]
```

### 5.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_candidate_building.py -v
```

---

## Cycle 6: Page Triggering Logic

### 6.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_triggered_pages.py`

```python
"""Tests for page triggering logic."""

import pytest

from ai_services.scripts.experiments.control_detection.dcf_controls import DCFControl
from ai_services.scripts.experiments.control_detection.predictor import (
    ScoredControl,
    PagePrediction,
)
from ai_services.scripts.experiments.control_detection.llm_decider import (
    LLMDeciderConfig,
    get_triggered_pages,
)


@pytest.fixture
def controls():
    """Test controls."""
    return [
        DCFControl(control_id="DCF-4", name="Test 1", description="Test", domain="Change Management"),
        DCFControl(control_id="DCF-5", name="Test 2", description="Test", domain="Change Management"),
        DCFControl(control_id="DCF-182", name="Test 3", description="Test", domain="Cryptography"),
    ]


class TestGetTriggeredPages:
    """Test get_triggered_pages function."""

    def test_page_above_trigger_threshold_triggers(self, controls):
        """Page with control above trigger threshold should trigger."""
        config = LLMDeciderConfig(trigger_threshold=100.0, candidate_threshold=60.0)

        page_predictions = [
            PagePrediction(
                page_num=1,
                top_controls=[ScoredControl(control=controls[0], score=120.0)],
            )
        ]

        triggered = get_triggered_pages(page_predictions, config)

        assert 1 in triggered
        assert len(triggered[1]) == 1

    def test_page_below_trigger_threshold_not_triggered(self, controls):
        """Page with all controls below trigger threshold should not trigger."""
        config = LLMDeciderConfig(trigger_threshold=100.0, candidate_threshold=60.0)

        page_predictions = [
            PagePrediction(
                page_num=1,
                top_controls=[ScoredControl(control=controls[0], score=90.0)],
            )
        ]

        triggered = get_triggered_pages(page_predictions, config)

        assert 1 not in triggered

    def test_candidates_use_lower_threshold(self, controls):
        """Triggered page should include candidates above candidate_threshold."""
        config = LLMDeciderConfig(trigger_threshold=100.0, candidate_threshold=60.0)

        page_predictions = [
            PagePrediction(
                page_num=1,
                top_controls=[
                    ScoredControl(control=controls[0], score=120.0),  # Triggers
                    ScoredControl(control=controls[1], score=70.0),   # Candidate (above 60)
                    ScoredControl(control=controls[2], score=50.0),   # Not candidate (below 60)
                ],
            )
        ]

        triggered = get_triggered_pages(page_predictions, config)

        assert len(triggered[1]) == 2  # DCF-4 and DCF-5

    def test_max_candidates_respected(self, controls):
        """Should cap candidates at max_candidates."""
        config = LLMDeciderConfig(
            trigger_threshold=100.0,
            candidate_threshold=60.0,
            max_candidates=2,
        )

        page_predictions = [
            PagePrediction(
                page_num=1,
                top_controls=[
                    ScoredControl(control=controls[0], score=120.0),
                    ScoredControl(control=controls[1], score=80.0),
                    ScoredControl(control=controls[2], score=70.0),
                ],
            )
        ]

        triggered = get_triggered_pages(page_predictions, config)

        assert len(triggered[1]) == 2

    def test_multiple_pages_triggered(self, controls):
        """Multiple pages can trigger independently."""
        config = LLMDeciderConfig(trigger_threshold=100.0, candidate_threshold=60.0)

        page_predictions = [
            PagePrediction(
                page_num=1,
                top_controls=[ScoredControl(control=controls[0], score=120.0)],
            ),
            PagePrediction(
                page_num=3,
                top_controls=[ScoredControl(control=controls[2], score=110.0)],
            ),
        ]

        triggered = get_triggered_pages(page_predictions, config)

        assert 1 in triggered
        assert 3 in triggered

    def test_empty_predictions_returns_empty(self, controls):
        """Empty predictions should return empty dict."""
        config = LLMDeciderConfig()

        triggered = get_triggered_pages([], config)

        assert triggered == {}

    def test_candidates_sorted_by_score(self, controls):
        """Candidates should be in score order (from top_controls)."""
        config = LLMDeciderConfig(trigger_threshold=100.0, candidate_threshold=60.0)

        page_predictions = [
            PagePrediction(
                page_num=1,
                top_controls=[
                    ScoredControl(control=controls[0], score=120.0),
                    ScoredControl(control=controls[1], score=90.0),
                    ScoredControl(control=controls[2], score=70.0),
                ],
            )
        ]

        triggered = get_triggered_pages(page_predictions, config)

        # Should preserve order from top_controls (already sorted by predictor)
        assert triggered[1][0].score == 120.0
        assert triggered[1][1].score == 90.0
        assert triggered[1][2].score == 70.0
```

### 6.2 Implement to Pass (GREEN)

**Add to** `ai_services/scripts/experiments/control_detection/llm_decider.py`:

```python
def get_triggered_pages(
    page_predictions: list[PagePrediction],
    config: LLMDeciderConfig,
) -> dict[int, list[ScoredControl]]:
    """
    Get pages that trigger LLM calls and their candidate controls.

    Dual threshold strategy:
    - TRIGGER: Page needs at least one control >= trigger_threshold to run LLM
    - CANDIDATES: Once triggered, include all controls >= candidate_threshold

    This allows the LLM to "rescue" borderline retrieval results.
    """
    triggered = {}
    for page_pred in page_predictions:
        # Check if page triggers (any control above trigger threshold)
        has_trigger = any(
            sc.score >= config.trigger_threshold
            for sc in page_pred.top_controls
        )
        if has_trigger:
            # Collect candidates (lower threshold, capped)
            candidates = [
                sc for sc in page_pred.top_controls
                if sc.score >= config.candidate_threshold
            ][:config.max_candidates]
            triggered[page_pred.page_num] = candidates
    return triggered
```

### 6.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_triggered_pages.py -v
```

---

## Cycle 7: Decision Aggregation

**Note:** With multi-select, aggregation changes from "weighted voting to pick one winner" to "union of all selected controls with max confidence per control." The tests below need updating to reflect this.

### Aggregation Strategy (Multi-Select)

```
For each control selected across any page:
    1. Collect all page selections for this control
    2. Take the maximum confidence level
    3. Combine reasoning from pages that selected it
    4. Include in document-level result

Result: List of all controls found, each with their best confidence.
```

### 7.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_aggregation.py`

```python
"""Tests for decision aggregation (multi-select)."""
import pytest
from ai_services.scripts.experiments.control_detection.llm_decider import (
    ControlSelection, PageLLMDecision, DocumentLLMDecision,
    aggregate_decisions, CONFIDENCE_WEIGHTS,
)

class TestConfidenceWeights:
    def test_weight_ordering(self): ...  # high > medium > low
    def test_expected_values(self): ...  # {"high": 3, "medium": 2, "low": 1}

class TestAggregateDecisions:
    """Test union aggregation with max confidence per control."""
    def test_single_control_single_page(self): ...
    def test_same_control_multiple_pages_takes_max_confidence(self): ...
    def test_multiple_controls_across_pages_union(self): ...
    def test_empty_selections_across_pages(self): ...
    def test_empty_decisions_returns_empty(self): ...
    def test_aggregation_method_union_with_max_confidence(self): ...
    def test_page_decisions_preserved(self): ...
    def test_controls_sorted_by_confidence_then_page_count(self): ...
```

### 7.2 Implement to Pass (GREEN)

**Add to** `ai_services/scripts/experiments/control_detection/llm_decider.py`:

```python
from collections import defaultdict

CONFIDENCE_WEIGHTS = {"high": 3, "medium": 2, "low": 1}


def aggregate_decisions(page_decisions: list[PageLLMDecision]) -> DocumentLLMDecision:
    """Aggregate page decisions using union with max confidence per control.

    Multi-select: Each page can select multiple controls. We union all
    selected controls across all pages, taking the max confidence for
    each control.
    """
    if not page_decisions:
        return DocumentLLMDecision(
            selected_controls=(),
            page_decisions=(),
            aggregation_method="union_with_max_confidence",
        )

    # Track max confidence and page count per control
    max_confidence: dict[str, str] = {}
    page_counts: dict[str, int] = defaultdict(int)
    reasonings: dict[str, list[str]] = defaultdict(list)

    for decision in page_decisions:
        for selection in decision.selected_controls:
            control_id = selection.control_id
            page_counts[control_id] += 1
            reasonings[control_id].append(f"p{decision.page_num}: {selection.reasoning}")

            # Track highest confidence
            current_max = max_confidence.get(control_id)
            if current_max is None or CONFIDENCE_WEIGHTS[selection.confidence] > CONFIDENCE_WEIGHTS[current_max]:
                max_confidence[control_id] = selection.confidence

    if not max_confidence:
        return DocumentLLMDecision(
            selected_controls=(),
            page_decisions=tuple(page_decisions),
            aggregation_method="union_with_max_confidence",
        )

    # Build result: all controls found, sorted by confidence then page count
    selected_controls = tuple(
        ControlSelection(
            control_id=cid,
            confidence=max_confidence[cid],
            reasoning=f"{page_counts[cid]} page(s): {'; '.join(reasonings[cid][:2])}",  # Limit reasoning
        )
        for cid in sorted(
            max_confidence.keys(),
            key=lambda c: (CONFIDENCE_WEIGHTS[max_confidence[c]], page_counts[c]),
            reverse=True,
        )
    )

    return DocumentLLMDecision(
        selected_controls=selected_controls,
        page_decisions=tuple(page_decisions),
        aggregation_method="union_with_max_confidence",
    )
```

### 7.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_aggregation.py -v
```

---

## Cycle 8: LLM Decider (Mocked LLM)

### 8.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_llm_decider.py`

```python
"""Tests for LLMDecider with mocked LLM calls (multi-select)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from ai_services.scripts.experiments.control_detection.llm_decider import (
    LLMDecider, LLMDeciderConfig, NeighborInclusionConfig, PageLLMInput,
)

# Fixtures: controls (DCFControl[]), prompt_dir (Path), config (LLMDeciderConfig)

class TestLLMDeciderCreate:
    @patch("...genai.Client")
    def test_create_initializes_vertex_ai_client(self, mock_client): ...

class TestLLMDeciderBuildPageInputs:
    def test_builds_input_for_triggered_page(self): ...
    def test_includes_neighbor_pages_when_related(self): ...
    def test_excludes_neighbors_when_disabled(self): ...
    def test_respects_max_total_pages(self): ...

class TestLLMDeciderDecidePage:
    """Test decide_page with multi-select responses."""
    @pytest.mark.asyncio
    async def test_calls_llm_returns_multiple_selections(self): ...
    @pytest.mark.asyncio
    async def test_handles_empty_selection(self): ...
    @pytest.mark.asyncio
    async def test_parses_confidence_and_reasoning_per_control(self): ...

class TestLLMDeciderDecideDocument:
    @pytest.mark.asyncio
    async def test_orchestrates_multiple_pages_aggregates_union(self): ...
    @pytest.mark.asyncio
    async def test_raises_when_no_pages_trigger(self): ...
    @pytest.mark.asyncio
    async def test_concurrent_calls_limited_by_semaphore(self): ...
```

### 8.2 Implement to Pass (GREEN)

**Complete** `ai_services/scripts/experiments/control_detection/llm_decider.py`:

```python
"""LLM decision layer for control detection."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google import genai
from google.genai.types import GenerateContentConfig, Part

from ai_services.scripts.experiments.control_detection.predictor import (
    ScoredControl,
    PagePrediction,
)
from ai_services.scripts.experiments.control_detection.prompt_loader import PromptBundle


# ... (dataclasses from Cycle 3) ...
# ... (functions from Cycles 4-7) ...


class LLMDecider:
    """LLM-based control selection with page-level decisions."""

    def __init__(
        self,
        client: genai.Client,
        config: LLMDeciderConfig,
        prompt_dir: Path,
    ):
        self._client = client
        self._config = config
        self._prompt_dir = prompt_dir

    @classmethod
    def create(
        cls,
        config: LLMDeciderConfig,
        prompt_dir: Path,
        gcp_project: str,
        gcp_region: str,
    ) -> "LLMDecider":
        """Factory method using Vertex AI authentication."""
        client = genai.Client(
            vertexai=True,
            project=gcp_project,
            location=gcp_region,
        )
        return cls(client=client, config=config, prompt_dir=prompt_dir)

    def build_page_inputs(
        self,
        triggered_pages: dict[int, list[ScoredControl]],
        page_predictions: list[PagePrediction],
        page_images: list[tuple[int, bytes]],
    ) -> list[PageLLMInput]:
        """Build PageLLMInput for each triggered page with neighbor context."""
        # Index predictions and images by page number
        pred_by_page = {p.page_num: p for p in page_predictions}
        img_by_page = {page_num: img_bytes for page_num, img_bytes in page_images}
        all_page_nums = sorted(pred_by_page.keys())

        inputs = []
        neighbor_threshold = self._config.trigger_threshold * self._config.neighbor_config.threshold_ratio

        for page_num, candidates in triggered_pages.items():
            images = [(page_num, img_by_page[page_num])]
            context_pages = []

            if self._config.neighbor_config.enabled:
                # Check previous page
                idx = all_page_nums.index(page_num)
                if idx > 0:
                    prev_page = all_page_nums[idx - 1]
                    if should_include_neighbor(candidates, pred_by_page[prev_page], neighbor_threshold):
                        images.insert(0, (prev_page, img_by_page[prev_page]))
                        context_pages.append(prev_page)

                # Check next page
                if idx < len(all_page_nums) - 1:
                    next_page = all_page_nums[idx + 1]
                    if should_include_neighbor(candidates, pred_by_page[next_page], neighbor_threshold):
                        images.append((next_page, img_by_page[next_page]))
                        context_pages.append(next_page)

                # Cap at max_total_pages
                if len(images) > self._config.neighbor_config.max_total_pages:
                    # Keep primary + closest neighbors
                    images = images[:self._config.neighbor_config.max_total_pages]

            # Build candidate list with neighbor expansion
            neighbor_preds = [pred_by_page[p] for p in context_pages if p in pred_by_page]
            expanded_candidates = build_candidate_list(
                primary_controls=candidates,
                neighbor_predictions=neighbor_preds,
                candidate_threshold=self._config.candidate_threshold,
                max_candidates=self._config.max_candidates,
            )

            inputs.append(PageLLMInput(
                primary_page_num=page_num,
                images=tuple(images),
                controls=tuple(expanded_candidates),
                context_page_nums=tuple(context_pages),
            ))

        return inputs

    async def decide_page(self, page_input: PageLLMInput) -> PageLLMDecision:
        """Make LLM decision for a single page (multi-select)."""
        control_ids = [c.control.control_id for c in page_input.controls]
        controls_text = "\n".join(
            f"- {c.control.control_id}: {c.control.name} - {c.control.description}"
            for c in page_input.controls
        )
        context_pages_text = ", ".join(str(p) for p in page_input.context_page_nums) or "none"

        context = {
            "page_num": page_input.primary_page_num,
            "context_pages": context_pages_text,
            "controls": controls_text,
            "CONTROL_IDS": control_ids,
        }

        bundle = PromptBundle.load(self._prompt_dir, context)

        # Build content parts with labeled images
        parts = []
        for i, (pg_num, img_bytes) in enumerate(page_input.images):
            label = "PRIMARY" if pg_num == page_input.primary_page_num else "CONTEXT"
            parts.append(Part.from_text(f"[Image {i + 1}: {label} page {pg_num}]"))
            parts.append(Part.from_bytes(data=img_bytes, mime_type="image/png"))
        parts.append(Part.from_text(bundle.user))

        response = await self._client.aio.models.generate_content(
            model=self._config.model,
            contents=parts,
            config=GenerateContentConfig(
                system_instruction=bundle.system,
                temperature=self._config.temperature,
                response_mime_type="application/json",
                response_schema=bundle.response_schema,
            ),
        )

        # Parse multi-select response
        parsed = response.parsed
        selected_controls = tuple(
            ControlSelection(
                control_id=sel.control_id,
                confidence=sel.confidence,
                reasoning=sel.reasoning,
            )
            for sel in parsed.selected_controls
        )

        return PageLLMDecision(
            page_num=page_input.primary_page_num,
            selected_controls=selected_controls,
            candidate_control_ids=tuple(control_ids),
            context_page_nums=page_input.context_page_nums,
        )

    async def decide_document(
        self,
        page_predictions: list[PagePrediction],
        page_images: list[tuple[int, bytes]],
    ) -> DocumentLLMDecision:
        """Make document-level decision via per-page LLM calls."""
        # 1. Find pages that trigger LLM calls
        triggered = get_triggered_pages(page_predictions, self._config)

        if not triggered:
            raise ValueError("No pages have controls above trigger threshold")

        # 2. Build page inputs with neighbor context
        page_inputs = self.build_page_inputs(triggered, page_predictions, page_images)

        # 3. Make parallel LLM calls with concurrency limit
        semaphore = asyncio.Semaphore(self._config.max_concurrent)

        async def bounded_decide(page_input: PageLLMInput) -> PageLLMDecision:
            async with semaphore:
                return await self.decide_page(page_input)

        page_decisions = await asyncio.gather(
            *[bounded_decide(pi) for pi in page_inputs]
        )

        # 4. Aggregate page decisions
        return aggregate_decisions(list(page_decisions))
```

### 8.3 Verify & Refactor

```bash
uv run pytest tests/scripts/experiments/control_detection/test_llm_decider.py -v
```

---

## Cycle 9: Integration & CLI (Final)

### 9.1 Write Tests First (RED)

**File:** `tests/scripts/experiments/control_detection/test_llm_decider_integration.py`

```python
"""Integration tests for LLM decider with run_experiment.py."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

class TestRunExperimentLLMArgs:
    def test_use_llm_flag_parsed(self): ...
    def test_default_llm_values(self): ...
    def test_custom_thresholds(self): ...
    def test_neighbor_inclusion_disabled(self): ...

class TestRunExperimentLLMIntegration:
    @pytest.mark.asyncio
    async def test_llm_flow_when_enabled(self): ...  # Verify decider.decide_document called
    @pytest.mark.asyncio
    async def test_embedding_only_when_llm_disabled(self): ...
```

### 9.2 Implement to Pass (GREEN)

**Modify:** `ai_services/scripts/experiments/control_detection/run_experiment.py`

Add CLI arguments and integrate LLMDecider:

```python
# Add to argument parser
parser.add_argument("--use-llm", action="store_true", help="Enable LLM decision layer")
parser.add_argument("--gcp-project", type=str, help="GCP project ID for Vertex AI")
parser.add_argument("--gcp-region", type=str, default="us-central1", help="GCP region")
parser.add_argument("--llm-model", type=str, default="gemini-3.0-pro", help="Gemini model")
parser.add_argument("--trigger-threshold", type=float, default=100.0, help="Score to trigger LLM")
parser.add_argument("--candidate-threshold", type=float, default=60.0, help="Score for candidates")
parser.add_argument("--max-candidates", type=int, default=10, help="Max candidates per LLM call")
parser.add_argument("--no-neighbor-inclusion", action="store_true", help="Disable neighbor inclusion")
parser.add_argument("--neighbor-threshold-ratio", type=float, default=0.5, help="Neighbor threshold ratio")
parser.add_argument("--max-pages-per-call", type=int, default=5, help="Max pages per LLM call")
parser.add_argument("--max-concurrent", type=int, default=10, help="Max concurrent LLM calls")

# In main flow, after ColModernVBERT predictions:
if args.use_llm:
    from ai_services.scripts.experiments.control_detection.llm_decider import (
        LLMDecider,
        LLMDeciderConfig,
        NeighborInclusionConfig,
    )

    config = LLMDeciderConfig(
        model=args.llm_model,
        trigger_threshold=args.trigger_threshold,
        candidate_threshold=args.candidate_threshold,
        max_candidates=args.max_candidates,
        neighbor_config=NeighborInclusionConfig(
            enabled=not args.no_neighbor_inclusion,
            threshold_ratio=args.neighbor_threshold_ratio,
            max_total_pages=args.max_pages_per_call,
        ),
        max_concurrent=args.max_concurrent,
    )

    prompt_dir = Path(__file__).parent / "prompts" / "select_control"
    decider = LLMDecider.create(
        config=config,
        prompt_dir=prompt_dir,
        gcp_project=args.gcp_project,
        gcp_region=args.gcp_region,
    )

    doc_decision = asyncio.run(decider.decide_document(page_predictions, page_images))
    # Multi-select: doc_decision.selected_controls is tuple[ControlSelection, ...]
    final_controls = [sel.control_id for sel in doc_decision.selected_controls]
else:
    # Use embedding-only prediction (single top control)
    final_controls = [top_prediction.control_id] if top_prediction else []
```

### 9.3 Create Prompt Files

**Create** `ai_services/scripts/experiments/control_detection/prompts/select_control/system`:

**Note:** The system prompt content is loaded from `distilled_mapping_instructions.md` which contains the synthesized control mapping protocol. This file is maintained separately to allow iteration on the mapping methodology without changing code.

```
# Load from: planning/llm_control_detection/distilled_mapping_instructions.md
# Contains:
# - The Critical Distinction (topic similarity ≠ valid match)
# - Binding Language requirements (must/shall vs should/may)
# - Selection Logic (per-control evaluation)
# - Confidence Guide (high/medium/low criteria)
# - Red Flags (when to select no controls)
# - Quick Heuristics
# - Quality Over Quantity guidance
```

**Create** `ai_services/scripts/experiments/control_detection/prompts/select_control/user`:
```
Analyze this policy document page and select ALL controls that this page adequately addresses.

<candidate_controls>
{controls}
</candidate_controls>

<page_info>
Primary page: {page_num}
Context pages: {context_pages}
</page_info>

<instructions>
1. Focus your analysis on page {page_num} (the primary page)
2. Use any context pages only for additional understanding
3. Evaluate EACH candidate control independently using the selection logic
4. Select ALL controls where the page contains binding mandates (must/shall/required)
5. A page may match zero, one, or many controls
6. For each selected control, provide confidence and brief reasoning
7. Return an empty array if no controls are adequately addressed
</instructions>
```

**Create** `ai_services/scripts/experiments/control_detection/prompts/select_control/response.json`:
```json
{
  "type": "object",
  "properties": {
    "selected_controls": {
      "type": "array",
      "description": "Controls that this page adequately addresses. Empty array if none match.",
      "items": {
        "type": "object",
        "properties": {
          "control_id": {
            "type": "string",
            "enum": "CONTROL_IDS",
            "description": "The control_id of a matching control"
          },
          "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence level for this specific control"
          },
          "reasoning": {
            "type": "string",
            "description": "Brief explanation of why this control matches"
          }
        },
        "required": ["control_id", "confidence", "reasoning"]
      }
    }
  },
  "required": ["selected_controls"]
}
```

**Note:** The `CONTROL_IDS` enum is dynamically replaced at runtime with the actual candidate control IDs for this page (see Cycle 2: Prompt Loader).

### 9.4 Verify All Tests Pass

```bash
# Run all tests
uv run pytest tests/scripts/experiments/control_detection/ -v

# Run with coverage
uv run pytest tests/scripts/experiments/control_detection/ --cov=ai_services.scripts.experiments.control_detection
```

---

## Files to Create/Modify Summary

| File | Action | TDD Cycle |
|------|--------|-----------|
| `tests/scripts/experiments/control_detection/test_dcf_controls.py` | **CREATE** | 1 |
| `dcf_controls.py` | MODIFY - Add `domain` field | 1 |
| `tests/scripts/experiments/control_detection/test_prompt_loader.py` | **CREATE** | 2 |
| `prompt_loader.py` | **CREATE** | 2 |
| `tests/scripts/experiments/control_detection/test_llm_decider_config.py` | **CREATE** | 3 |
| `llm_decider.py` | **CREATE** (dataclasses incl. `ControlSelection`) | 3 |
| `tests/scripts/experiments/control_detection/test_neighbor_inclusion.py` | **CREATE** | 4 |
| `llm_decider.py` | MODIFY - Add `should_include_neighbor()` | 4 |
| `tests/scripts/experiments/control_detection/test_candidate_building.py` | **CREATE** | 5 |
| `llm_decider.py` | MODIFY - Add `build_candidate_list()` | 5 |
| `tests/scripts/experiments/control_detection/test_triggered_pages.py` | **CREATE** | 6 |
| `llm_decider.py` | MODIFY - Add `get_triggered_pages()` | 6 |
| `tests/scripts/experiments/control_detection/test_aggregation.py` | **CREATE** | 7 |
| `llm_decider.py` | MODIFY - Add `aggregate_decisions()` (multi-select) | 7 |
| `tests/scripts/experiments/control_detection/test_llm_decider.py` | **CREATE** | 8 |
| `llm_decider.py` | MODIFY - Add `LLMDecider` class | 8 |
| `tests/scripts/experiments/control_detection/test_llm_decider_integration.py` | **CREATE** | 9 |
| `run_experiment.py` | MODIFY - Add CLI args, integrate decider | 9 |
| `prompts/select_control/system` | **CREATE** - Load from `distilled_mapping_instructions.md` | 9 |
| `prompts/select_control/user` | **CREATE** | 9 |
| `prompts/select_control/response.json` | **CREATE** (multi-select schema) | 9 |

### Prompt Methodology Files

| File | Purpose |
|------|---------|
| `planning/llm_control_detection/distilled_mapping_instructions.md` | **EXISTS** - Distilled control mapping protocol for system prompt |
| `results/teach_llm_to_map_controls/synthesized_control_mapping_instructions.md` | Full methodology (reference, not used in prompt) |

---

## TDD Workflow Summary

For each cycle:

1. **RED**: Write failing tests that define expected behavior
2. **GREEN**: Write minimal code to make tests pass
3. **REFACTOR**: Clean up while keeping tests green

```bash
# Per-cycle verification
uv run pytest tests/scripts/experiments/control_detection/test_<cycle>.py -v

# Full test suite
uv run pytest tests/scripts/experiments/control_detection/ -v

# With coverage
uv run pytest tests/scripts/experiments/control_detection/ --cov=ai_services.scripts.experiments.control_detection --cov-report=term-missing
```

---

## Dependencies

Already available in `gcp` group:
- `google-genai>=1.46.0`

Run with:
```bash
uv sync --group gcp --group ai
```

## Usage

```bash
# Run with LLM decision layer
uv run --group gcp --group ai python ai_services/scripts/experiments/control_detection/run_experiment.py \
    --use-llm \
    --gcp-project your-project-id \
    --gcp-region us-central1 \
    --trigger-threshold 100.0 \
    --candidate-threshold 60.0 \
    --row 4

# Full experiment with LLM
uv run --group gcp --group ai python ai_services/scripts/experiments/control_detection/run_experiment.py \
    --use-llm \
    --gcp-project your-project-id \
    --save
```

## Default Configuration

- **Model**: `gemini-3.0-pro` (Gemini 3 Pro)
- **Multi-select**: Each page can match zero, one, or many controls
- **Dual thresholds**: `trigger=100.0`, `candidate=60.0` (allows LLM to "rescue" borderline results)
- **Max candidates**: `10` per LLM call
- **Neighbor inclusion**: `enabled` with `threshold_ratio=0.5`, `max_total_pages=5`
- **Temperature**: `0.1` (deterministic selection)
- **Max concurrent**: `10` (avoid rate limiting)
- **Aggregation**: `union_with_max_confidence` - union all selected controls, keep highest confidence per control
