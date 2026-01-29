# AI Services Monorepo

You are operating inside a monorepo that provides an API for all AI-based pipelines/processing for the Drata Governance Risk and Compliance (GRC) webapp. The API is a FastAPI wrapper that calls Temporal workflows to run pipelines. The repo contains many best practices around temporal/AI usage that you should research when implementing code.

## Global instructions

Your current context can always be found in @.agents/claude/dev/active. The parent directories there will contain subdirectories around planning, research, tasks, prompts, results etc. The current use case/feature we're working on will have a parent dir there you can use to find more information within.

If your current context has a `NOTES.md` file you need to update it like an append-only log with extremely concise short summaries of your decisions (they don't even need to be complete sentences). Append dated entries to the bottom as you make big decisions.

## Running code

Use uv run to run all python files.

## Code Style

- When creating a grouped set of constant strings, always create a StrEnum
- We define all types via StrEnum's and dataclasses
- Use `@dataclass(frozen=True, slots=True, kw_only=True)` for all dataclasses
- Ensure classmethods on dataclasses always return Self as their type
- Never use `init=False` in dataclasses
- Serialization/Deserialization methods (e.g., `to_dto()`) live on the dataclass
- The serialized version of a dataclass is a TypedDict with `DTO` appended to the name.
- Structured JSON logging via `ai_services.shared.logging.get_logger`
- Default to raising exceptions instead of swallowing and continuing. If I want you to catch and swallow, I will tell you.

## Testing

- uv run pytest to run all tests.
- you should run tests, mypy and ruff to check your work.
- Tests mirror source structure in `tests/`
- Set `TEMPORAL_DISABLE_RETRIES=1` for tests
- Use `WorkflowEnvironment.start_time_skipping()` for workflow tests
- Use `respx.mock` for HTTP mocking

## Service Documentation

- [ai_services/api/CLAUDE.md](ai_services/api/CLAUDE.md) - API endpoints, patterns
- [ai_services/temporal_workers/CLAUDE.md](ai_services/temporal_workers/CLAUDE.md) - Workflows, activities
- [ai_services/mcp_server/CLAUDE.md](ai_services/mcp_server/CLAUDE.md) - MCP protocol, tools
- [ai_services/vellum/CLAUDE.md](ai_services/vellum/CLAUDE.md) - Vellum workflow development
- [ai_services/shared/CLAUDE.md](ai_services/shared/CLAUDE.md) - Shared utilities