Excellent analysis. Here's the summary:

  Stage 3 Verification Failure Analysis

  The Numbers

  | Metric           | Value                 |
  |------------------|-----------------------|
  | Stage 2 MAPPED   | 61                    |
  | Stage 3 verified | 29                    |
  | True Positives   | 6                     |
  | False Positives  | 23 (79% of verified!) |
  | False Negatives  | 1 (DCF-32)            |

  Root Causes

  1. Inference Rule Overreach (IR-1, IR-8)
  Stage 3 uses inference rules too liberally to justify mappings:
  - "Managing according to classification" → infers classification itself (IR-8)
  - "Endpoint systems" → accepted for "all system components" (IR-1)
  - "Policy violations" → interpreted as "security risks" (IR-1)

  2. Inconsistent Guardrail Application
  - G-14 (Scope Boundary): Enforced for DCF-9, DCF-326; ignored for DCF-291, DCF-580, DCF-822
  - G-15 (Artifact Type): Enforced for DCF-123; ignored for DCF-180, DCF-822
  - G-1 (Admin vs Technical): Should have blocked DCF-108 but didn't

  3. ARTIFACT vs MANDATE Confusion
  Stage 3 accepts sections within the AUP as satisfying controls that require dedicated policy documents:
  - DCF-822: AUP's "Remote Access Tools" section accepted as "Remote Access Management documentation"
  - DCF-180: AUP's procedures section accepted as "Secure Information Transfer Policies"

  4. Component → System Leap
  Stage 3 accepts individual mandates as evidence of systemic programs:
  - "Lock workstations" → accepted for "secure storage mechanisms" (DCF-108)
  - "Access discontinued upon disciplinary action" → accepted for "process for disabling high-risk accounts" (DCF-580)

  What Stage 3 Got Right (Correctly Rejected)

  - DCF-123: Rejected via G-15 (AUP section ≠ Disposal Procedure)
  - DCF-655: Rejected via G-15, G-17 (behavioral rule ≠ tamper protection procedure)
  - DCF-516: Rejected via G-4, G-10 (malware training ≠ IR training)

  The Core Problem

  Stage 3 is supposed to be adversarial ("try to REJECT this mapping") but it's actually finding reasons to VERIFY. The model applies inference rules to bridge gaps instead of treating gaps as reasons to reject.

  Potential Fixes

  1. Tighten the verification prompt - Explicitly prohibit inference rules in Stage 3 (they're for Stage 2 only)
  2. Add explicit guardrail checklist - Force Stage 3 to evaluate each applicable guardrail
  3. Stricter artifact type matching - If control requires "X Policy", only accept a document titled "X Policy"
  4. Ban scope expansion - If evidence covers "endpoints" and control requires "all systems", that's NO_MATCH

  Want me to update the Stage 3 verification prompt to be stricter?