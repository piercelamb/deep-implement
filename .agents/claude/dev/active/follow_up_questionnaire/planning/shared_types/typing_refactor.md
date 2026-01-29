You can definitely get to something cleaner than what you have now, but it helps to name what “smells” here so the alternative is actually addressing the discomfort.

From the doc, the core situation is:
	•	CriterionEvidence.refs was typed too narrowly (Sequence[VellumDocExcerpt]), so anything else (follow-up responses) got dropped in output conversion.
	•	The “obvious” fix—make refs a union including VellumFollowupResponse—ran into an import cycle because questionnaire types inherit from evidence types, while evidence wanted to import questionnaire types for the union + deserialization logic.  ￼

Your chosen solution (extract base types + move VellumFollowupResponse next to its base) is a valid, pragmatic Python fix. The code-smell feeling usually comes from conceptual layering, not whether the cycle is broken:
	•	“Why does questionnaire depend on evidence (even if only Reference)?”
	•	“Why is a questionnaire response class living in evidence/schema.py?”
	•	“Why do I have to keep editing a union + dispatcher every time I add a ref type?”

Below are a couple approaches that tend to feel cleaner long-term, and how they’d map onto your system.

⸻

What I think is actually “off” in the current shape

1) Package ownership is doing architectural work

evidence/base.py is acting like a core module (foundational types used everywhere), but it lives under evidence. That’s why it feels like “questionnaire imports evidence”, which feels backwards even if it’s harmless technically.  ￼

A very small rename/move often eliminates 50% of the “smell”:
	•	schema/evidence/base.py → schema/core/reference.py (or schema/common/reference.py)
	•	Keep Reference, SourcedContent there

Now it’s “questionnaire depends on core”, not “questionnaire depends on evidence”.

2) CriterionEvidence is forced to know every concrete ref type

CriterionEvidence.from_dto() currently dispatches on ref_type and must import/mention every concrete evidence ref. That’s fine for 2 types, but it becomes churn and a hotspot as ref types grow.  ￼

This is where a different typing model helps.

⸻

Cleaner typing model: make refs an interface, not a union

Right now, refs is a closed set union:

CriterionEvidenceRef = VellumDocExcerpt | VellumFollowupResponse

That forces:
	•	tight imports
	•	union updates
	•	dispatcher updates
	•	dependency issues when types live in different modules

A cleaner model is: “refs contains anything that behaves like an evidence ref”.

Step 1: define a Protocol (structural type) for refs

Put this in a neutral module, e.g. schema/evidence/ref_api.py (or schema/core/evidence_ref.py):

from typing import Protocol, ClassVar, Mapping, Any

class EvidenceRef(Protocol):
    # required discriminator for DTO parsing
    ref_type: ClassVar[str]

    def to_assessment_webhook_dto(self) -> "AssessmentSourceWebhookDTO": ...
    def to_dto(self) -> Mapping[str, Any]: ...

Then:

refs: Sequence[EvidenceRef]

Now you don’t need a union at all for normal usage (iteration, serialization, webhook conversion). Mypy will enforce that all items have those methods.

Why this reduces “typing smell”:
	•	CriterionEvidence no longer needs to import concrete ref types to typecheck.
	•	Adding a new ref type doesn’t require editing a central union type just to store it.

Step 2: move parsing/dispatch out of CriterionEvidence (or make it pluggable)

You still need runtime dispatch on ref_type somewhere. The trick is to locate it in a module that is allowed to import all ref implementations, without creating cycles.

A simple pattern:
	•	schema/evidence/ref_parse.py imports all ref types (doc excerpt, followup response, etc.) and owns the dispatch table.
	•	CriterionEvidence.from_dto calls parse_ref(dto).

Example:

# schema/evidence/ref_parse.py
from typing import Mapping, Any
from .doc_excerpt import VellumDocExcerpt
from .followup import VellumFollowupResponse

_PARSERS = {
    VellumDocExcerpt.ref_type: VellumDocExcerpt.from_dto_any,
    VellumFollowupResponse.ref_type: VellumFollowupResponse.from_dto_any,
}

def parse_ref(d: Mapping[str, Any]) -> "EvidenceRef":
    ref_type = d.get("ref_type", "doc_excerpt")
    try:
        return _PARSERS[ref_type](d)
    except KeyError:
        raise ValueError(f"Unknown ref_type: {ref_type}")

Then:

# CriterionEvidence.from_dto
from schema.evidence.ref_parse import parse_ref
refs = [parse_ref(d) for d in dto["refs"]]

If you really want to avoid even that import direction, you can put CriterionEvidence.from_dto in the same module as the parser (or a higher “serialization” layer), leaving CriterionEvidence as a pure data container.

⸻

Fixing the “LSP / from_dto signature” concern without hacks

In the doc, you rejected putting from_dto on the base class because the base would accept a union type and subclasses would accept narrower DTOs (LSP issue).  ￼

There’s a simple way around this:
	•	Don’t make from_dto accept a union.
	•	Make it accept a generic mapping at the interface boundary, and cast inside.

Example for each ref class:

@classmethod
def from_dto_any(cls, dto: Mapping[str, Any]) -> "Self":
    typed = cast(VellumFollowupResponseRefDTO, dto)
    ...

Now:
	•	Every ref parser has the same signature (Mapping[str, Any] -> Self)
	•	Your registry/parsing table is type-consistent
	•	You still keep strict TypedDict types internally where they add value

This is a really common “typed edge, flexible boundary” technique.

⸻

Even cleaner layering: don’t make “questionnaire” and “evidence” depend on each other at all

If you’re willing to do a slightly bigger structural change, the “cleanest” architecture is:
	•	core: foundational types (Reference, Artifact, etc.)
	•	questionnaire: questionnaire domain models (indexing, internal semantics)
	•	evidence_refs: retrieval/evidence-facing wrappers (what you actually send to the webapp / LLM assessment)
	•	assessment/serialization: DTO parsing + dispatch

In that world:
	•	questionnaire does not inherit from evidence
	•	evidence does not import questionnaire
	•	the adapter layer can import both

Concretely, instead of moving VellumFollowupResponse into evidence/schema.py, you can introduce an adapter/wrapper type, e.g.:
	•	questionnaire/schema.py keeps FollowupResponse (domain object)
	•	evidence_refs/followup_response_ref.py defines VellumFollowupResponseRef that implements EvidenceRef and contains a FollowupResponse (composition)

This keeps “ownership” clean and prevents inheritance from creating cycles.

⸻

One more “smell” that’s not typing, but worth calling out

In your to_assessment_webhook_dto() for follow-ups, you’re mapping the response into docExcerpt=... and using metadata-based fields like fileId=self.metadata["form_id"].  ￼

That may be completely fine as a compatibility move, but if it feels weird, it’s because you’re forcing a new concept (follow-up response evidence) through an old shape (document excerpt). The “real” fix is usually to make the webhook DTO explicitly support multiple evidence kinds, e.g.:
	•	sourceType: "doc_excerpt" | "followup_response" | "soc2_summary"
	•	plus type-specific fields

If changing the webapp contract is expensive, the Protocol + parser cleanup still helps you keep the “hack” localized.

⸻

What I would do in your codebase as the next incremental step

Minimal churn, maximum “cleanliness gain”:
	1.	Move/rename evidence/base.py → a neutral schema/core/... module (or schema/common/...).
This is mostly mechanical but removes the “questionnaire depends on evidence” smell.
	2.	Introduce EvidenceRef Protocol and change CriterionEvidence.refs to Sequence[EvidenceRef].
You can still keep ref_type discriminators exactly as you have.
	3.	Create a small ref_parse.py module with a dispatch table and parse_ref().
That isolates “knowledge of all ref types” away from the core schema objects.
	4.	(Optional) If you anticipate more ref types: allow registration into the dispatch table so new ref types don’t require editing one central file (or keep the central file—it’s fine if the set is small and controlled).

If you want, I can sketch a concrete module layout based on the exact packages you showed (ai_services.shared.schema.evidence, ai_services.shared.schema.questionnaire, etc.) and show the smallest diff that implements Protocol + parse module without changing runtime behavior.

￼