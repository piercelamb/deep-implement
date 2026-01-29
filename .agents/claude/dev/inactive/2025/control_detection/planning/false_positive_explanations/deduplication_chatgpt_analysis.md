A few suggestions based on what you observed in the dedup run (and where the reduction “stalled” at 2.2×).  ￼

1) (control_id, IR_rule) is a good first compression, but it can over-merge different failure modes

You’re now grouping “everything that looks like DCF-13 + IR-6” together—even if the reason it was wrong differs across policies (e.g., aspirational language vs scope mismatch vs non-binding “purpose” section).

Upgrade: keep (control_id, IR_rule) as the base, but split into 2–5 sub-buckets using a cheap “evidence archetype” feature, e.g.:
	•	EVIDENCE_SECTION: purpose/scope vs requirements/procedure vs definitions
	•	BINDINGNESS: must/shall/required vs should/may/encourage vs purely descriptive
	•	SPECIFICITY: has numbers/durations/frequencies vs none
	•	REFERENCE_ONLY: just names a standard/framework (ISO/NIST/etc.) without obligation language

Signature becomes:
(control_id, IR_rule, evidence_archetype) → still stable across policies, but much more actionable.

This often gives you better dedupe than evidence hashing, while avoiding “one giant blob per control+IR”.

⸻

2) Evidence-hash dedupe failed because you used exactness; switch to near-duplicate matching

Your core finding (“quotes are unique per policy”) is true for strict hashes, but many policies share templated language that won’t match exactly.

Instead of md5(normalized_quote), try fuzzy / locality-sensitive approaches:
	•	SimHash / MinHash over token shingles (works well on near-duplicate boilerplate)
	•	Normalize harder:
	•	strip org names, dates, version strings
	•	strip headings like “Purpose”, “Scope”, “Policy”
	•	lemmatize/stem; remove stopwords
	•	keep only content words + modal verbs (must/shall/should) + negations

Then signature becomes:
(control_id, IR_rule, fuzzy_bucket_id) where fuzzy_bucket_id is derived from SimHash distance or MinHash Jaccard buckets.

This can recover a lot of the reduction you expected from “evidence-based dedupe,” without requiring identical quotes.

⸻

3) Add semantic clustering within (control_id, IR_rule) for the long tail

For each (control_id, IR_rule) group, embed control_text + evidence_excerpt (+section_header) and cluster.

Then you review only:
	•	the cluster medoid(s) (1–3 per big group), plus
	•	1 random extra per large cluster (quality check)

This typically squeezes the 1,878 “patterns” further, because many of the freq=1 “patterns” are semantically the same mistake phrased differently.

⸻

4) Double-check one stats red flag

Your IR table shows pattern count == FP count for many IRs (e.g., IR-3: 1,345 FPs and 1,345 patterns). That would imply almost no dedupe within IR-3, which is surprising given you also report 1,878 total patterns from 4,104 FPs.

I’d sanity check that your “pattern count per IR” is computed from unique signatures (not raw rows) under the same signature mode. This kind of mismatch is often a reporting bug, and it matters because it changes how you prioritize IR tightening.

⸻

5) Sampling plan tweaks (yours is good; make it more “guaranteed representative”)

Your buckets are a solid start. I’d make two changes:

A) Sample by pattern weight for prevalence estimates

When you want “distribution of root causes,” weight patterns by their FP frequency; otherwise you’ll over-learn from rare one-offs.

B) Add hard quotas for coverage

In addition to “freq ≥ 6 mandatory,” enforce:
	•	each IR rule: at least min(20, 5% of its patterns) reviewed
	•	each policy doc: at least 3–5 reviewed (even if it’s quiet)
	•	head controls (top N controls by FP volume): review all their high-frequency patterns

This prevents missing “small-but-systemic” doc families and IRs.

⸻

6) Turn this into a fix-prioritization machine (not just analysis)

Once you have the above grouping, compute “expected FP reduction if we fix X”:
	•	Fix candidate = (IR rule change) or (control family rule) or (bindingness constraint)
	•	Lift estimate = sum of FP frequencies for all patterns in buckets addressed

That lets you ship changes that eliminate the most FPs first, and you can re-run the same grouped eval to verify.

⸻

If I had to pick just 2 next steps
	1.	Add evidence archetype to (control_id, IR_rule) and use that as your new pattern key.
	2.	Add semantic clustering inside big (control_id, IR_rule) groups so the “freq=1” tail becomes reviewable.

If you paste (or upload) a small sample of the FP rows schema (what fields you have for evidence, section, chunk ids, confidence), I can suggest an exact signature + archetype rules that fit what you already log.