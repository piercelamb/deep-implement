Looking at all three prompts, I'll analyze what to keep and reject from each for the master synthesis.

  ---
  Analysis: Opus (Mine)

  KEEP:

  | Element                                                                                                | Reason                                                             |
  |--------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
  | 5-category blocking rule organization (Domain, Scope, Lifecycle, Evidence Quality, Semantic Precision) | Clear mental model, easier to navigate than flat list              |
  | "DO NOT Apply When" constraints on each IR                                                             | Critical innovation - makes IRs conditional, not automatic rescues |
  | Pre-Decision Checklist                                                                                 | Forces systematic verification before committing to a decision     |
  | Common Mapping Errors table                                                                            | Concrete examples are highly effective for LLM calibration         |
  | Structured output with tracking fields                                                                 | Enables post-hoc analysis and debugging                            |

  REJECT:

  | Element                                 | Reason                                                                                |
  |-----------------------------------------|---------------------------------------------------------------------------------------|
  | "Block first, search second" ordering   | Counter-intuitive; better to find evidence first, then validate it against guardrails |
  | 20 separate blocking rules              | Too granular; can consolidate without losing coverage                                 |
  | No Control Type classification          | Missing the single most important precision lever                                     |
  | No explicit confidence-to-decision rule | ChatGPT's "don't output MAPPED with low confidence" is cleaner                        |

  ---
  Analysis: Gemini

  KEEP:

  | Element                                      | Reason                                                                                                                       |
  |----------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
  | "Funnel" metaphor (wide mouth → narrow neck) | Excellent mental model: search broadly, filter rigorously                                                                    |
  | Golden Rule framing                          | "Don't penalize for missing how-to... DO penalize for admin substitute for technical" - captures the core tradeoff elegantly |
  | Trigger words list                           | review, monitor, audit, encourage, training - actionable red flags                                                           |
  | Quick Reference Check                        | 3 questions before MAPPED, 2 before NO_MATCH - simple and memorable                                                          |
  | Concise structure                            | ~150 lines vs. Opus's ~300 - less cognitive load                                                                             |

  REJECT:

  | Element                            | Reason                                                                                       |
  |------------------------------------|----------------------------------------------------------------------------------------------|
  | Only 4 filters                     | Too coarse; misses important edge cases (qualifier requirements, artifact vs activity, etc.) |
  | IRs in candidate search phase      | Creates confusion about when IRs apply; better to gate them explicitly after guardrails      |
  | No Control Type classification     | Same gap as Opus                                                                             |
  | No Mandatory Qualifiers extraction | Misses hard requirements like "FIPS validated", "authenticated", specific frequencies        |
  | No output tracking fields          | Harder to debug and iterate                                                                  |

  ---
  Analysis: ChatGPT

  KEEP:

  | Element                                                                                              | Reason                                                                                              |
  |------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------|
  | Control Type Classification (TECHNICAL/ADMINISTRATIVE/MONITORING/TRAINING/PHYSICAL/PRIVACY/ARTIFACT) | THE key precision lever - forces domain-match checking upfront                                      |
  | Evidence Admissibility Filter (upfront)                                                              | Clean separation: inadmissible evidence is rejected before any mapping logic                        |
  | Mandatory Qualifiers extraction (1.3)                                                                | Forces explicit handling of "FIPS", "authenticated", "privileged", frequencies, etc.                |
  | Qualifier Rule (PG-12)                                                                               | "If control has hard qualifiers, policy must have them too. Do not infer." - critical for precision |
  | Artifact Rule (PG-13)                                                                                | "Track/monitor ≠ inventory/plan" - addresses a major FP category                                    |
  | Confidence rule                                                                                      | "Do not output MAPPED with low confidence" - forces decisive calls                                  |
  | "One Quote → Many Controls" anti-pattern                                                             | Prevents generic sentences from matching dozens of controls                                         |
  | Edge-case guardrails                                                                                 | Exception governance, maintenance requirements, backup vs redundancy, etc.                          |
  | Explicit IR gating                                                                                   | "Only if: admissible evidence AND no guardrail violated" - crystal clear                            |

  REJECT:

  | Element                | Reason                                                            |
  |------------------------|-------------------------------------------------------------------|
  | 17 separate PG rules   | Too many; some overlap (PG-1/PG-10 both about admin vs technical) |
  | Flat guardrail list    | Harder to navigate than categorized organization                  |
  | Less structured output | Missing tracking fields for analysis                              |
  | Verbose explanations   | Some rules explained multiple times; can be tighter               |

  ---
  Master Prompt Architecture

  Based on this analysis, here's the structure I propose:

  1. ROLE & MAPPING STANDARD
     - From ChatGPT's 4-requirement framing
     - Add Golden Rule from Gemini

  2. PHASE 0: EXTRACT POLICY CONTEXT (Once per document)
     - From ChatGPT/Opus

  3. PHASE 1: BUILD CONTROL REQUIREMENT PROFILE (Per control)
     - 1.1 Core Objective
     - 1.2 Control Type Classification ← FROM CHATGPT (critical)
     - 1.3 Mandatory Qualifiers ← FROM CHATGPT (critical)
     - 1.4 AND/OR Logic

  4. PHASE 2: EVIDENCE RETRIEVAL
     - 2.0 Admissibility Filter (upfront) ← FROM CHATGPT
     - Pass A: Direct Binding Evidence
     - Pass B: Semantic Equivalence (same domain only)
     - Pass C: Pre-Rejection Search ← FROM GEMINI/OPUS

  5. PHASE 3: PRECISION GUARDRAILS (~12 consolidated rules)
     - Category A: Control Type Mismatch (3 rules)
     - Category B: Domain & Scope Boundaries (3 rules)
     - Category C: Lifecycle & Temporal (2 rules)
     - Category D: Qualifier & Artifact Requirements (2 rules) ← FROM CHATGPT
     - Category E: Evidence Quality (2 rules)
     - Edge Cases appendix ← FROM CHATGPT

  6. PHASE 4: INTERPRETIVE RULES (Gated)
     - Explicit gate: "Only if admissible evidence AND no guardrail violated"
     - ~8 IRs with "DO NOT Apply When" constraints ← FROM OPUS

  7. PHASE 5: DECISION LOGIC
     - MAPPED/PARTIAL/NO_MATCH criteria
     - Confidence rule ← FROM CHATGPT
     - One Quote → Many Controls warning ← FROM CHATGPT

  8. OUTPUT FORMAT
     - Core fields + guardrail_applied + ir_applied ← FROM OPUS (simplified)

  9. QUICK REFERENCE
     - 3 questions before MAPPED, 2 before NO_MATCH ← FROM GEMINI

  ---
  Key Innovations in Master Prompt

  1. Control Type as gatekeeper: Before searching for evidence, classify the control. If it's TECHNICAL, admin evidence is auto-rejected.
  2. Mandatory Qualifiers as hard requirements: Extract them upfront, check them explicitly. No inference allowed.
  3. Funnel flow: Search broadly → Filter through Admissibility → Validate against Guardrails → Apply IRs only if clean
  4. Consolidated guardrails: 12 core rules organized in 5 categories (vs. Opus's 20 or ChatGPT's 17)
  5. Explicit IR gating: IRs can only rescue if evidence passes all prior gates
  6. Confidence-to-decision rule: Low confidence = NO_MATCH (not MAPPED)

  ---
  Should I proceed with writing the master prompt?