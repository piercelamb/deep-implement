# Go Guardrails

File size and architecture constraints for Go hex-architecture projects. Read this before writing any code.

## File Size Limits

| File type | Path pattern | Max lines |
|-----------|-------------|-----------|
| Port interfaces | `internal/ports/*.go` | 100 |
| Domain entities | `internal/domain/*.go` | 250 |
| Handler files | `internal/handler/**/*.go` | 250 |
| Service files | `internal/service/*.go` | 300 |
| Adapter files | `internal/adapter/**/*.go` | 300 |
| Test files | `*_test.go` | 500 |
| Other `.go` files | (default) | 300 |

## Function Length Limits

| Context | Max lines |
|---------|-----------|
| Non-test functions | 75 |
| Test functions | 150 |

## Hex Architecture Import Rules

Inner layers must NOT import outer layers:

```
domain (0) → ports (1) → service (2) → handler (3) → adapter (4)
```

- `domain` may import: stdlib, contracts, pkg
- `ports` may import: domain, stdlib, contracts, pkg
- `service` may import: ports, domain, stdlib, contracts, pkg
- `handler` may import: service, ports, domain, stdlib, contracts, pkg
- `adapter` may import: everything above

Cross-service `internal/` imports are prohibited. Use `contracts/` or `pkg/` instead.

## Prohibited Patterns

- Hardcoded secrets (`password := "..."`, `apiKey := "..."`)
- `os.Exit()` outside `cmd/` packages
- `panic()` in non-test code (use error returns)

## File Splitting Strategy

When approaching limits:

1. **One entity per file** — `blueprint.go`, `project.go`, not `entities.go`
2. **Extract helpers** — move shared logic to `internal/domain/` or `pkg/`
3. **Split adapters by operation** — `repo_read.go`, `repo_write.go`
4. **Extract validation** — `validate.go` for complex validation logic
5. **Table-driven tests** — keep test cases as data, loop body small
