⏺ Now I have a clear picture. Let me analyze the false positive patterns:

  Analysis: Why False Positives Remain High

  The Numbers

  - Ground Truth: 7 controls (DCF-106, DCF-32, DCF-37, DCF-50, DCF-558, DCF-763, DCF-780)
  - Predictions: 80 MAPPED + 18 PARTIAL = 98 total positive predictions
  - True Positives: 6 MAPPED + 1 PARTIAL = 7
  - False Positives: 74 MAPPED + 17 PARTIAL = 91 false positives

  Root Cause: The Interpretive Rules (IRs) Are Being Massively Over-Applied

  Breaking down the FP citations:

  | Rule                         | FP Count | Description                                               |
  |------------------------------|----------|-----------------------------------------------------------|
  | Direct                       | 30       | LLM claims "direct match" for tangentially related topics |
  | IR-3 (Semantic Equivalence)  | 24       | "Different words, same outcome" - far too permissive      |
  | IR-4 (Governance→Procedure)  | 16       | Being used to accept any governance language              |
  | IR-1 (Hierarchical Scope)    | 14       | Over-generalizing scope containment                       |
  | IR-2 (Parameter Abstraction) | 13       | Stripping away important qualifiers                       |
  | IR-6 (Inferred Existence)    | 10       | Inferring artifacts from mere references                  |

  Specific Failure Patterns

  1. "Direct match" is too loose:
  FP DCF-381 PHYSICAL  "The policy explicitly mandates that all sensitive materials must be secured"
  FP DCF-627 ADMIN     "The policy establishes specific rules of behavior prohibiting..."
  FP DCF-355 TECHNICAL "The policy explicitly mandates multi-factor authentication..."
  The policy has a sentence about MFA for remote access, so ANY MFA control gets mapped.

  2. IR-3 (Semantic Equivalence) is the biggest offender:
  FP DCF-94   "Clean Desk/Work Area" → mapped to "physical security requirements"
  FP DCF-748  "Isolate environments" → mapped to "network segmentation"
  FP DCF-713  "Lock computer workstations" → mapped to "console login screens"
  The LLM is finding surface-level semantic similarity and calling it "equivalence."

  3. IR-6 (Inferred Existence) is being abused:
  FP DCF-182  Reference to "Asset Management Policy" → maps to "documented asset management"
  FP DCF-181  Reference to external policy → maps to "policy artifact exists"
  Mentioning another policy ≠ satisfying the control that requires that policy.

  4. The prompt is recall-optimized but precision-hostile:

  Comparing experiments:
  | Experiment             | Recall | Precision | Notes                  |
  |------------------------|--------|-----------|------------------------|
  | Exp 4 (baseline)       | 86.1%  | 18.3%     | Original instructions  |
  | Exp 5 (FN-optimized)   | 94.0%  | 9.4%      | Added IRs for rescue   |
  | Current (FP-optimized) | 85.7%  | 7.5%      | Added guardrails + IRs |

  The guardrails aren't firing. The IRs provide escape hatches that let almost any mapping through.

  The Fundamental Problem

  The architecture is:
  1. Retrieve candidates via embeddings (100% recall at this stage)
  2. Ask LLM to confirm/reject each candidate

  The LLM is confirming too much. The IRs give it 10 different ways to say "yes" while the guardrails are not blocking enough.

  Recommendations

  1. Remove or drastically restrict IRs - They're creating more FPs than they rescue FNs
  2. Remove "medium confidence" for MAPPED - Only allow HIGH confidence mappings
  3. Add a batch-level sanity check - If >30% of a batch is MAPPED, something is wrong
  4. Consider document-type priors - An AUP realistically maps to 5-15 controls, not 80+
  5. Tighten "Direct match" - Require exact terminology, not just topic overlap