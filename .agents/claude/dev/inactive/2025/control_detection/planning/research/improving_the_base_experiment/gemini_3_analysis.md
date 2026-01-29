This analysis suggests that while your retrieval foundation (ColModernVBERT) is solid, the **architectural pairing of the LLM to the data is the bottleneck**. The system is currently asking the LLM to perform a "needle in a haystack" task where the haystack is noisy (irrelevant page text) and the needles are too numerous (100 similar controls).

Here is a breakdown of strategic directions to improve the system, ranging from immediate optimizations to architectural pivots.

---

### Direction 1: The "Inverted Context" Pivot (Highest Potential)

**Concept:** Instead of iterating through *Pages* and asking "Which of these 100 controls fit here?", iterate through *Controls* and ask "Does this document satisfy this specific control?"

**Why it works:**
*   **Context Fragmentation:** Your current failure mode involves split context (definitions on pg 2, mandates on pg 10). The page-level approach misses this.
*   **Cognitive Load:** Asking an LLM to hold 100 complex control definitions in working memory and map them to a page is prone to hallucination. Asking it to check *one* control against a document is a focused, reasoning task.

**Implementation:**
1.  **Context Caching:** Upload the **entire Policy PDF** (text + images) to Gemini’s context cache.
2.  **Coarse Filtering (Optional but recommended):** Use your existing ColModernVBERT to filter the 779 controls down to the "Relevant 200" for the whole document (not per page).
3.  **Batch Inference:** Query the cached document with batches of controls (e.g., 5-10 at a time) or single controls.
    *   *Prompt:* "Does this policy document contain binding language ('must', 'shall') satisfying Control X? If yes, quote the text and cite the page number."

**Pros:** Solves cross-page context; reduces LLM confusion; leverages Gemini's long context window (up to 2M tokens).
**Cons:** Higher token usage (offset by caching pricing); higher latency if processed serially (can be parallelized).

---

### Direction 2: "Mandate-First" Pre-processing (Noise Reduction)

**Concept:** The experiment showed that non-binding language ("should", "may", boilerplate) causes false positives. Instead of asking the LLM to find controls in raw text, force it to extract **Mandates** first.

**Why it works:**
Policy documents are 80% fluff (headers, definitions, intros) and 20% rules. By extracting only the rules, you increase the signal-to-noise ratio significantly.

**Implementation:**
1.  **Step 1 (Extraction):** Run a fast LLM (Gemini Flash or a smaller model) over every page.
    *   *Prompt:* "Extract every sentence from this page that contains a binding mandate (must, shall, required, will ensure). Return a list of JSON objects: `{text: '...', page: 1}`. Ignore definitions."
2.  **Step 2 (Mapping):** Take the aggregated list of **only** binding statements (the "extracted policy") and run the mapping against the controls.
3.  **Step 3 (Grounding):** Map the matched mandate back to the original page image for final verification.

**Pros:** drastically reduces input tokens for the reasoning step; eliminates false positives caused by "aspirational" language.

---

### Direction 3: Agentic "Auditor" Workflow (High Accuracy)

**Concept:** Mimic a human auditor. Instead of a single pass, give an LLM agent "Tools" to investigate the document.

**Why it works:**
The current system forces a decision based on a static snapshot. An agent can "look harder" if it's unsure.

**Implementation:**
1.  **State:** The Agent holds the list of 779 controls.
2.  **Tools:**
    *   `keyword_search(query)`: Returns snippets + page numbers.
    *   `read_page(page_num)`: Returns full text + image description of a page.
    *   `get_candidate_controls(page_text)`: Calls your ColModernVBERT model to suggest relevant controls for a view.
3.  **Loop:**
    *   Agent picks a Domain (e.g., "Access Control").
    *   Agent searches for "password", "access review".
    *   Agent reads relevant pages.
    *   Agent marks controls as "Satisfied" with evidence or "Gap".

**Pros:** Highest potential accuracy; highly explainable chain-of-thought.
**Cons:** Slow; expensive; complex to orchestrate.

---

### Direction 4: Reranking with Cross-Encoders (The "Better Top-K" Fix)

**Concept:** If you want to keep the current Page-based architecture, you must fix the ranking. The ColBERT score (Late Interaction) is good for retrieval, but a **Cross-Encoder** is better for ranking.

**Why it works:**
ColBERT scores independently. A Cross-Encoder takes `(Control Text, Page Text)` as a single input and outputs a relevance score, allowing the model to see the *interaction* between specific words (e.g., "must" appearing near "password").

**Implementation:**
1.  **Retrieval:** Use ColModernVBERT to get Top-200 candidates (Threshold 0.44 to ensure 100% recall).
2.  **Rerank:** Pass the Page Text + Control Text pairs through a Cross-Encoder (e.g., a BGE-Reranker or a finetuned BERT) or a very cheap LLM prompt (zero-shot scoring).
3.  **Select:** Take the Top-20 from the Reranker.
4.  **Final Decision:** Send Page + Top-20 to Gemini.

**Pros:** Fixes the "Top-K" bottleneck without overwhelming the final LLM; drop-in replacement for current ranking logic.

---

### Direction 5: The "Negative Constraint" Prompting

**Concept:** Your LLM analysis shows precision is the issue (42%). The prompt currently encourages finding matches. You need to aggressively encourage *rejecting* matches.

**Immediate Optimization:**
Modify your prompt to include a specific "Rejection Step" before the selection step.

**New Prompt Structure:**
1.  **Analyze Page:** List all topics discussed.
2.  **Analyze Candidate:** For Control X:
    *   *Check 1:* Does the page mention the topic? (Yes/No)
    *   *Check 2:* Is there a "must/shall" verb attached to this topic? (Yes/No)
    *   *Check 3 (The Kicker):* **"Generate a counter-argument: Why might this control NOT be a match?"** (e.g., "It mentions passwords but only defines them, it doesn't set a length requirement.")
3.  **Final Verdict:** Only select if Check 2 is YES and Check 3 is weak.

---

### Recommended Experiment Plan

If I were running this, I would execute in this order:

1.  **The "Inverted Context" Pilot (Direction 1):**
    *   Take 5 documents.
    *   Cache the whole doc in Gemini 1.5 Pro (or Flash).
    *   Iterate through the 50 "hardest" controls.
    *   Compare F1 against the baseline.
    *   *Hypothesis:* This will drastically improve Recall and F1, as context is no longer fractured.

2.  **Mandate Extraction (Direction 2):**
    *   Run a script to strip all non-binding sentences from a policy.
    *   Read the output. Does it still make sense?
    *   If yes, feed *that* text into your current pipeline.
    *   *Hypothesis:* Precision will skyrocket.

3.  **Fixing the Ranking (Direction 4):**
    *   If you must stay page-based, implement a BGE-Reranker after ColBERT.
    *   Stop sending Top-100 to the LLM. Send a high-quality Top-15.