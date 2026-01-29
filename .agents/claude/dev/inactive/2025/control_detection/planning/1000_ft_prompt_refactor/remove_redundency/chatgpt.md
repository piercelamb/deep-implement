Here are the main redundancy “clusters” I see in refactored_system.md, along with low-impact ways to consolidate them without losing meaning (and keeping intentional “core reminders” where helpful).

1) Decision labels are defined twice (Part 1 vs Part 5)
	•	Where it repeats
	•	Part 1 introduces MAPPED / PARTIAL / NO_MATCH as the primary outputs.  ￼
	•	Part 5 re-defines each decision again (“MAPPED means…”, etc.).  ￼  ￼  ￼
	•	Consolidation idea
	•	Keep Part 1 as the high-level list (that’s useful early), but replace the Part 5 “means:” lines with “See Part 1 for definitions; below are the decision criteria.” That removes true duplication while keeping structure.

2) “Default to NO_MATCH” + Golden Rule show up in 3 places
	•	Where it repeats
	•	Default NO_MATCH + Golden Rule in Part 1.  ￼
	•	Golden Rule reminder again in Part 5.3.  ￼
	•	Golden Rule reminder again in Closing.  ￼
	•	Consolidation idea
	•	This is core, so repetition is fine—but you can tighten it:
	•	Keep the full version in Part 1.
	•	In Part 5.3 and Closing, use a short tag like “Golden Rule: default NO_MATCH unless irrefutable.”

3) “IRs only after guardrails” is repeated verbatim
	•	Where it repeats
	•	Part 4.1 states “IRs can only be applied if NO guardrail is violated.”  ￼
	•	Part 6.4 repeats essentially the same reminder.  ￼
	•	Consolidation idea
	•	Keep it in Part 4.1 as the canonical statement.
	•	In Part 6.4, replace with “See Part 4.1 (Order of operations)” or shorten to a single-line label (since Part 6 is already a reference section).

4) “Don’t penalize for procedures/parameters/frequencies” appears in multiple forms
	•	Where it repeats
	•	Corollary in Part 1: don’t penalize missing procedures/technical parameters/frequencies.  ￼
	•	Part 5.2 “What is NOT a PARTIAL” repeats those same ideas in table form (procedures, parameters, frequencies, etc.).  ￼
	•	NO_MATCH verification checklist repeats the “not penalizing for procedures” reminder.  ￼
	•	Consolidation idea
	•	Keep the Part 1 corollary as the “source of truth”.
	•	In Part 5.2 and the NO_MATCH checklist, replace the repeated explanation with a pointer like: “Don’t penalize missing procedures/params/frequency (see Part 1 Corollary; see Core Mandate Test).”

5) “Expected mapping count ranges” appears twice
	•	Where it repeats
	•	Part 1 “Setting Expectations” provides ranges by policy type.  ￼
	•	Part 5.4 “Mass Mapping” repeats those ranges again.  ￼
	•	Consolidation idea
	•	Keep the table once (Part 1 is a good home).
	•	In “Mass Mapping,” replace the repeated ranges with “See Part 1 (Setting Expectations) for typical mapping counts.”

6) “If found → Proceed to Part 4” is duplicated exactly in Pass A and Pass B
	•	Where it repeats
	•	Pass A: “If found: Proceed to Part 4…”  ￼
	•	Pass B repeats the same line.  ￼
	•	Consolidation idea
	•	Keep it once after Pass B (or as a single line after the whole Pass A/B block): “If Pass A or B yields binding evidence, proceed to Part 4.”

7) “Subset coverage vs exclusion” logic appears in at least two sections
	•	Where it repeats
	•	Guardrail G-6 explains “subset without explicit exclusion can still be MAPPED.”  ￼
	•	Part 5.2 repeats the same principle (“Policy covers a subset… is MAPPED”).  ￼
	•	Consolidation idea
	•	Keep the full nuance in G-6 (since it’s the governing rule).
	•	In Part 5.2, shorten the repeated row to “Subset coverage without explicit exclusion is not a gap (see G-6).”

8) Guardrail / IR “index” repeats content that already exists (but this one is structurally redundant, not conceptually redundant)
	•	Where it repeats
	•	Part 6.3 Guardrail Index re-lists one-line descriptions of guardrails.  ￼
	•	Part 6.4 IR Index re-lists one-line descriptions of IRs.  ￼
	•	Consolidation idea (optional, low-risk)
	•	Keep the index (it’s useful), but consider making it mechanically derived from the canonical guardrail/IR definitions (so you don’t have to maintain the same text twice). That’s less about removing it and more about preventing drift.

⸻

A consolidation pattern that keeps your “core reminders” intact

You can remove most redundancies without deleting guidance by using a lightweight pattern:
	•	Canonical statement once (where it belongs)
	•	Short reminder later (“Reminder: default NO_MATCH”)
	•	Pointer instead of re-explaining (“See Part 1 Corollary / See G-6 / See Part 4.1”)

If you want, I can propose exact replacement wording for each repeated spot (minimal edits, same tone), but the list above should already tell you where the easiest wins are.  ￼