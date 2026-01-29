⏺ Alright, putting on my grumpy senior dev hat. Here's my code review:

  ---
  Code Review: Shared Types Implementation

  🔴 Critical Issues

  1. External ID regex will break with hyphenated vendor IDs

  external_id_re = re.compile(
      r"""
      ^followup-                           # prefix
      (?P<vendor_id>[^-]+)                 # vendor_id  <-- THIS IS WRONG
      -
      (?P<criterion_hash>[0-9a-f]{16})

  If vendor_id is "acme-corp", the external_id becomes "followup-acme-corp-abc123...round1". Your regex [^-]+ stops at the first hyphen, extracting "acme" as the vendor_id. This will silently corrupt data.

  2. Silent failures with empty string defaults

  tenant_id=str(metadata.get("tenant_id", "")),
  vendor_id=str(metadata.get("vendor_id", "")),
  round_number=int(metadata.get("round_number", 0)),

  Missing metadata loads successfully with garbage defaults. You'll discover this when your search returns results with vendor_id="" and round_number=0. Should these raise MissingMetadata or at least log warnings?

  3. Timezone handling is broken

  submitted_at=datetime.fromisoformat(
      str(metadata.get("timestamp", datetime.min.isoformat()))
  )

  - datetime.min.isoformat() returns "0001-01-01T00:00:00" which is probably not what you want
  - No timezone awareness - mixing naive and aware datetimes will cause comparison bugs
  - datetime.fromisoformat() can't parse "2024-01-15T10:30:00Z" (the Z suffix) - only works in Python 3.11+

  ---
  🟡 Design Concerns

  4. One-way serialization

  def to_dto(self) -> FollowupQuestionnaireDTO:
      ...
  # Where's from_dto()?

  FollowupQuestionnaire has to_dto() but no from_dto(). How do you deserialize? You have from_metadata_dict() but DTOs and metadata dicts have different key names (artifact_id vs ARTIFACT_ID). Inconsistent interfaces.

  5. Inheritance depth is excessive

  VellumFollowupResponse
    → RankedFollowupResponse
      → FollowupResponse
        → QuestionnaireResponse
          → Reference  (from evidence.schema)

  Five levels of inheritance for what is essentially a data container. Why not composition? Every time someone touches Reference, all 4 children need testing.

  6. Questionnaire type alias is imported but unused

  from ai_services.shared.schema.artifact.schema import (
      FollowupQuestionnaire,
      Questionnaire,  # <-- never used in this file
  )

  Dead import. What was the intention here?

  ---
  🟡 Missing Edge Case Tests

  7. No validation of criterion_hash format

  Test passes any 16-char hex string. What if someone passes "????????????????" or "0000000000000000"? Should there be validation that it was computed via your normalization?

  8. Missing test cases:

  - Empty question or answer strings - valid or error?
  - round_number = 0 - is this valid? Negative?
  - round_number as string "2" vs int 2 in metadata
  - Unicode in vendor_id/tenant_id (e.g., "北京公司")
  - Very long criterion text (what's the hash distribution?)
  - Vendor ID with special regex characters (vendor.id, vendor[1])
  - metadata containing extra keys not in schema

  9. No integration-style test

  You test from_vector_db_search_result with hand-crafted VectorDbSearchResult objects. Where's the test that uses actual Vellum response structure? What if Vellum's actual metadata has different key casing?

  ---
  🟡 Code Smells

  10. Inconsistent metadata key names

  In build_vellum_metadata():
  "criterion_content_hash": self.criterion_hash,

  In from_vector_db_search_result():
  criterion_hash = parsed.group("criterion_hash")  # from external_id
  # but metadata.get("criterion_content_hash") is ignored!

  You're extracting from the external_id regex but ignoring the metadata field. If they ever diverge, which wins?

  11. SourcedContent.generate_content_hash dependency

  content_hash=SourcedContent.generate_content_hash(result.text),

  You're coupling to SourcedContent for hash generation. Is this the same algorithm as normalize_and_hash? Now you have two hash functions.

  12. Class-level regex is a class variable

  external_id_re = re.compile(...)

  This compiles once at import time (good for perf), but it's a mutable class variable. Not frozen. A determined bug could VellumFollowupResponse.external_id_re = None.

  ---
  Summary

  The implementation follows the plan, but it has:
  - A showstopper bug with hyphenated vendor IDs
  - Silent data corruption from empty string defaults
  - Timezone bugs waiting to happen
  - Insufficient test coverage for edge cases

  My recommendation: Fix the vendor_id regex (maybe use a different delimiter like | or encode vendor_id), add validation/logging for missing metadata, and add tests for the edge cases before merging.