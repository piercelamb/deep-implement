# Control Mapping Quick Reference

## The 5 Critical Questions

| # | Question | What to Look For |
|---|----------|------------------|
| 1 | **Same subject?** | Direct terminology or semantic equivalence |
| 2 | **Scope covers assets?** | Explicit applicability statement |
| 3 | **Binding language?** | "shall", "must", "required" (not "should", "may") |
| 4 | **Who owns it?** | Named role/team with accountability |
| 5 | **How is it done?** | Procedures, frequency, specs, artifacts |

---

## Evidence Types

| Type | Keywords/Signals |
|------|------------------|
| `explicit_mandate` | "shall", "must", "required to", "will ensure" |
| `scope_definition` | "applies to", "in scope", "applicable to all" |
| `responsibility_assignment` | "is responsible for", "owned by", "accountable" |
| `procedural_definition` | "steps include", "process for", "workflow" |
| `technical_specification` | config values, parameters, protocol names |
| `frequency_timing` | "annually", "quarterly", "within X days", "upon" |
| `artifact_reference` | "logs", "records", "reports", "evidence" |
| `standard_reference` | "ISO 27001", "NIST", "SOC 2", "GDPR" |
| `exception_handling` | "waiver", "exception", "deviation", "approval" |

---

## Insufficient Evidence (False Signals)

| Looks Like Evidence | Why It's Not Enough |
|---------------------|---------------------|
| "periodically review" | No specific frequency defined |
| "should encrypt" | Not mandatory ("should" vs "shall") |
| "staff are responsible" | No specific accountability |
| "maintain records" | No specification of what records |
| "follow industry standards" | No specific standard named |
| "as needed" | No defined trigger criteria |

---

## Confidence Levels

| Level | Criteria |
|-------|----------|
| **HIGH** | Direct match + scope + ownership + implementation detail |
| **MEDIUM** | Semantic equivalence OR minor gaps in detail |
| **LOW** | Tangential coverage OR major gaps |
| **NONE** | Wrong subject, excluded scope, or no binding language |

---

## Common Failure Modes

- **Scope gap**: Policy excludes required assets
- **Frequency gap**: Less frequent than control requires
- **Ownership gap**: No one accountable
- **Specificity gap**: Intent without procedures
- **Third-party gap**: Internal only, control needs vendor coverage
- **Evidence gap**: No artifact/record requirements

---

## Special Control Types

### Prohibition Controls
Must find: "must not", "prohibited", "forbidden"
NOT sufficient: "should avoid", "discouraged"

### External Standard Controls
Must find: Named standard citation (ISO XXXXX, NIST SP XXX-XX)
NOT sufficient: "industry standards", "best practices"

### Third-Party Controls
Must find: Explicit vendor/supplier scope extension
NOT sufficient: Internal-only policy

### Automation Controls
Must find: Mandatory automation requirement
NOT sufficient: Tools mentioned as "examples" or "options"
