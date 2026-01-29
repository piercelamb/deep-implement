Based on an analysis of the `false_negatives.json` file against your `system.md` prompt, the high false negative rate is primarily driven by **over-strict linguistic parsing** and **structural constraints** that do not align with how real-world corporate policies are written.

Here are the specific themes and prompt rules causing these failures:

### 1. The "Permissive Language" Hard Blocker (Phase 2.0 & Guardrails)
**The Issue:** The prompt explicitly instructs the LLM to treat words like "should," "may," "recommended," and "where possible" as hard blockers (Phase 2.0).
**Impact:** Many corporate policies use "should" or "should be" to denote requirements in a softer tone than "must/shall" (e.g., "Production data should not be used in testing"). The LLM is rejecting these entirely, even when the context implies a mandate.
*   **Specific Examples:** DCF-4, DCF-5, DCF-6, DCF-7, DCF-104, DCF-149, DCF-155, DCF-456, DCF-694, DCF-808.
*   **Reasoning Quote:** "The policy... uses permissive language ('should'), which is a hard blocker per Phase 2.0."

### 2. The Evidence Locality Rule (Phase 5)
**The Issue:** The prompt demands: *"Evidence must come from one contiguous location... Do not piece together content from different sections."*
**Impact:** Complex controls often require piecing together a "Scope" section (Section 1), a "Roles" section (Section 3), and a "Procedure" section (Section 5). The LLM is correctly following the prompt by rejecting these valid "synthesized" matches.
*   **Specific Examples:** DCF-15 (Risk Assessment), DCF-16 (Periodic Risk), DCF-375 (Badges), DCF-528 (Sensitive Info Management).
*   **Reasoning Quote:** "Violating the Evidence Locality Rule... information required... is distributed across non-contiguous sections."

### 3. Hyper-Specific Qualifier Rigidity (G-10 & G-14)
**The Issue:** Guardrail G-10 rejects matches if "hard qualifiers" (e.g., "annually," "external," "root," "CUI") are missing. Guardrail G-14 rejects "general" evidence for "specific" controls.
**Impact:** The LLM is rejecting broad policy statements that effectively cover the control because they lack the *exact* adjective or specific timeline mentioned in the control.
*   **Frequency Mismatches:** DCF-21, DCF-22, DCF-26, DCF-204, DCF-310 (Control says "Annually"; Policy says "Periodically" or "Regularly").
*   **Terminology Mismatches:**
    *   DCF-90: Control asks for "Root account"; Policy says "Administrative actions" (Rejected).
    *   DCF-19/465: Control asks for "External" pen test; Policy says "Pen test" (Rejected).
    *   DCF-788: Control asks for "CUI"; Policy says "Sensitive/PHI" (Rejected).
*   **Reasoning Quote:** "G-10: The policy fails to mandate the specific 'annual' frequency..."

### 4. Technical vs. Administrative Categorization (Phase 1.2 & G-1)
**The Issue:** The prompt forces a binary classification. If a control is typed as **TECHNICAL**, G-1 blocks it if the evidence describes a policy/process.
**Impact:** Policies mandate the *outcome* of technical controls (e.g., "Source code must be versioned"), but they rarely define the specific technical configuration (e.g., "Use Git"). The LLM rejects the mandate because it looks "Administrative" while the control is "Technical."
*   **Specific Examples:** DCF-4 (Version Control), DCF-79 (Logging System), DCF-590 (Info Sharing Tools), DCF-707 (Hard-coded creds), DCF-889 (Inventory Tool).
*   **Reasoning Quote:** "G-1: Control requires technical automated tools... policy describes administrative agreements."

### 5. Rejection of Placeholders and Templates (Phase 2.0)
**The Issue:** Phase 2.0 Admissibility Filter rejects "Examples/templates/placeholders ('<VALUE>')."
**Impact:** Many policies in the dataset appear to be drafts or templates where the header exists (mandating the activity), but the specific value is a placeholder. The LLM rejects the *existence* of the mandate because the *implementation detail* is a placeholder.
*   **Specific Examples:** DCF-15, DCF-42, DCF-77 ("<BACKUP FREQUENCY>"), DCF-162, DCF-212, DCF-660, DCF-807.
*   **Reasoning Quote:** "The artifact is incomplete as core components... are empty placeholders."

### 6. Document Type Mismatches (G-15)
**The Issue:** Phase 0 and G-15 require the document title to match the control's requested document type exactly.
**Impact:** The LLM rejects valid content because it is located in a consolidated policy document (e.g., finding "Information Security Policy" requirements inside a "Code of Conduct" or "Breach Notification" document).
*   **Specific Examples:** DCF-32, DCF-193, DCF-800.
*   **Reasoning Quote:** "G-15: Document is a Breach Notification Policy, not the requested Information Security Policy."

### Summary of Prompt Adjustments Needed

To fix these false negatives, you need to relax the "Strict Auditor" constraints:

1.  **Allow "Should":** Permit permissive language if the context implies a standard operating procedure.
2.  **Allow Synthesis:** Remove the "Evidence Locality" rule to allow combining Scope + Requirement from different sections.
3.  **Broaden Definitions:** Allow "Periodic" to map to "Annual" (or flag as Partial), and "Administrative" accounts to map to "Root".
4.  **Accept Outcomes:** Allow a policy mandate ("Must use version control") to satisfy a technical control ("Version control system") even if the specific tool isn't named.
5.  **Permit Placeholders:** Accept the *presence* of a section header as evidence of the requirement, even if the variable within is `<TBD>`.