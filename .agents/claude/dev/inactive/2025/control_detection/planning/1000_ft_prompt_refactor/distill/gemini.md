This is a classic prompt engineering challenge: the "Wall of Text" problem. The current prompt is effectively a comprehensive training manual for a human junior auditor. While legally precise, it creates **cognitive interference** for an LLM. The model is likely to forget early instructions (the "Golden Rule") by the time it reaches the JSON schema, or hallucinate mappings because it’s trying to balance 17 different negative constraints simultaneously.

To distill this while maximizing precision (avoiding false positives) and recall (catching valid mappings), we need to shift from **"Teaching the reasoning"** to **"Enforcing the rules."**

Here is the plan to distill the prompt.

### 1. The Strategy: "Rules over Education"

We will remove all "educational" text (why this matters, definitions of GRC, motivational speeches) and "procedural" text (how to read the document step-by-step). We will retain only the **definitions**, **constraints**, and **output schema**.

**The Guiding Principle:** The LLM does not need to know *why* a policy is not a procedure; it just needs a rule that says `IF text describes "how-to" steps THEN reject`.

### 2. Specific Sections to Cut or Compress

| Section | Action | Reasoning |
| :--- | :--- | :--- |
| **Part 1: Foundations** | **Compress** | Reduce to a single "Persona" block. Remove "Key Concepts" and "Why does this matter?" definitions. Keep the "Golden Rule" but rephrase it as a system constraint. |
| **Part 2: Inputs** | **Remove** | The LLM does not need to be told to "read the document." We can rely on its native ability to parse text. We will simply instruct it to Identify *Document Type* and *Control Type* implicitly. |
| **Part 3: Evidence** | **Merge** | Remove the "Pass A/B/C" search procedure. Instead, define a strict **"Admissibility Filter"** list (Allowed vs. Banned words). |
| **Part 4: Validation** | **Restructure** | This is the bloated section. We will convert the 17 Guardrails and 8 IRs into a **Lookup Table** or **Checklist**. We will strip the examples and "Why" text, leaving only the logic trigger. |
| **Part 5: Decision** | **Merge** | Merge this into the "Output Format" section. The criteria for `MAPPED`, `PARTIAL`, and `NO_MATCH` should be the definitions of the output keys. |
| **Part 5.4: Anti-Patterns** | **Remove** | These are redundant if the Guardrails are enforced correctly. |

### 3. The New Structure (Proposed)

We will reorganize the prompt into four tight sections:

1.  **Role & Constraints (The Prime Directive):** The skepticism setting and the definition of "Binding Language" (Must/Shall).
2.  **The Admissibility Logic:** A blacklist of words (should, recommended, may) and a whitelist of types.
3.  **The Logic Core (Guardrails & IRs):** A condensed table. We must keep the IDs (G-1, IR-1) because the output schema requires them, but we will reduce their text descriptions to <15 words each.
4.  **Schema & Evaluation:** The JSON structure and the definition of the decision values.

### 4. Detailed Distillation Tactics

#### Tactic A: Condensing Guardrails (The "Rule Compression")
Current Guardrails are verbose. We will compress them into logical groupings.

*   *Current G-1:* "Control is TECHNICAL but evidence describes administrative review, manual process, policy statement..."
*   *Distilled G-1:* "Type Mismatch: Control is TECHNICAL/AUTOMATED, but evidence is MANUAL/ADMIN/POLICY."

*   *Current G-5:* "Evidence domain (physical/logical/data) doesn't match control domain..."
*   *Distilled G-5:* "Domain Mismatch: Evidence targets wrong layer (Physical vs Logical vs Data)."

#### Tactic B: Eliminating "Soft" Logic
The current prompt tries to teach nuance regarding the word "should."
*   *Current:* "Check if the CORE OBJECTIVE has binding language elsewhere..."
*   *Distilled:* "Reject 'should', 'recommended', 'may' unless explicitly overridden by a 'must' in the immediate same clause."

#### Tactic C: Redefining PARTIAL
The prompt spends too long explaining PARTIAL.
*   *Distilled:* "Use PARTIAL **only** for: Scope Gaps (Internal vs External), Third-Party Gaps, or Contradictions. Missing details = MAPPED. Missing mandates = NO_MATCH."

### 5. The "Cheatsheet" Prototype

Below is how the core logic section should look in the distilled prompt. This replaces about 3 pages of the original text.

> **VALIDATION LOGIC (GUARDRAILS)**
> *If any Guardrail applies, Decision is NO_MATCH. Cite the ID.*
>
> *   **G-1 (Type):** Control is Technical/Automated; Evidence is Admin/Manual/Policy.
> *   **G-2 (Enforcement):** Control requires System Enforcement; Evidence relies on User Behavior/Rules.
> *   **G-3 (Outcome):** Control requires Prevention; Evidence provides Detection/Logging only.
> *   **G-4 (Program):** Control requires Program/Plan; Evidence is only a component/input (e.g., Reporting).
> *   **G-5 to G-10 (Scope):** Wrong Domain (Phy/Log), Explicit Exclusion ("Not applied to X"), Wrong Entity (Vendor vs Internal), Wrong Artifact.
> *   **G-11/12 (Timing):** Lifecycle Mismatch (Prov vs Term) or Frequency Mismatch (Event-driven vs Periodic).
> *   **G-13 (Qualifiers):** Missing Primary Qualifier (FIPS, "Immutable", "Third-party").
> *   **G-16/17 (Weakness):** Reference only (ISO citations) or Risk Assessment only (identifying risk vs fixing it).
>
> **INTERPRETIVE RULES (BRIDGES)**
> *Use ONLY if no Guardrail applies. Cite the ID.*
>
> *   **IR-1 (Scope):** Policy says "All"; Control target is a subset. (Valid)
> *   **IR-2 (Params):** Policy requires "Strong/Secure"; Control asks for specific algo (AES-256). (Valid)
> *   **IR-3 (Freq):** Policy mandates continuous/regular; Control asks for specific interval. (Valid)
> *   **IR-5 (Header):** Binding header ("Requirements:") applies to bulleted list. (Valid)

### 6. Implementation Plan

To execute this, I will rewrite the system prompt to be **data-centric**.

1.  **Define the Input:** Policy Text + Control Text.
2.  **Define the Process:** Filter -> Match -> Validate.
3.  **Define the Output:** JSON.

**Goal Metric:** Reduce token count by ~60% while retaining 100% of the G-X and IR-X logic references required for the JSON output.

Shall I proceed with generating the distilled system prompt based on this plan?