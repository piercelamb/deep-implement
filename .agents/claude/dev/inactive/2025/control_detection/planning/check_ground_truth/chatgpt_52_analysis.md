Here are the biggest mistakes / footguns I see, plus what I’d add to make this robust.

Biggest footguns
	•	You’ll miss GT controls that were never evaluated in Phase 1. Phase 2 says “find GT in batch_*.json outputs” and collect PARTIAL/NO_MATCH  ￼, but if retrieval thresholding (or MAX_CALLS) prevented a GT control from ever appearing in any batch, it won’t exist in those files at all. That’s exactly the kind of error you’re trying to detect. Add an explicit third state like NOT_EVALUATED / NOT_RETRIEVED and run the judge on those too.
	•	Anchoring bias in the judge prompt. You include the original LLM’s decision + reasoning in the judge context  ￼. That will systematically bias the judge toward agreeing with the earlier model. A safer pattern:
	1.	“blind” judge (no original decision shown) → verdict + evidence
	2.	only then reveal original decision and ask “did the prior model miss anything / was it too strict?”
	•	Ambiguity around what to do with PARTIAL. You treat “non-MAPPED GT” as PARTIAL or NO_MATCH  ￼, but GT labels appear binary (policy maps / doesn’t). If the policy partially addresses a control, should GT stay or be removed? You need an explicit rule: either (a) GT should only contain “fully satisfied mandates”, or (b) GT can include partial coverage and you should add a new label (GT_PARTIAL) rather than forcing it into “keep/remove”.
	•	CLI flag confusion: --timestamp means “reuse experiment”, but you also generate a new validation timestamp. The plan’s example output includes both timestamp and experiment_timestamp  ￼, but the CLI example only has --timestamp  ￼. Rename the CLI arg to --experiment-timestamp (or similar) to avoid people overwriting/reading the wrong run.
	•	Path inconsistency (files/llm_outputs/... vs llm_outputs/...). In one place you describe experiment outputs under files/llm_outputs/control_centric/...  ￼, but Phase 4 says “Save to: llm_outputs/gt_validation/{timestamp}/”  ￼ while the File Structure shows it under files/llm_outputs/gt_validation/...  ￼. This will become an instant “where are my outputs?” trap—pick one root and codify it (preferably via a single config constant).

Missing pieces I’d add
	•	Resumability / idempotency. If a run dies midway, you want to restart without re-judging everything. Since you already plan to write judge_{control_id}.json  ￼, make the runner skip any control that already has an output file (unless --force).
	•	Concurrency + rate limiting. Judge-per-control is accurate but can explode into hundreds/thousands of calls (multi-doc + many non-mapped). Add:
	•	per-project QPS cap
	•	max in-flight tasks (async semaphore)
	•	exponential backoff on transient errors
	•	Evidence with location. Your schema asks for “evidence quotes”  ￼, but reviewers will want page number + snippet (or section heading) so they can verify quickly. Add fields like:
	•	evidence_page: int (or evidence_location: "p12 / §3.2")
	•	evidence_quote: short, bounded length
	•	Config capture for reproducibility. Write a run_metadata.json into the output dir containing:
	•	model name/version, temperature, max tokens
	•	prompt file hashes/versions
	•	retrieval threshold/MAX_CALLS (because those determine “NOT_EVALUATED” rates)
	•	code version/commit if available
This makes results defensible when someone asks “why did verdicts change?”.
	•	Quality control via “double-judge” on low confidence. You already have UNCERTAIN  ￼. For low confidence or UNCERTAIN, run a second independent judge pass (or self-consistency vote) and only escalate to GRC when they disagree.
	•	A concrete mechanism to update GT. You output CSVs for review  ￼, but you don’t describe how changes get applied back to eval.csv. Add one of:
	•	a patch file format (e.g., “remove control X from policy Y”, “add control Z”)
	•	a script that applies approved changes and writes a new eval.csv + changelog
	•	Handling cross-references. Policies often say “see Incident Response Plan”. Decide whether a reference counts as “addresses” (usually no, unless the mandate is in the doc) and instruct the judge accordingly—otherwise you’ll get inconsistent verdicts.

Small nits
	•	The architecture diagram calls the CLI run_gt_validation.py  ￼ but the file structure + examples use run_validation.py  ￼. Align names to reduce confusion.

If you want, I can rewrite the plan as a tighter “spec” with the new states (NOT_EVALUATED), a bias-resistant judge flow, and the exact output schema/filenames so implementation is straightforward.