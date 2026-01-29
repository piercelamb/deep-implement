Here are the main themes / “rules” that repeatedly drive NO_MATCH (false negatives) in this batch, based on the model’s own rules_cited + reasoning patterns in the FN JSON.

⸻

1) Evidence Locality Rule is nuking valid matches when evidence is split across sections

The model is rejecting cases where the control’s required elements are present but not in one contiguous passage.
	•	It explicitly calls out that required info is “distributed across non-contiguous sections,” and rejects on locality even when the doc likely covers the full story collectively.  ￼
	•	Same pattern: “evidence is fragmented across non-contiguous sections” → NO_MATCH.  ￼

Why this causes FNs: a lot of real policies split “definition / process / review cadence / reporting” across headings. If locality is enforced as single-snippet sufficiency, you’ll get systematic under-mapping.

⸻

2) Hard-qualifier strictness (G-10 / G-16) is acting like “exact-match or nothing”

Many NO_MATCH outcomes are: “the policy is close, but missing one non-negotiable qualifier.” Common missing qualifiers include:
	•	External / independent / third party: policy allows internal testers vs control mandates independent third party; plus “external” qualifier missing.  ￼
	•	Frequency requirements (annual / daily / weekly / “after significant change”): e.g., control requires annual inspections but policy omits review cadence.  ￼
	•	Specific sub-requirements inside a broader category: “policy mandates automated review mechanisms” but doesn’t literally include “audit record reduction” / “correlated review.”  ￼
	•	Vendor change qualifiers: mentions managing changes, but missing “management authorization” + “retain documentation.”  ￼

Why this causes FNs: your decision logic is effectively treating many qualifiers as binary must-haves. That’s fine for precision, but it will over-produce NO_MATCH where a human would say “Partial (missing X).”

⸻

3) Permissive-language hard blocker (“should”) is creating direct false negatives

Multiple decisions say: even if the policy otherwise matches, any permissive wording (“should”) makes it a hard blocker for mapping.
	•	Example: “requirement … is permissive (‘should’), which is a hard blocker.”  ￼
	•	Another: remediation/validation sections use permissive “should” → NO_MATCH.  ￼

Why this causes FNs: many policies are written in “should” language even when intended as mandatory, or mix “must” + “should” across subsections. Treating “should” as automatic NO_MATCH will systematically miss real coverage.

⸻

4) “General policy statement” ≠ “specific control requirement” (often via G-14)

The model frequently rejects broad statements as insufficient for narrow control events.
	•	“Capture all actions…” is deemed too general; control requires logging specific credential/account modification events.  ￼
	•	“Disabling unnecessary utilities” doesn’t satisfy “disable PowerShell 2.0” specifically.  ￼

Why this causes FNs: controls that name a specific object/event (PowerShell 2.0, credential changes, system-level objects) will rarely be stated verbatim in policy. If you require literal specificity, you’ll miss valid “coverage by category.”

⸻

5) Pointer/“defined elsewhere” rule (G-12) causes NO_MATCH even when the doc clearly references the right control area

If a policy says “do X per Logging & Monitoring Policy” without restating requirements, the model rejects.
	•	“Only provides a pointer to another policy …” plus “general access rules … do not specifically address audit log files.”  ￼
	•	“Only contains an external pointer … without stating the actual requirements.”  ￼

Why this causes FNs: many policy sets are intentionally modular. If cross-references are treated as “no evidence,” you’ll under-map unless you always run a multi-doc retrieval pass.

⸻

6) Incomplete templates / placeholders trigger NO_MATCH (G-15), even if other parts match
	•	“Artifact is incomplete … empty placeholders; additionally … fragmented across separate non-contiguous sections.”  ￼

Why this causes FNs: templates often include placeholders for org-specific values; strict “placeholder = unusable” is reasonable, but it will create lots of misses if your policy corpus includes templated docs.

⸻

7) “Policy mandate” vs “technical mechanism required” mismatch (G-2 / G-1)

Controls requiring implemented mechanisms get rejected when the policy is purely behavioral.
	•	“Passwords must not be hard-coded” is not accepted because control requires “mechanisms to validate” (e.g., scanning).  ￼

Why this causes FNs: if your eval expects “policy-level commitment maps to technical control” (even partially), the current rule set is too strict.

⸻

What to change (if your goal is fewer false negatives)

These are the highest-leverage rule adjustments implied by the above:
	1.	Downgrade permissive-language from NO_MATCH → PARTIAL (with a “strength/enforceability gap”) instead of hard-blocking. This directly targets cases like the “should” examples.  ￼
	2.	Relax Evidence Locality: allow mapping when evidence can be satisfied by 2–4 snippets with separate location references, instead of forcing one contiguous quote. (This directly targets locality failures.)  ￼
	3.	Handle cross-references as “Needs referenced doc” (PARTIAL) rather than NO_MATCH, so the pipeline can fetch the referenced policy next.  ￼
	4.	Treat missing hard qualifiers as PARTIAL gaps more often (frequency, “external,” “after significant change,” “management approval”), rather than NO_MATCH.  ￼
	5.	For technical mechanism controls, allow policy-only statements to map as PARTIAL (“mechanism not specified”) rather than rejecting.  ￼

If you want, I can also produce a quick “rule → recommended new decision behavior” matrix (e.g., when G-10/G-14/G-12 should become PARTIAL vs remain NO_MATCH) using the most common FN patterns in your file.