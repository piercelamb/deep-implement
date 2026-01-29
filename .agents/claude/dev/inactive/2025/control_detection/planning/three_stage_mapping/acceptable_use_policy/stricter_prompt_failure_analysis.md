⏺ The problem is now clear. The model is applying the rules inconsistently:

  Ground Truth DCF-558 (should MAPPED) → REJECTED
  - Reason: "'types of software' is different from 'software programs'" (G-10/Rule 2)
  - Being pedantic about word choice

  False Positive DCF-822 (should NOT map) → MAPPED
  - Reason: "Acceptable Use Policy contains remote access sections, so it satisfies 'documented remote access management'"
  - But wait - this violates Rule 3! An AUP is not a "Remote Access Policy"

  Compare to DCF-106 (GT, should map) → REJECTED
  - Reason: "G-15: An AUP is not a 'Clear Desk Policy'"
  - Applied Rule 3 strictly here

  The model applied G-15 (artifact type) to reject DCF-106 but NOT to reject DCF-822. Both are sections within the AUP that the model should treat the same way.

  Summary

  | Control | Type | Should Be | Is       | Problem                            |
  |---------|------|-----------|----------|------------------------------------|
  | DCF-37  | GT   | MAPPED    | MAPPED   | ✓                                  |
  | DCF-106 | GT   | MAPPED    | NO_MATCH | Too strict on artifact type        |
  | DCF-558 | GT   | MAPPED    | NO_MATCH | Too strict on word choice          |
  | DCF-822 | FP   | NO_MATCH  | MAPPED   | Not strict enough on artifact type |

  The stricter prompt made the model more inconsistent, not less. It's now selectively applying rules.

  This might be a fundamental limitation - the model can't reliably distinguish when a section-within-a-policy is "enough" vs "not enough" to satisfy artifact controls.