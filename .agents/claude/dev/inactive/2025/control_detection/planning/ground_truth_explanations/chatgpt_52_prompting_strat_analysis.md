You’re already doing a lot of the right things (forcing quotes + pages, separating specific vs generalizable, giving controlled labels, and allowing is_mapped=false). The main risk is that you’ll still get a ton of variance and “clever” rationales that make the map-reduce generalization step noisy.

Below are the highest-leverage improvements I’d make.

⸻

What’s working well
	•	Forcing evidence quotes + page numbers strongly reduces hallucination.
	•	The evidence_type / mapping_pattern taxonomy gives you structure for later clustering.
	•	The generalized_reason “abstraction rule” is exactly what you want for downstream pattern distillation.
	•	Allowing is_mapped=false prevents forcing a mapping.

⸻

Where this will break (and why)

1) “generalized_reason” variance will explode

Even with rules, models will produce many semantically-similar but syntactically-diverse rationales, which makes your pairwise generalization step harder.

Fix: constrain generalized reasons to templates or pattern IDs.

⸻

2) You’re missing a “strength” signal

Not all quotes are equal. Your reducer will treat weak implied scope language the same as a “must/shall” mandate.

Fix: add evidence_strength (high|medium|low) and optionally confidence (0–1). This is huge for ranking and later filtering.

⸻

3) Evidence dedupe + over-collection

Models tend to dump lots of overlapping quotes from the same paragraph. That inflates tokens and pollutes the “reasons.md”.

Fix: enforce:
	•	max reasons (e.g., 3–6),
	•	no overlapping quotes, and
	•	each reason must contribute a distinct evidence_type or mapping_pattern unless truly necessary.

⸻

4) Page-number reliability

Depending on your PDF extraction, “page numbers” can be inconsistent (headers vs PDF index). Models will guess if they can’t see clear page markers.

Fix options:
	•	Ensure the text in context includes explicit markers like === Page 4 ===.
	•	Add a rule: “If page is unknown, omit mapping (is_mapped=false) rather than guessing.” (or allow page_numbers: [] and mark strength low)

⸻

5) The abstraction guardrails are easy to violate

“Don’t mention domain terms” is hard to follow consistently and hard to validate later.

Fix: split the output into two fields:
	•	specific_rationale (can mention control topic; used for human debugging)
	•	generalized_reason (must be abstract; used for your distillation pipeline)

This dramatically reduces “model feels constrained so it gets vague” behavior.

⸻

Prompting strategy upgrades

A) Make it a 2-pass job (even in one call)

You can do this in a single model invocation by instructing an internal workflow:
	1.	Locate candidate excerpts relevant to the control
	2.	Select the top N non-overlapping excerpts
	3.	Label + justify each excerpt with evidence_type/mapping_pattern
	4.	Generate generalized_reason using a constrained template

This increases precision without requiring extra calls.

⸻

B) Use templated generalized reasons (reduces variance)

Instead of free-form generalized_reason, give ~10–20 approved templates keyed by (evidence_type, mapping_pattern) and require the model to pick one.

Example approach:
	•	Provide a list like:
	•	T1: “The policy contains explicit mandates using terminology that directly mirrors the requirement, indicating a direct mapping.”
	•	T2: “The policy defines a process that operationalizes the requirement, indicating alignment through implementation detail.”
	•	T3: “The policy assigns accountable ownership for the area covered by the requirement, indicating responsibility alignment.”
	•	etc.

Then output:
	•	generalized_reason_template_id: "T2"
	•	generalized_reason: <exact template text> (or template + 1 clause)

This makes your reducer’s job way easier.

⸻

C) Make “evidence selection rules” explicit

Add rules like:
	•	Prefer explicit_mandate over scope statements.
	•	Prefer language that includes who + what + must.
	•	Avoid aspirational words (“may”, “should”, “aim to”) unless nothing else exists.
	•	Quotes must be exact and ≤ 60 words (prevents dumping paragraphs).

⸻

D) Add a “coverage dimension” tag (optional but powerful)

Many controls map via different “dimensions” of policy language:
	•	governance/ownership
	•	process/lifecycle
	•	scope/applicability
	•	technical requirements
	•	exceptions

You already have most of this, but a single coverage_dimension enum can help clustering later.

⸻

Schema improvements I’d make

Add:
	•	evidence_strength: "high"|"medium"|"low"
	•	confidence: number 0–1
	•	specific_rationale: short, control-specific explanation (debugging)
	•	quote_location: { "page": 4, "snippet_start": "...", "snippet_end": "..." } (optional)
	•	generalized_reason_template_id: "T1"..."Tn" (if you adopt templates)

Also tighten conditional requirements:
	•	Require evidence_type_custom only if evidence_type == other
	•	Require mapping_pattern_custom only if mapping_pattern == other

(Your schema describes this, but many validators won’t enforce it unless you add JSON Schema if/then.)

⸻

A revised prompt (drop-in, still close to your current one)

System (key deltas):
	•	Add selection rules, max reasons, non-overlap, and template requirement.

You are a Governance, Risk and Compliance (GRC) expert specializing in mapping controls to policy documents.

Goal: Provide high-precision evidence that a control is addressed in a policy, and produce standardized generalized mapping patterns.

Process:
1) Identify candidate excerpts relevant to the control.
2) Select the STRONGEST 3–6 non-overlapping excerpts (prefer MUST/SHALL/WILL and clear responsibility/process language).
3) For each excerpt: label evidence_type + mapping_pattern, write a brief specific_rationale (may mention control topic), then write generalized_reason using one of the approved templates.

Evidence rules:
- Evidence must be an EXACT QUOTE from the document (<= 60 words).
- Provide accurate 1-indexed page numbers. If you cannot determine page numbers reliably, do not guess.
- Avoid redundant/overlapping quotes.

Generalized reason rules:
- generalized_reason MUST be abstract and MUST NOT mention control topic/domain terms/control ID.
- Use one of the provided generalized_reason templates (T1–Tn). Output template_id.

If you cannot find strong evidence with page numbers, set is_mapped=false and explain what you searched for.
Return JSON only that conforms to the schema.

User: keep as-is.

Response: add template_id, specific_rationale, evidence_strength, confidence.

⸻

Improvements to your overall pipeline (beyond the prompt)

1) Don’t rely on “full PDF in context” for retrieval quality

Even with context cache, models do better when you pass only the top relevant chunks plus a short “document map” (titles/headings → page ranges). If you can:
	•	pre-chunk the PDF,
	•	retrieve top-k chunks per control,
	•	then ask the model to justify with quotes from those chunks.

This increases quote accuracy and reduces missed evidence.

2) Your map-reduce step will work better with normalization

Before pairwise comparisons, normalize each reason into a canonical “signature”:

signature = evidence_type + "|" + mapping_pattern + "|" + generalized_reason_template_id

Then your reducer mostly merges templates + examples, instead of trying to reconcile free-form prose.

3) Build a “golden lint” validator

After generation, automatically reject outputs that:
	•	include banned domain terms in generalized_reason,
	•	have quotes > 60 words,
	•	missing/empty page_numbers,
	•	duplicate evidence strings,
	•	or too many other.

This keeps your reasons.md clean for the distillation step.

⸻

If you only do 3 things, do these
	1.	Template-ize generalized_reason (template IDs)
	2.	Add evidence_strength + confidence and cap to 3–6 non-overlapping quotes
	3.	Add specific_rationale (control-topic allowed) separate from generalized_reason

That combination will reduce noise, improve clustering, and make your final “teaching instructions” far more stable.

If you want, paste one real generated output (a reasons.json) and I’ll show exactly how I’d rewrite it to be more reducer-friendly.