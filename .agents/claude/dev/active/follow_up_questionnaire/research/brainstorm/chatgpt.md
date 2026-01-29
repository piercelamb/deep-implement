Here’s how I’d think about it, starting from the product team’s “store follow-up data into the same assessment namespace and give it precedence” expectation, and then stress-testing it against the two rerun modes.

First principles: what does “precedence” mean?

Before mechanics, define precedence behaviorally:
	•	Hard precedence (override): if follow-up data is relevant to a criterion, it should always be included and should outweigh older evidence from docs.
	•	Soft precedence (boost): follow-up data should be more likely to appear, but not guaranteed.
	•	Scope precedence: follow-up answers should be preferred for the specific criteria they pertain to, not globally.

Most product expectations I’ve seen implicitly want hard + scoped precedence: “If the vendor answered this, use it first for this.”

Once you want “hard,” pure top_k semantic retrieval is usually not enough unless you add structure.

⸻

Case 1: user does NOT modify follow-up questionnaire (rerun only those criteria)

“The assessment step will get exactly the same criterion to vector search against that it did the first time… follow-up questionnaire data tied directly to these questions, so they should be the top result. Do you agree?”

Mostly yes, but I wouldn’t rely on ‘should be top’ as a guarantee if you’re only doing vanilla vector similarity search.

Why it often works:
	•	Same criterion text → query embedding stays consistent.
	•	If you store follow-up Q/A as chunks that include the criterion text (or very close paraphrase), it’ll likely match strongly.

Why it can still fail:
	•	The follow-up answer might be short/ambiguous (“Yes, we do this annually”) and embed poorly vs a long SOC2 excerpt with many overlapping terms.
	•	If you chunk documents aggressively, a big chunk with lots of keyword overlap can dominate similarity even if the follow-up is the “right” evidence.
	•	If you have any reranker / MMR / diversity logic, it can demote duplicates or short snippets.

Recommendation for this case: make precedence deterministic, not probabilistic.
	•	Store follow-up responses with metadata keyed to the criterion_id (or a stable criterion hash).
	•	Retrieval path for rerun:
	1.	Fetch follow-up evidence by criterion_id (exact match) → always include it
	2.	Then do vector search against the rest of the namespace for additional context
	•	Even if you also vector-store the follow-up answer, don’t depend on it being top_k.

This gives you “follow-up always included” without sacrificing semantic search on the rest.

⸻

Case 2: user DOES modify follow-up questionnaire (rerun ALL criteria)

This is the tricky one you called out: the modified follow-up questions may diverge semantically from the original criteria being rerun, so the follow-up answers might not appear in top_k when querying with original criteria text.

That’s a real failure mode, and it gets worse the more “editorial” the user gets (e.g., turning a criterion into a narrower or broader question, or changing terminology).

Options to solve this (in increasing “structure”)

Below are a few patterns; you can mix them.

⸻

Option A: Don’t make precedence depend on similarity at all (recommended)

Treat follow-up responses as first-class evidence linked to criteria, not just another document in the vector pile.

Mechanism
	•	When the follow-up questionnaire is created, each question should retain a link to:
	•	the original criterion_id(s) it came from (even if the user edits the text), and/or
	•	an internal “followup_item_id → criterion_id(s)” mapping.
	•	When vendor submits, store answers with that mapping.
	•	During rerun for any criterion:
	•	Always attach any follow-up answers mapped to that criterion_id
	•	Then do normal vector retrieval across policies/SOC2/etc

Why this works well
	•	You get deterministic precedence (always included).
	•	You’re robust to semantic drift from edits.
	•	You preserve provenance (this came from the vendor, date X, question text Y, edited by user Z).

Key requirement
	•	Your editing UI must preserve that mapping rather than “breaking” the link when text changes.

Even if product wants the follow-up stored in the vector DB “namespace,” you can still do that—just don’t make retrieval solely vector-based.

⸻

Option B: Store follow-up answers in a way that still matches the original criteria

If you must rely on vector similarity more heavily, then store follow-up entries as embeddings that include the original criterion text.

For each follow-up item, store a “retrieval blob” like:
	•	criterion_question_text + "\nUser follow-up question: ...\nVendor answer: ..."

…and tag it with metadata like source=followup, criterion_id=....

Then, even if the user edited the follow-up question, the stored embedding still contains the original criterion language, so querying by original criterion still hits it.

This is basically “index-time query expansion” using the stable criterion text.

Tradeoff
	•	You’re kind of “cheating” the embedding by injecting the criterion text, but that’s good here: you want guaranteed recall for the criterion.

⸻

Option C: Two-pass retrieval (follow-up-first rerank)

If you want to keep things “vector-native,” you can do a two-pass scheme:
	1.	Query vector DB with criterion → get top_k candidates from all sources
	2.	Separately query (or filter) for follow-up entries (by metadata or smaller index)
	3.	Merge results with a rule: follow-up evidence is always inserted at the top (or always included)
	4.	Optionally rerank everything with a cross-encoder / LLM judge that knows follow-up is higher priority

This is essentially “hard inclusion + rerank,” but still uses semantic search.

⸻

Option D: Reserve slots in top_k for follow-up evidence

If you’re concerned about flooding the model context, you can do:
	•	Always include up to N follow-up items (by criterion mapping or by follow-up similarity),
	•	Then fill remaining top_k - N with SOC2/policies evidence.

This gives consistent behavior and prevents follow-up answers from being drowned out.

⸻

What I’d avoid
	•	Relying on vector “precedence” alone (e.g., “it’ll just come back top_k”). It won’t be reliable across content lengths, chunking strategies, or embedding quirks.
	•	Global precedence (“follow-up outweighs everything”). Follow-up is high-value, but only for the criteria it addresses. Otherwise you can accidentally use a vendor’s answer to one question as evidence for another.

⸻

A pragmatic design I’d push for

Data model
	•	criterion: id, canonical text, derived metadata (control/domain)
	•	followup_item: id, vendor_id, assessment_id, linked_criterion_ids[], question_text_current, question_text_original, edited_flag, timestamps
	•	followup_response: followup_item_id, answer, attachments, timestamps, author

Indexing

Store follow-up entries in vector DB, but with explicit criterion linkage:
	•	Metadata: source=followup, assessment_id, vendor_id, linked_criterion_ids
	•	Content: include both criterion canonical text and current follow-up Q + answer (Option B)

Retrieval during assessment for each criterion
	1.	Pull follow-up evidence by linked_criterion_ids contains criterion_id (exact filter) → always include
	2.	Vector search across base docs (policies/SOC2) using criterion text
	3.	Merge with rule: follow-up evidence placed first + marked as higher priority
	4.	Assessment LLM prompt explicitly says: “Vendor-provided follow-up responses are newer; if conflicting, explain and prefer follow-up unless it’s non-responsive.”

That gives product their “it lives in the vendor assessment namespace” story, and gives you deterministic precedence.

⸻

Extra: handling conflicts + trust

If you elevate follow-up answers, you’ll eventually hit:
	•	vendor answer contradicts SOC2/policy
	•	vendor answer is vague / nonresponsive

So your assess step should treat follow-up as high priority but not unquestionable:
	•	Prefer follow-up if it directly answers the criterion with specifics
	•	If conflict, mark INCONCLUSIVE (or “MET with exception” if you have that) and surface discrepancy to the user

Also: keep provenance surfaced in UI (source + date + who answered).

⸻

Direct answers to your two questions
	•	Non-modified case: yes, it’s conceptually straightforward, but I’d still implement hard inclusion via criterion_id linkage rather than trusting top_k ranking.
	•	Modified case: you need a mechanism that doesn’t depend on semantic similarity between original criterion text and modified follow-up question. Best fix is to preserve mapping and fetch follow-up evidence by ID/metadata, or to embed follow-up content together with the original criterion text so it remains retrievable.

⸻

If you want, I can sketch a concrete retrieval contract for the “assess criteria” step (inputs/outputs) that makes this precedence behavior explicit and testable (including a couple adversarial cases like “edited question uses different terminology” and “vendor answer is extremely short”).