# Concern-Type Execution Ordering

Concern ordering reorders sections by concern type instead of manifest number order. This prevents the most common LLM failure: referencing types or interfaces that don't exist yet.

## Opt-In

Set `concern_ordering: true` in the `PROJECT_CONFIG` block of `index.md`:

```markdown
<!-- PROJECT_CONFIG
runtime: go
test_command: go test ./...
concern_ordering: true
END_PROJECT_CONFIG -->
```

When not set or set to `false`, sections execute in manifest number order (existing behavior).

## The 6 Concern Types

Executed in this order:

| Order | Concern | Purpose | Examples |
|-------|---------|---------|----------|
| 1 | `scaffold` | Directory structure, module init, stub routes, empty interfaces | `go mod init`, empty port interfaces, directory layout |
| 2 | `functional` | Core logic, ports, domain types, service implementations | Domain entities, service methods, handler routes |
| 3 | `observability` | Structured logging, metrics, tracing | OTel instrumentation, log middleware |
| 4 | `configuration` | Env vars, secrets, feature flags | Config loaders, validation |
| 5 | `resilience` | Error handling, graceful shutdown, health checks | Circuit breakers, retry logic, liveness probes |
| 6 | `integration` | Adapter wiring, cross-service calls, end-to-end tests | DI containers, integration tests |

## Tagging Sections

Add a concern tag after the section name in `SECTION_MANIFEST`:

```markdown
<!-- SECTION_MANIFEST
section-01-project-init scaffold
section-02-domain-models functional
section-03-api-handlers functional
section-04-logging observability
section-05-config configuration
section-06-error-handling resilience
section-07-external-apis integration
END_MANIFEST -->
```

- Sections with the same concern execute in manifest number order.
- Sections without a concern tag execute after all tagged sections.

## SECTION_META Block

Section files can include an optional metadata block for guardrail integration:

```markdown
<!-- SECTION_META
concern: scaffold
target_files: internal/ports/repository.go, internal/domain/entity.go
estimated_lines: 150
END_SECTION_META -->
```

Fields (all optional):
- `concern` — The concern type (redundant with manifest tag, useful as section-local context)
- `target_files` — Comma-separated list of files this section creates/modifies
- `estimated_lines` — Approximate total lines of code for guardrail calibration

## Fallback Behavior

- If `concern_ordering` is absent or `false` in PROJECT_CONFIG: manifest number order
- If `concern_ordering` is `true` but no sections have concern tags: manifest number order
- Mixed tagged/untagged: tagged sections first (in concern order), then untagged (in manifest order)
