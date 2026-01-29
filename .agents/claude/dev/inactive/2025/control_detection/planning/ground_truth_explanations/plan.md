# Plan: Ground Truth Control Mapping Reasons Generator

## Objective

Create a script that iterates through template policy PDFs and, for each ground truth DCF control, uses an LLM to enumerate the reasons why that control maps to the policy, with page number citations.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Control Mapping Reasons Generator                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
     ┌──────────┐            ┌──────────┐            ┌──────────┐
     │ Policy 1 │            │ Policy 2 │            │ Policy N │
     │  (PDF)   │            │  (PDF)   │  ...       │  (PDF)   │
     └────┬─────┘            └────┬─────┘            └────┬─────┘
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │Upload to    │         │Upload to    │         │Upload to    │
   │Gemini Cache │         │Gemini Cache │         │Gemini Cache │
   └─────────────┘         └─────────────┘         └─────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ For each ground truth DCF control:                          │
   │   - Submit LLM request with PDF in cache                    │
   │   - Get reasons + page citations                            │
   │   - Append to policy_name_reasons.md                        │
   └─────────────────────────────────────────────────────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │Delete from  │         │Delete from  │         │Delete from  │
   │Gemini Cache │         │Gemini Cache │         │Gemini Cache │
   └─────────────┘         └─────────────┘         └─────────────┘
```

## Key Paths

| Component | Path |
|-----------|------|
| Template PDFs | `ai_services/scripts/experiments/control_detection/files/policies/template_policies/` |
| Ground Truth Mapping | `ai_services/scripts/experiments/control_detection/files/experiments/template_policies/eval_to_policy_mapping.json` |
| DCF Controls CSV | `ai_services/scripts/experiments/control_detection/files/dcf_controls.csv` |
| Output Directory | `ai_services/scripts/experiments/control_detection/files/experiments/template_policies/parsed_policies/` |
| JSON Responses | `ai_services/scripts/experiments/control_detection/files/policies/template_policies/{policy_name}/responses/` |
| Script Location | `ai_services/scripts/experiments/control_detection/control_mapping_reasons/` |

## Output Structure

```
template_policies/
├── Asset_Management_Policy/
│   ├── Asset_Management_Policy.pdf
│   └── responses/                    # Raw LLM JSON responses
│       ├── DCF-4.json
│       ├── DCF-5.json
│       └── ...
├── Data_Protection_Policy/
│   ├── Data_Protection_Policy.pdf
│   └── responses/
│       ├── DCF-107.json
│       ├── DCF-108.json
│       └── ...
└── ...

parsed_policies/                      # Aggregated markdown files
├── Asset_Management_Policy_reasons.md
├── Data_Protection_Policy_reasons.md
└── ...
```

## File Structure

```
ai_services/scripts/experiments/control_detection/control_mapping_reasons/
├── __init__.py
├── config.py                  # Configuration dataclass
├── cache_manager.py           # Gemini context cache management
├── prompt_loader.py           # PromptBundle loading (from disk)
├── reason_generator.py        # Main orchestration logic
├── json_writer.py             # Raw JSON response writer
├── output_writer.py           # Markdown file writer
├── run.py                     # CLI entry point
└── prompts/
    └── control_reasons/
        ├── system             # System prompt
        ├── user               # User prompt with {PLACEHOLDERS}
        └── response.json      # Structured output schema
```

## Data Flow

1. **Load ground truth mapping**: Read `eval_to_policy_mapping.json` to get list of policies with their ground truth controls
2. **For N policies in parallel** (configurable):
   - Upload PDF to Gemini context cache
   - For each ground truth control:
     - Load prompt from disk with context placeholders
     - Submit LLM request referencing cached PDF
     - **Save raw JSON response to `{policy_dir}/responses/{DCF_ID}.json`**
     - Parse structured response
     - Append to `{policy_name}_reasons.md`
   - Delete PDF from context cache

## Implementation Plan

### TDD Cycle 1: Configuration

**Test**: `tests/scripts/experiments/control_detection/control_mapping_reasons/test_config.py`

```python
class TestConfig:
    def test_default_parallelism(self):
        config = ReasonGeneratorConfig()
        assert config.max_parallel_policies == 3

    def test_configurable_parallelism(self):
        config = ReasonGeneratorConfig(max_parallel_policies=1)
        assert config.max_parallel_policies == 1

    def test_paths_exist(self):
        config = ReasonGeneratorConfig()
        assert config.template_policies_dir.exists()
        assert config.ground_truth_mapping.exists()
```

**Implementation**: `config.py`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ReasonGeneratorConfig:
    max_parallel_policies: int = 3
    max_parallel_controls: int = 5          # Controls processed in parallel per policy
    max_retries: int = 3                    # Retry failed LLM calls
    model: str = "gemini-2.5-pro"           # Official model name, supports caching
    cache_prefix: str = "control_reasons_"  # Prefix for cache display names (for cleanup)
    template_policies_dir: Path = FILES_DIR / "policies" / "template_policies"
    ground_truth_mapping: Path = EXPERIMENTS_DIR / "eval_to_policy_mapping.json"
    output_dir: Path = EXPERIMENTS_DIR / "parsed_policies"
    prompts_dir: Path = SCRIPT_DIR / "prompts" / "control_reasons"
```

### TDD Cycle 2: Cache Manager

**Test**: `test_cache_manager.py`

```python
class TestCacheManager:
    @pytest.mark.asyncio
    async def test_upload_pdf_returns_cache_name(self, mock_genai_client):
        manager = GeminiCacheManager(client=mock_genai_client)
        cache_name = await manager.upload_pdf(pdf_bytes, display_name="test.pdf")
        assert cache_name.startswith("cachedContents/")

    @pytest.mark.asyncio
    async def test_delete_cache_removes_content(self, mock_genai_client):
        manager = GeminiCacheManager(client=mock_genai_client)
        await manager.delete_cache("cachedContents/abc123")
        mock_genai_client.caches.delete.assert_called_with(name="cachedContents/abc123")
```

**Implementation**: `cache_manager.py`

```python
class GeminiCacheManager:
    """Manages Gemini context cache for PDFs."""

    def __init__(self, client: genai.Client, model: str = "gemini-1.5-pro-002"):
        self.client = client
        self.model = model

    async def upload_pdf(self, pdf_bytes: bytes, display_name: str) -> str:
        """Upload PDF to context cache, return cache name."""
        cached_content = await self.client.aio.caches.create(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")]
                )
            ],
            config=types.CreateCachedContentConfig(
                display_name=display_name,
                ttl="3600s",  # 1 hour
            )
        )
        return cached_content.name

    async def delete_cache(self, cache_name: str) -> None:
        """Delete cached content by name."""
        await self.client.aio.caches.delete(name=cache_name)

    async def cleanup_orphaned_caches(self, prefix: str) -> int:
        """Delete all caches with the given prefix. Returns count deleted."""
        deleted = 0
        async for cache in self.client.aio.caches.list():
            if cache.display_name and cache.display_name.startswith(prefix):
                await self.delete_cache(cache.name)
                deleted += 1
        return deleted
```

### TDD Cycle 3: Prompt Loader

**Test**: `test_prompt_loader.py`

```python
class TestPromptLoader:
    def test_load_substitutes_placeholders(self, tmp_path):
        (tmp_path / "system").write_text("You are a compliance expert.")
        (tmp_path / "user").write_text("Policy: {POLICY_NAME}\nControl: {CONTROL_ID}")
        (tmp_path / "response.json").write_text('{"type": "object"}')

        context = {"POLICY_NAME": "Data Protection", "CONTROL_ID": "DCF-107"}
        bundle = PromptBundle.load(tmp_path, context)

        assert "Data Protection" in bundle.user
        assert "DCF-107" in bundle.user
```

**Implementation**: `prompt_loader.py` - Use existing PromptBundle pattern from llm_control_detection.md

### TDD Cycle 4: Output Writer

**Test**: `test_output_writer.py`

```python
class TestOutputWriter:
    def test_creates_new_file_with_header(self, tmp_path):
        writer = MarkdownOutputWriter(output_dir=tmp_path)
        writer.start_policy("Data Protection Policy")

        output_file = tmp_path / "Data_Protection_Policy_reasons.md"
        assert output_file.exists()
        content = output_file.read_text()
        assert "# Data Protection Policy" in content

    def test_appends_control_reasons(self, tmp_path):
        writer = MarkdownOutputWriter(output_dir=tmp_path)
        writer.start_policy("Test Policy")
        writer.append_control_reasons(
            control_id="DCF-107",
            control_name="Data Classification",
            reasons=["Mentions data categories", "References classification levels"],
            page_citations=[1, 2, 3]
        )

        content = (tmp_path / "Test_Policy_reasons.md").read_text()
        assert "## DCF-107" in content
        assert "Mentions data categories" in content
        assert "Pages: 1, 2, 3" in content
```

**Implementation**: `output_writer.py`

```python
class MarkdownOutputWriter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._current_file: Path | None = None
        self._missed_controls: list[tuple[str, str, str]] = []  # (id, name, reason)

    def start_policy(self, policy_name: str) -> None:
        safe_name = policy_name.replace(" ", "_").replace("/", "_")
        self._current_file = self.output_dir / f"{safe_name}_reasons.md"
        self._current_file.write_text(f"# {policy_name}\n\nControl Mapping Reasons\n\n")
        self._missed_controls = []

    def append_control_reasons(
        self,
        control_id: str,
        control_name: str,
        reasons: list[ReasonWithEvidence],  # Each reason has its own page citations
    ) -> None:
        """Append control with per-reason page citations (not collapsed)."""
        with self._current_file.open("a") as f:
            f.write(f"## {control_id}: {control_name}\n\n")
            for reason in reasons:
                f.write(f"- **{reason.reason}**\n")
                f.write(f"  - Evidence: \"{reason.evidence}\"\n")
                f.write(f"  - Pages: {', '.join(map(str, reason.page_numbers))}\n")
            f.write("\n---\n\n")

    def append_missed_control(
        self,
        control_id: str,
        control_name: str,
        unmapped_reason: str
    ) -> None:
        """Record a ground truth control that the LLM failed to verify (False Negative)."""
        self._missed_controls.append((control_id, control_name, unmapped_reason))

    def finalize(self) -> None:
        """Write missed controls section at end of file."""
        if not self._missed_controls:
            return
        with self._current_file.open("a") as f:
            f.write("\n# Missed Controls (LLM False Negatives)\n\n")
            f.write("These ground truth controls were NOT verified by the LLM.\n\n")
            for control_id, control_name, reason in self._missed_controls:
                f.write(f"## {control_id}: {control_name}\n\n")
                f.write(f"**LLM's reason for not mapping:** {reason}\n\n")
                f.write("---\n\n")
```

### TDD Cycle 4b: JSON Response Writer

**Test**: `test_json_writer.py`

```python
class TestJsonResponseWriter:
    def test_creates_responses_directory(self, tmp_path):
        writer = JsonResponseWriter(policy_dir=tmp_path)
        writer.ensure_responses_dir()
        assert (tmp_path / "responses").exists()

    def test_saves_response_with_dcf_id_in_filename(self, tmp_path):
        writer = JsonResponseWriter(policy_dir=tmp_path)
        raw_response = {"is_mapped": True, "reasons": [...]}
        writer.save_response("DCF-107", raw_response)

        response_file = tmp_path / "responses" / "DCF-107.json"
        assert response_file.exists()
        saved = json.loads(response_file.read_text())
        assert saved["is_mapped"] == True
```

**Implementation**: `json_writer.py`

```python
import json
from pathlib import Path
from typing import Any

class JsonResponseWriter:
    """Saves raw LLM JSON responses to disk for debugging and reprocessing."""

    def __init__(self, policy_dir: Path):
        self.policy_dir = policy_dir
        self.responses_dir = policy_dir / "responses"

    def ensure_responses_dir(self) -> None:
        """Create responses directory if it doesn't exist."""
        self.responses_dir.mkdir(parents=True, exist_ok=True)

    def save_response(self, control_id: str, raw_response: dict[str, Any]) -> Path:
        """
        Save raw LLM response to JSON file.

        Args:
            control_id: DCF control ID (e.g., "DCF-107")
            raw_response: Raw structured output from LLM

        Returns:
            Path to saved JSON file
        """
        self.ensure_responses_dir()
        # Sanitize control_id for filename (handle potential slashes, etc.)
        safe_id = control_id.replace("/", "_").replace("\\", "_")
        output_file = self.responses_dir / f"{safe_id}.json"
        output_file.write_text(json.dumps(raw_response, indent=2))
        return output_file

    def response_exists(self, control_id: str) -> bool:
        """Check if response already exists (for resume functionality)."""
        safe_id = control_id.replace("/", "_").replace("\\", "_")
        return (self.responses_dir / f"{safe_id}.json").exists()

    def load_response(self, control_id: str) -> dict[str, Any] | None:
        """Load existing response if it exists."""
        safe_id = control_id.replace("/", "_").replace("\\", "_")
        response_file = self.responses_dir / f"{safe_id}.json"
        if response_file.exists():
            return json.loads(response_file.read_text())
        return None
```

### TDD Cycle 5: Reason Generator (Core Logic)

**Test**: `test_reason_generator.py`

```python
class TestReasonGenerator:
    @pytest.mark.asyncio
    async def test_generates_reasons_for_single_control(self, mock_genai_client, tmp_path):
        # Setup mocks
        mock_genai_client.aio.caches.create.return_value = MagicMock(name="cachedContents/abc")
        mock_genai_client.aio.models.generate_content.return_value = MagicMock(
            parsed=MagicMock(
                reasons=["Policy describes data handling", "References encryption"],
                page_numbers=[1, 2]
            )
        )

        generator = ReasonGenerator(config=config, client=mock_genai_client)
        result = await generator.generate_for_control(
            cache_name="cachedContents/abc",
            control_id="DCF-107",
            control_name="Data Classification",
            control_description="...",
            policy_name="Data Protection Policy"
        )

        assert len(result.reasons) == 2
        assert 1 in result.page_numbers
```

**Implementation**: `reason_generator.py`

```python
import random

@dataclass(frozen=True, slots=True, kw_only=True)
class ReasonWithEvidence:
    """A single reason with its own evidence and page citations."""
    reason: str
    evidence: str
    page_numbers: tuple[int, ...]

@dataclass(frozen=True, slots=True, kw_only=True)
class ControlReasons:
    control_id: str
    control_name: str
    is_mapped: bool
    reasons: tuple[ReasonWithEvidence, ...]  # Each reason has its own citations
    unmapped_reason: str | None = None  # Present when is_mapped=False

class ReasonGenerator:
    def __init__(self, config: ReasonGeneratorConfig, client: genai.Client):
        self.config = config
        self.client = client
        self.cache_manager = GeminiCacheManager(client, model=config.model)

    async def process_policy(self, policy_name: str, pdf_path: Path, controls: list[DCFControl]) -> None:
        """Process a single policy - upload, process controls in parallel, cleanup."""
        pdf_bytes = pdf_path.read_bytes()

        # Cache creation failure = fail fast (critical error)
        display_name = f"{self.config.cache_prefix}{policy_name}"
        cache_name = await self.cache_manager.upload_pdf(pdf_bytes, display_name)

        # Register cache for cleanup on interrupt (SIGINT/SIGTERM)
        _active_caches.append(cache_name)

        try:
            # Set up writers
            output_writer = MarkdownOutputWriter(self.config.output_dir)
            output_writer.start_policy(policy_name)

            # JSON writer saves to responses/ directory alongside the PDF
            json_writer = JsonResponseWriter(policy_dir=pdf_path.parent)

            # Process controls in parallel with semaphore
            semaphore = asyncio.Semaphore(self.config.max_parallel_controls)

            async def process_control(control: DCFControl) -> ControlReasons | None:
                async with semaphore:
                    return await self._generate_with_retry(
                        cache_name=cache_name,
                        control=control,
                        policy_name=policy_name,
                        json_writer=json_writer,  # Pass writer for saving raw responses
                    )

            results = await asyncio.gather(
                *[process_control(c) for c in controls],
                return_exceptions=True
            )

            # Sort results by control ID for stable, deterministic output
            valid_results = [r for r in results if isinstance(r, ControlReasons)]
            valid_results.sort(key=lambda r: r.control_id)

            # Write results - track both mapped and unmapped (False Negatives)
            for result in valid_results:
                if result.is_mapped:
                    output_writer.append_control_reasons(
                        control_id=result.control_id,
                        control_name=result.control_name,
                        reasons=list(result.reasons),
                    )
                else:
                    # False Negative: LLM didn't verify a ground truth control
                    output_writer.append_missed_control(
                        control_id=result.control_id,
                        control_name=result.control_name,
                        unmapped_reason=result.unmapped_reason or "No reason provided"
                    )

            # Log errors separately
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Failed to process control: {result}")

            output_writer.finalize()  # Write missed controls section
        finally:
            # Shield cache deletion from cancellation to prevent orphaned caches
            await asyncio.shield(self.cache_manager.delete_cache(cache_name))
            # Unregister cache after successful deletion
            if cache_name in _active_caches:
                _active_caches.remove(cache_name)

    async def _generate_with_retry(
        self,
        cache_name: str,
        control: DCFControl,
        policy_name: str,
        json_writer: JsonResponseWriter,
    ) -> ControlReasons | None:
        """Generate reasons with retry logic. Returns None on final failure."""
        for attempt in range(self.config.max_retries):
            try:
                # Get raw response from LLM
                raw_response = await self._call_llm(
                    cache_name=cache_name,
                    control_id=control.control_id,
                    control_name=control.name,
                    control_description=control.description,
                    policy_name=policy_name
                )

                # Save raw JSON to disk BEFORE parsing
                json_writer.save_response(control.control_id, raw_response)

                # Parse into domain object
                return self._parse_response(
                    control_id=control.control_id,
                    control_name=control.name,
                    raw_response=raw_response
                )
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Retry {attempt + 1}/{self.config.max_retries} for {control.control_id}: {e}")
                    # Exponential backoff with jitter to prevent thundering herd
                    base_delay = 2 ** attempt
                    jitter = random.uniform(0, base_delay * 0.5)
                    await asyncio.sleep(base_delay + jitter)
                else:
                    logger.error(f"Failed after {self.config.max_retries} retries: {control.control_id}")
                    return None

    def _parse_response(
        self, control_id: str, control_name: str, raw_response: dict
    ) -> ControlReasons:
        """Parse raw LLM response into ControlReasons domain object."""
        reasons = tuple(
            ReasonWithEvidence(
                reason=r["reason"],
                evidence=r["evidence"],
                page_numbers=tuple(r["page_numbers"]),
            )
            for r in raw_response.get("reasons", [])
        )
        return ControlReasons(
            control_id=control_id,
            control_name=control_name,
            is_mapped=raw_response["is_mapped"],
            reasons=reasons,
            unmapped_reason=raw_response.get("unmapped_reason"),
        )
```

### TDD Cycle 6: CLI Entry Point

**Test**: `test_run.py`

```python
class TestCLI:
    def test_single_policy_single_control_mode(self, mock_generator):
        result = runner.invoke(app, [
            "--policy", "Data Protection Policy",
            "--control", "DCF-107",
            "--parallelism", "1"
        ])
        assert result.exit_code == 0

    def test_all_policies_mode(self, mock_generator):
        result = runner.invoke(app, ["--all", "--parallelism", "3"])
        assert result.exit_code == 0
```

**Implementation**: `run.py`

```python
import asyncio
import signal
import typer
from typing import Optional
from tqdm.asyncio import tqdm

app = typer.Typer()

# Track active caches for cleanup on interrupt
_active_caches: list[str] = []
_cache_manager: GeminiCacheManager | None = None

async def cleanup_on_exit():
    """Clean up any active caches on SIGINT/SIGTERM."""
    if _cache_manager and _active_caches:
        for cache_name in _active_caches:
            try:
                await _cache_manager.delete_cache(cache_name)
            except Exception:
                pass  # Best effort cleanup

@app.command()
def main(
    policy: Optional[str] = typer.Option(None, help="Single policy name to process"),
    control: Optional[str] = typer.Option(None, help="Single control ID to process"),
    all_policies: bool = typer.Option(False, "--all", help="Process all policies"),
    parallelism: int = typer.Option(3, "-n", help="Number of policies to process in parallel"),
    control_parallelism: int = typer.Option(5, "-c", help="Number of controls to process in parallel per policy"),
    model: str = typer.Option("gemini-2.5-pro", "--model", "-m", help="Gemini model to use"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Clean up orphaned caches and exit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be processed without running"),
):
    """Generate control mapping reasons for template policies."""
    config = ReasonGeneratorConfig(
        max_parallel_policies=parallelism,
        max_parallel_controls=control_parallelism,
        model=model,
    )

    if cleanup:
        asyncio.run(run_cleanup(config))
        return

    if dry_run:
        asyncio.run(run_dry_run(config, policy, control, all_policies))
        return

    asyncio.run(run_generator(config, policy, control, all_policies))

async def run_dry_run(config, policy, control, all_policies) -> None:
    """Show what would be processed without actually running."""
    # Load ground truth mapping and count policies/controls
    mapping = load_ground_truth_mapping(config.ground_truth_mapping)
    policies_to_process = filter_policies(mapping, policy, all_policies)

    total_controls = sum(len(p.controls) for p in policies_to_process)
    typer.echo(f"Would process {len(policies_to_process)} policies, {total_controls} controls")
    typer.echo(f"Model: {config.model}")
    typer.echo(f"Max concurrent LLM calls: {config.max_parallel_policies * config.max_parallel_controls}")

async def run_cleanup(config: ReasonGeneratorConfig) -> None:
    """Clean up orphaned caches from previous interrupted runs."""
    client = genai.Client()
    cache_manager = GeminiCacheManager(client, model=config.model)
    deleted = await cache_manager.cleanup_orphaned_caches(config.cache_prefix)
    typer.echo(f"Deleted {deleted} orphaned cache(s)")

async def run_generator(config, policy, control, all_policies) -> None:
    """Main generator with signal handling."""
    global _cache_manager

    # Set up signal handlers for graceful cleanup
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(cleanup_on_exit()))

    client = genai.Client()
    _cache_manager = GeminiCacheManager(client, model=config.model)

    # ... rest of generator logic with tqdm progress bars
```

## Prompts Design

### `prompts/control_reasons/system`

```
You are a Governance, Risk and Compliance (GRC) expert specializing in mapping security controls to policy documents.

Your task is to analyze a policy document and explain WHY a specific security control maps to this policy.

You must:
1. Identify specific text passages that relate to the control
2. Cite page numbers where evidence is found
3. Explain the compliance reasoning (why an auditor would expect this mapping)
4. Be specific and cite actual content from the document
```

### `prompts/control_reasons/user`

```
Analyze this policy document and explain why the following control maps to it.

**Control ID:** {CONTROL_ID}
**Control Name:** {CONTROL_NAME}
**Control Description:** {CONTROL_DESCRIPTION}

**Policy Name:** {POLICY_NAME}

Provide:
1. A list of specific reasons why this control maps to this policy
2. Page numbers where supporting evidence can be found
3. Direct quotes or paraphrases from the document that support each reason

If the control does NOT appear to map to this policy, explain why not.
```

### `prompts/control_reasons/response.json`

```json
{
  "type": "object",
  "properties": {
    "is_mapped": {
      "type": "boolean",
      "description": "Whether this control maps to this policy"
    },
    "reasons": {
      "type": "array",
      "description": "List of reasons (required when is_mapped=true, can be empty when false)",
      "items": {
        "type": "object",
        "properties": {
          "reason": {
            "type": "string",
            "description": "Explanation of why this control maps to the policy"
          },
          "page_numbers": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Page numbers where evidence is found (1-indexed)"
          },
          "evidence": {
            "type": "string",
            "description": "Direct quote from the document supporting this reason"
          }
        },
        "required": ["reason", "page_numbers", "evidence"]
      }
    },
    "unmapped_reason": {
      "type": "string",
      "description": "Required when is_mapped=false: explanation of why control doesn't map"
    }
  },
  "required": ["is_mapped"]
}
```

**Schema notes:**
- `reasons` is NOT required at top level (allows empty/missing when `is_mapped=false`)
- `unmapped_reason` should be present when `is_mapped=false` (enforced in code)
- `page_numbers` are 1-indexed (matching PDF page numbers)

## Output Format

**File**: `{output_dir}/{Policy_Name}_reasons.md`

```markdown
# Data Protection Policy

Control Mapping Reasons

## DCF-107: Data Classification

- **Policy defines data classification levels (Public, Internal, Confidential, Restricted) which aligns with control requirement for data categorization.**
  - Evidence: "All data must be classified according to sensitivity level..."
  - Pages: 1

- **Policy requires labeling of classified data, supporting control implementation.**
  - Evidence: "Classified information must be clearly marked..."
  - Pages: 2

---

## DCF-108: Data Handling Procedures

- **Policy specifies handling requirements for each classification level.**
  - Evidence: "Confidential data must be encrypted in transit and at rest..."
  - Pages: 3, 4

---

# Missed Controls (LLM False Negatives)

These ground truth controls were NOT verified by the LLM.

## DCF-999: Example Missed Control

**LLM's reason for not mapping:** The policy does not discuss this topic.

---
```

**Output characteristics:**
- Controls sorted by ID for stable, deterministic ordering
- Each reason has its own evidence and page citations (not collapsed)
- False negatives tracked in separate section at end

## Testing Strategy

1. **Unit tests**: Mock genai client, test each component in isolation
2. **Integration tests**: Test with real Gemini API (mark as integration, skip in CI)
3. **Single file testing**: `--policy "Asset Management" --control "DCF-4" -n 1`

## Dependencies

- `google-genai>=1.46.0` (already in `gcp` group)
- `typer` for CLI (already available)
- `tqdm` for progress bars (already available)
- Existing: `dcf_controls.py`, `eval_to_policy_mapping.json`

## Gemini Model Selection

**Context Caching Availability:**
Here are the Gemini models that can use Context Caching (i.e., they show “Caching: Supported” in Google’s Gemini models reference), with their model names + model IDs.  ￼

Model name	Model ID(s)
Gemini 3 Pro (Preview)	gemini-3-pro-preview  ￼
Gemini 3 Flash (Preview)	gemini-3-flash-preview  ￼
Gemini 2.5 Pro	gemini-2.5-pro  ￼
Gemini 2.5 Flash	gemini-2.5-flash  ￼
Gemini 2.5 Flash (Preview)	gemini-2.5-flash-preview-09-2025  ￼
Gemini 2.5 Flash Image	gemini-2.5-flash-image  ￼
Gemini 2.5 Flash-Lite	gemini-2.5-flash-lite  ￼
Gemini 2.5 Flash-Lite (Preview)	gemini-2.5-flash-lite-preview-09-2025  ￼
Gemini 2.0 Flash	gemini-2.0-flash (latest), gemini-2.0-flash-001 (stable), gemini-2.0-flash-exp (experimental)  ￼
Gemini 2.0 Flash Image (Preview)	gemini-2.0-flash-preview-image-generation  ￼
Gemini 2.0 Flash-Lite	gemini-2.0-flash-lite (latest), gemini-2.0-flash-lite-001 (stable)  ￼

Note: when creating an explicit cache, Google’s caching guide warns that for some models you must use an explicit version suffix (example given: use ...-flash-001, not just ...-flash).  ￼

**Recommended**: `gemini-3-flash-preview` for best reasoning capabilities with caching support. Override via `--model` CLI flag if needed.

## Usage Examples

```bash
# Test with single policy and single control (for initial testing)
uv run python -m ai_services.scripts.experiments.control_detection.control_mapping_reasons.run \
  --policy "Asset Management Policy" \
  --control "DCF-4" \
  -n 1 -c 1

# Process all controls for one policy (5 controls in parallel)
uv run python -m ai_services.scripts.experiments.control_detection.control_mapping_reasons.run \
  --policy "Data Protection Policy" \
  -n 1 -c 5

# Process all policies with parallelism=3 policies, 5 controls each
uv run python -m ai_services.scripts.experiments.control_detection.control_mapping_reasons.run \
  --all \
  -n 3 -c 5

# Clean up orphaned caches from interrupted runs
uv run python -m ai_services.scripts.experiments.control_detection.control_mapping_reasons.run \
  --cleanup

# Dry run - see what would be processed without running
uv run python -m ai_services.scripts.experiments.control_detection.control_mapping_reasons.run \
  --all \
  --dry-run

# Use a different model
uv run python -m ai_services.scripts.experiments.control_detection.control_mapping_reasons.run \
  --policy "Asset Management Policy" \
  --model gemini-1.5-pro-002 \
  -n 1 -c 1
```

**Parallelism Notes:**
- `-n` / `--parallelism`: Number of policies processed in parallel (default: 3)
- `-c` / `--control-parallelism`: Number of controls processed in parallel per policy (default: 5)
- Total concurrent LLM calls = `n * c` (e.g., 3 policies × 5 controls = 15 concurrent calls)

## Confirmed Decisions

1. **Unmapped controls (False Negatives)**: Track in separate "Missed Controls" section
   - These are ground truth controls that the LLM failed to verify
   - Log the LLM's `unmapped_reason` for debugging prompts/policies
2. **Error handling**:
   - Context cache creation failure → **Fail fast** (critical error)
   - LLM call failure → **Retry 3 times**, then skip and log
3. **Control parallelism**: Process controls in parallel within a policy
   - Configurable parallelism via `--control-parallelism` / `-c` flag
4. **Orphaned cache cleanup**: `--cleanup` flag to remove orphaned caches
   - Protects against quota exhaustion from interrupted runs
5. **Signal handling**: SIGINT/SIGTERM triggers cache cleanup before exit
6. **Raw JSON response persistence**: Save each LLM response to `{policy_dir}/responses/{DCF_ID}.json`
   - Enables debugging without re-running LLM calls
   - Preserves raw output before parsing
   - Filename includes DCF control ID for easy identification

---

## Revision History

### 2025-12-20: Incorporated Gemini 3 Analysis

Based on review in `gemini_3_analysis.md`, the following changes were made:

| Change | Rationale |
|--------|-----------|
| Model name `gemini-2.5-pro-preview-06-05` → `gemini-1.5-pro-002` | Original model name may not exist; 1.5 Pro is verified |
| Added `cleanup_orphaned_caches()` method | Protects against quota exhaustion (5-10 cache limit) |
| Added `--cleanup` CLI flag | Allows manual cleanup of orphaned caches |
| Added signal handlers (SIGINT/SIGTERM) | Ensures cache cleanup on Ctrl+C |
| Changed unmapped control handling | **Critical**: Log False Negatives instead of silently skipping |
| Added `append_missed_control()` and `finalize()` | Outputs "Missed Controls" section for debugging |
| Added `cache_prefix` to config | Enables targeted cleanup of our caches only |
| Added `tqdm` for progress bars | Better UX for long-running operations |
| Added `unmapped_reason` to `ControlReasons` | Captures why LLM didn't verify a ground truth control |

**Not incorporated:**
- Confidence score in response schema: Over-engineering for this experiment. The structured reasons with evidence provide sufficient signal.

### 2025-12-20: Incorporated ChatGPT o1 Pro Analysis

Based on review in `chatgpt_52_analysis.md`, the following changes were made:

| Change | Rationale |
|--------|-----------|
| Model name `gemini-1.5-pro-002` → `gemini-2.5-pro` | ChatGPT correctly identified official model name |
| Added jitter to exponential backoff | Prevents "thundering herd" synchronized retries |
| Per-reason page citations (not collapsed) | Preserves traceability; original writer collapsed pages |
| `asyncio.shield` for cache deletion | Protects finally block from cancellation |
| Sort controls by ID before writing | Ensures stable, deterministic output from parallel execution |
| Schema: `reasons` not required at top level | Models often omit fields when `is_mapped=false` |
| Added `--dry-run` flag | Preview what would be processed without running |
| Added `--model` flag | Override default model via CLI |
| Added `ReasonWithEvidence` dataclass | Each reason carries its own evidence and page citations |

**Not incorporated:**
- Evidence verification via PDF text extraction: Great idea but adds significant complexity. Noted for v2.
- 4 outcome buckets (verified/unverified/false-neg/error): Over-engineering for initial experiment. Keeping 3 buckets (mapped/false-neg/error).
- `--resume` flag: Adds complexity. Can rerun from scratch easily.
- `--output-json`: Markdown is sufficient for this experiment.

### 2025-12-20: Added Raw JSON Response Persistence

Per user request, added functionality to save raw LLM JSON responses to disk:

| Change | Rationale |
|--------|-----------|
| Added `JsonResponseWriter` class | Saves raw responses to `{policy_dir}/responses/{DCF_ID}.json` |
| Added TDD Cycle 4b for JSON writer | Tests for directory creation, file saving, response existence check |
| Updated `_generate_with_retry` to save JSON before parsing | Ensures raw output is preserved even if parsing fails |
| Added `_parse_response` helper method | Separates LLM call from response parsing for clarity |
| Added output structure documentation | Shows directory layout with responses/ subdirectory |

**Benefits:**
- Debug LLM responses without re-running expensive API calls
- Supports future resume functionality (check if response exists before calling LLM)
- Raw JSON preserved even if parsing logic changes

### 2025-12-20: Fixed Signal Handler Cache Registration Gap

Fixed bug where `_active_caches` list was defined but never populated, making signal handlers ineffective:

| Change | Rationale |
|--------|-----------|
| Added `_active_caches.append(cache_name)` after cache creation | Register cache for signal handler cleanup |
| Added `_active_caches.remove(cache_name)` in finally block | Unregister after successful deletion |

**Before:** Signal handler would iterate empty list, caches orphaned on Ctrl+C
**After:** Signal handler can clean up any caches that haven't been deleted by `finally` block

### Summary of All Reviews

| Reviewer | Model | Key Contributions |
|----------|-------|-------------------|
| Gemini 3 | gemini-2.0-flash | False negative tracking, orphaned cache cleanup, signal handlers |
| ChatGPT o1 Pro | o1-pro | Model naming, jitter, per-reason citations, asyncio.shield, sorting |
| User | - | Raw JSON response persistence with DCF ID in filename |
