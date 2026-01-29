This is a classic Information Retrieval (IR) problem: **The semantic space of the query (technical control) does not overlap with the semantic space of the document (policy procedural text), yet they are logically linked.**

Since you want to avoid OCR/layout extraction and utilize your specific toolbox (ColModernVBERT, fast VLMs, smart LLMs), here are four distinct approaches to solving the recall/precision trade-off.

---

### Solution 1: "Hypothetical Policy Generation" (HyPo)
**Technique:** Query Expansion / Index Augmentation
**Tool:** Large LLM (Offline) + ColModernVBERT

The fundamental issue is that ColModernVBERT is trying to match a technical description (e.g., "Internet Explorer 11 Disabled") against a procedural document (e.g., "All changes must go through the Change Advisory Board"). These will never match semantically.

Instead of matching the **Control Description**, match the **Hypothetical Policy Text**.

1.  **Offline Step:** Use a smart LLM (Sonnet/Gemini) to process all 779 controls.
    *   *Prompt:* "Given this security control description, write a paragraph of *policy text* that would appear in a corporate policy document to satisfy this control. Do not describe the technical settings; describe the *governance requirement*."
    *   *Example Output for DCF-988 (IE 11 Disabled):* "The organization shall maintain standard configuration baselines for all workstations. Derivations from the baseline must be approved via the Change Management process."
2.  **Indexing:** Embed these "Hypothetical Policy Paragraphs" using ColModernVBERT alongside (or instead of) the original descriptions.
3.  **Retrieval:** When the Change Management Policy page comes in, it will semantically match the "Hypothetical Policy Paragraph" much better than the raw control text.

**Why this works:** It shifts the query into the same semantic modality as the target image.

---

### Solution 2: Visual Listwise Reranking (The "Flash Filter")
**Technique:** Two-Stage Retrieval
**Tool:** Flash 2.5 / Haiku (Fast VLM)

If you must keep the ColModernVBERT threshold low (0.20) to ensure recall, you effectively have a "Candidate Generation" stage that returns ~600 garbage results and ~20 real results. Standard LLMs are too expensive to filter this one-by-one.

However, **Gemini Flash 2.5** and **Haiku** have massive context windows and low costs.

1.  **Stage 1 (VBERT):** Keep the threshold at 0.20. Get the massive list of 500+ control **Titles** (not full descriptions, to save tokens).
2.  **Stage 2 (VLM Rerank):**
    *   **Input:** The Page Image + A JSON list of 500 candidate Control Names.
    *   **Prompt:** "You are an auditor. Look at this policy page. Review the list of 500 control titles below. Return a JSON list of the IDs of the top 50 controls that are potentially relevant to the content on this page. Be generous with relevance."
3.  **Stage 3 (Smart LLM):** Send the filtered 50 full descriptions + Page Image to the expensive LLM for the final decision.

**Why this works:** VLMs are excellent at scanning an image and skimming a text list simultaneously. It treats the candidate list as a menu. This avoids running 500 separate inference calls.

---

### Solution 3: The "Anchor & Drag" Strategy (Graph-Based)
**Technique:** Co-occurrence Expansion
**Tool:** Python / NetworkX (No AI required for runtime)

Your analysis showed that semantic retrieval finds "Anchor" controls (e.g., "Change Control Procedures") with high scores (>0.35), but misses "Compliance" controls (e.g., "PowerShell Settings") which score low (0.20).

However, **Anchors and Compliance controls appear together in the ground truth.**

1.  **Offline Step:** Build a **Control Co-occurrence Graph** based on the Drata templates or your ground truth `_Controls` column. If Control A and Control B frequently apply to the same policy document, create an edge between them.
2.  **Runtime:**
    *   Set ColModernVBERT threshold high (e.g., 0.35). This ensures high precision but low recall.
    *   Identify the "Anchor" controls retrieved.
    *   **The "Drag":** Automatically pull in the "neighbors" of the Anchors from your graph.
    *   *Example:* VBERT finds "Change Management Policy" (Score 0.40). The graph knows "Change Management Policy" is linked to "PowerShell Settings". Pull "PowerShell Settings" into the candidate set, even if its VBERT score was 0.15.

**Why this works:** It uses the strong semantic signal to bootstrap the weak compliance signal without flooding the LLM with unrelated garbage.

---

### Solution 4: Domain-First Hierarchical Retrieval
**Technique:** Coarse-to-Fine Search
**Tool:** ColModernVBERT

Your analysis noted that specific outliers (Change Management Policy) fail because entire domains (Configuration Management) are missing. Instead of retrieving distinct controls, retrieve the **Domain** first.

1.  **Embed Domains:** Create embeddings for the 20-30 DCF Domain names/definitions (e.g., "Access Control", "Risk Management", "Configuration Management").
2.  **Step 1:** Run ColModernVBERT between the Page Image and the *Domain Embeddings*.
3.  **Step 2:**
    *   If a Domain scores high (e.g., "This page is about Change Management"), automatically include **ALL** controls in that domain as candidates.
    *   *Optimization:* Combine this with the low-threshold search.
    *   `Candidates = (Specific Controls > 0.30) UNION (All Controls in Domains > 0.25)`

**Why this works:** It is much easier for VBERT to recognize that a page belongs to the "Configuration Management" *domain* than to match a specific "PowerShell" control. This guarantees the relevant bucket of controls is passed to the LLM.

### Recommendation

**I recommend implementing Solution 1 (Hypothetical Policy Generation) immediately.**

*   **Low Friction:** It only changes the text strings you embed. You don't need to change your runtime architecture, `predictor.py`, or add new API calls.
*   **Fixes the Root Cause:** It forces the embedding space to align.
*   **Cost:** One-time cost to generate synthetic descriptions for 779 controls.

If Solution 1 doesn't yield 100% recall at a reasonable threshold, layer **Solution 3 (Anchor & Drag)** on top of it to capture the hidden compliance logic.