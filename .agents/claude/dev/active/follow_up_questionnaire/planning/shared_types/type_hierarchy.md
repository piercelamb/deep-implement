# Type Hierarchy: Before & After

Visual representation of the type system changes for follow-up questionnaire support.

---

## Before: Current Type Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARTIFACT HIERARCHY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Artifact                                                                   │
│   ├── artifact_id: UUID                                                      │
│   ├── remote_key: str                                                        │
│   ├── bucket: str                                                            │
│   └── ext: Ext                                                               │
│           │                                                                  │
│           ├───────────────────┬────────────────────┐                         │
│           │                   │                    │                         │
│           ▼                   ▼                    ▼                         │
│       Document            Tabular            (nothing)                       │
│       ├── pages           ├── sheets          ← No JSON                      │
│       │                   │                     artifact type                │
│       ▼                   │                                                  │
│      SOC2                 └── UNUSED                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          EVIDENCE HIERARCHY                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Reference                                                                  │
│   └── source: Artifact                                                       │
│           │                                                                  │
│           ├───────────────────────────────────────┐                          │
│           │                                       │                          │
│           ▼                                       ▼                          │
│   QuestionnaireAnswer                      SourcedContent                    │
│   └── source: Tabular                      ├── content: str                  │
│       ← UNUSED                             └── content_hash: str             │
│                                                   │                          │
│                                                   ▼                          │
│                                              DocExcerpt                      │
│                                                   │                          │
│                                                   ▼                          │
│                                           RankedDocExcerpt                   │
│                                           ├── first_stage_score              │
│                                           ├── second_stage_score             │
│                                           └── third_stage_score              │
│                                                   │                          │
│                                                   ▼                          │
│                                           VellumDocExcerpt                   │
│                                           ├── metadata                       │
│                                           └── from_vector_db_search_result() │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            ARTIFACT TYPES                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ArtifactType (StrEnum)                                                     │
│   ├── SOC_2_TYPE_2                                                           │
│   ├── SOC_2_TYPE_1                                                           │
│   ├── SOC_1_TYPE_2                                                           │
│   └── SOC_1_TYPE_1                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## After: New Type Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ARTIFACT HIERARCHY                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Artifact                                                                   │
│   ├── artifact_id: UUID                                                      │
│   ├── remote_key: str                                                        │
│   ├── bucket: str                                                            │
│   └── ext: Ext                                                               │
│           │                                                                  │
│           ├─────────────────────┬─────────────────────┬────────────────────┐ │
│           │                     │                     │                    │ │
│           ▼                     ▼                     ▼                    │ │
│       Document              Tabular              ╔═══════════╗             │ │
│       ├── pages             ├── sheets           ║ JsonData  ║  ◀── NEW    │ │
│       │                     │                    ╚═════╤═════╝             │ │
│       ▼                     │                          │                   │ │
│      SOC2                   │                          │                   │ │
│                             │                          │                   │ │
│                             ▼                          ▼                   │ │
│                ╔════════════════════════╗   ╔══════════════════════╗       │ │
│                ║ TabularQuestionnaire   ║   ║  JsonQuestionnaire   ║ ◀─NEW │ │
│                ╚════════════╤═══════════╝   ╚══════════╤═══════════╝       │ │
│                             │                          │                   │ │
│                             │                          │                   │ │
│                             └──────────┬───────────────┘                   │ │
│                                        │                                   │ │
│                                        ▼                                   │ │
│                          ╔═════════════════════════════╗                   │ │
│                          ║       Questionnaire         ║ ◀── UNION TYPE   │ │
│                          ║ (TabularQuestionnaire |     ║                   │ │
│                          ║  JsonQuestionnaire)         ║                   │ │
│                          ╚═════════════════════════════╝                   │ │
│                                                                            │ │
│                                        │                                   │ │
│                       (JsonQuestionnaire branch)                           │ │
│                                        │                                   │ │
│                                        ▼                                   │ │
│                          ╔═════════════════════════════╗                   │ │
│                          ║  FollowupQuestionnaire      ║ ◀── NEW          │ │
│                          ╠═════════════════════════════╣                   │ │
│                          ║  (S3 pointer only - no      ║                   │ │
│                          ║   runtime context fields)   ║                   │ │
│                          ╠═════════════════════════════╣                   │ │
│                          ║  artifact_type → FOLLOWUP_  ║                   │ │
│                          ║                QUESTIONNAIRE║                   │ │
│                          ║  from_metadata_dict()       ║                   │ │
│                          ╚═════════════════════════════╝                   │ │
│                                                                            │ │
└────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          VALUE OBJECTS                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ╔═══════════════════════════════════╗                                      │
│   ║       QuestionnaireItem           ║ ◀── NEW (source-agnostic Q&A)        │
│   ╠═══════════════════════════════════╣                                      │
│   ║  question: str                    ║                                      │
│   ║  answer: str                      ║                                      │
│   ║  notes: str | None                ║                                      │
│   ╠═══════════════════════════════════╣                                      │
│   ║  @property embedding_content      ║  → "Question: {q} Answer: {a}"       │
│   ║  to_dto()                         ║                                      │
│   ║  from_dto() → Self                ║                                      │
│   ╚═══════════════════════════════════╝                                      │
│                                                                              │
│   ╔═══════════════════════════════════╗                                      │
│   ║  FollowupQuestionnaireHydrated    ║ ◀── NEW (artifact + parsed content)  │
│   ╠═══════════════════════════════════╣                                      │
│   ║  artifact: FollowupQuestionnaire  ║                                      │
│   ║  items: Sequence[QuestionnaireItem]                                      │
│   ╠═══════════════════════════════════╣                                      │
│   ║  from_json(artifact, data) → Self ║                                      │
│   ╚═══════════════════════════════════╝                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          EVIDENCE HIERARCHY                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Reference                                                                  │
│   └── source: Artifact                                                       │
│           │                                                                  │
│           ├───────────────────────────────────────────────────────────┐      │
│           │                                                           │      │
│           ▼                                                           ▼      │
│   ╔═══════════════════════════════════╗                        SourcedContent│
│   ║     QuestionnaireResponse         ║ ◀── NEW                ├── content   │
│   ╠═══════════════════════════════════╣                        └── hash      │
│   ║  source: Questionnaire            ║                              │       │
│   ║  item: QuestionnaireItem          ║                              ▼       │
│   ╚═══════════════════╤═══════════════╝                         DocExcerpt   │
│                       │                                              │       │
│                       ▼                                              ▼       │
│   ╔═══════════════════════════════════╗                      RankedDocExcerpt│
│   ║       FollowupResponse            ║ ◀── NEW                      │       │
│   ╠═══════════════════════════════════╣                              ▼       │
│   ║  source: FollowupQuestionnaire    ║                      VellumDocExcerpt│
│   ║  criterion_hash: str              ║                                      │
│   ║  original_criterion_question_text: str     ║                                      │
│   ╠═══════════════════════════════════╣                                      │
│   ║  DOC_TYPE = "FOLLOWUPQUESTIONNAIRE"                                      │
│   ║  TYPE_PREFIX = "followup_response:"                                      │
│   ╠═══════════════════════════════════╣                                      │
│   ║  build_metadata_type(round)       ║  → "followup_response:{round}"       │
│   ║  build_filename(vendor, round)    ║                                      │
│   ║  build_external_id(tenant,        ║                                      │
│   ║    vendor, round)                 ║                                      │
│   ║  build_vellum_metadata(...)       ║  (runtime context as params)         │
│   ╚═══════════════════╤═══════════════╝                                      │
│                       │                                                      │
│                       ▼                                                      │
│   ╔═══════════════════════════════════╗                                      │
│   ║    RankedFollowupResponse         ║ ◀── NEW                              │
│   ╠═══════════════════════════════════╣                                      │
│   ║  first_stage_score: float         ║                                      │
│   ║  second_stage_score: float | None ║                                      │
│   ║  third_stage_score: float | None  ║                                      │
│   ╚═══════════════════╤═══════════════╝                                      │
│                       │                                                      │
│                       ▼                                                      │
│   ╔═══════════════════════════════════╗                                      │
│   ║    VellumFollowupResponse         ║ ◀── NEW                              │
│   ╠═══════════════════════════════════╣                                      │
│   ║  metadata: Mapping[str, Any]      ║                                      │
│   ║  content: str                     ║                                      │
│   ║  content_hash: str                ║                                      │
│   ╠═══════════════════════════════════╣                                      │
│   ║  external_id_re: Pattern          ║                                      │
│   ║  from_vellum_search_res()         ║                                      │
│   ║  from_vector_db_search_result()   ║                                      │
│   ╚═══════════════════════════════════╝                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            ARTIFACT TYPES                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ArtifactType (StrEnum)                                                     │
│   ├── SOC_2_TYPE_2                                                           │
│   ├── SOC_2_TYPE_1                                                           │
│   ├── SOC_1_TYPE_2                                                           │
│   ├── SOC_1_TYPE_1                                                           │
│   └── ╔═══════════════════════════╗                                          │
│       ║ FOLLOWUP_QUESTIONNAIRE    ║ ◀── NEW                                  │
│       ╚═══════════════════════════╝                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            DTOs (TypedDict)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ╔═══════════════════════════════════╗                                      │
│   ║       QuestionnaireItemDTO        ║ ◀── NEW                              │
│   ╠═══════════════════════════════════╣                                      │
│   ║  question: str                    ║                                      │
│   ║  answer: str                      ║                                      │
│   ║  notes: str | None                ║                                      │
│   ╚═══════════════════════════════════╝                                      │
│                                                                              │
│   ╔═══════════════════════════════════╗                                      │
│   ║    FollowupQuestionnaireDTO       ║ ◀── NEW (S3 pointer only)            │
│   ╠═══════════════════════════════════╣                                      │
│   ║  artifact_id: str                 ║                                      │
│   ║  remote_key: str                  ║                                      │
│   ║  bucket: str                      ║                                      │
│   ║  ext: str                         ║                                      │
│   ╚═══════════════════════════════════╝                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         STRING UTILITIES                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Location: ai_services/shared/helpers/strings.py ◀── NEW FILE               │
│                                                                              │
│   ╔═══════════════════════════════════════════════════════════════════════╗  │
│   ║  normalize_for_hash(text: str) → str                                  ║  │
│   ╠═══════════════════════════════════════════════════════════════════════╣  │
│   ║  - Unicode NFC normalization                                          ║  │
│   ║  - Lowercase                                                          ║  │
│   ║  - Whitespace collapsed to single spaces                              ║  │
│   ║  - Leading/trailing whitespace stripped                               ║  │
│   ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
│   ╔═══════════════════════════════════════════════════════════════════════╗  │
│   ║  compute_sha256_prefix(text: str, length: int = 16) → str             ║  │
│   ╠═══════════════════════════════════════════════════════════════════════╣  │
│   ║  - SHA256 hash of input text                                          ║  │
│   ║  - Returns first `length` hex characters                              ║  │
│   ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
│   ╔═══════════════════════════════════════════════════════════════════════╗  │
│   ║  normalize_and_hash(text: str, length: int = 16) → str                ║  │
│   ╠═══════════════════════════════════════════════════════════════════════╣  │
│   ║  - Combines normalize_for_hash + compute_sha256_prefix                ║  │
│   ║  - Primary function for criterion hash generation                     ║  │
│   ╚═══════════════════════════════════════════════════════════════════════╝  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Parallel Hierarchies: Documents vs Questionnaires

The new design creates parallel evidence hierarchies that mirror each other:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DOCUMENT PATH                │     QUESTIONNAIRE PATH    │
├────────────────────────────────────────────────┼────────────────────────────┤
│                                                │                            │
│  Document (Artifact)                           │  Questionnaire (Artifact)  │
│      │                                         │      │                     │
│      ▼                                         │      ▼                     │
│  SourcedContent (Reference)                    │  QuestionnaireResponse     │
│  └── content, content_hash                     │  └── source, item          │
│      │                                         │      │                     │
│      ▼                                         │      ▼                     │
│  DocExcerpt                                    │  FollowupResponse          │
│  └── page, location                            │  └── criterion_hash        │
│      │                                         │      │                     │
│      ▼                                         │      ▼                     │
│  RankedDocExcerpt                              │  RankedFollowupResponse    │
│  └── scores                                    │  └── scores                │
│      │                                         │      │                     │
│      ▼                                         │      ▼                     │
│  VellumDocExcerpt                              │  VellumFollowupResponse    │
│  └── metadata                                  │  └── metadata              │
│  └── from_vector_db_search_result()            │  └── from_vector_db_...()  │
│                                                │                            │
└────────────────────────────────────────────────┴────────────────────────────┘
```

---

## External ID Format

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   {tenant_id}--{vendor_id}--FOLLOWUPQUESTIONNAIRE--{criterion_hash}--{round} │
│                                                                              │
│   Example: abc123--vendor456--FOLLOWUPQUESTIONNAIRE--a1b2c3d4e5f67890--2     │
│                                                                              │
│   ┌───────────┬───────────┬──────────────────────┬────────────┬───────┐      │
│   │ tenant_id │ vendor_id │      doc_type        │  criterion │ round │      │
│   │  (UUID)   │  (UUID)   │ "FOLLOWUPQUESTIONNAIRE"│   _hash   │  num  │      │
│   │           │           │                      │ (16 hex)   │       │      │
│   └───────────┴───────────┴──────────────────────┴────────────┴───────┘      │
│                                                                              │
│   Note: Fields are separated by "--" (double dash)                           │
│   Note: tenant_id and vendor_id may contain single dashes (e.g. UUIDs)       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Organization After Implementation

```
ai_services/shared/
├── schema/
│   ├── artifact/
│   │   ├── metadata.py         ← Add FOLLOWUP_QUESTIONNAIRE
│   │   ├── schema.py           ← Add JsonData, TabularQuestionnaire,
│   │   │                         JsonQuestionnaire, FollowupQuestionnaire,
│   │   │                         Questionnaire (union type)
│   │   ├── util.py             ← Add require_str() helper
│   │   └── types.py            ← Unchanged (Ext.JSON already exists)
│   │
│   ├── questionnaire/          ← NEW DIRECTORY
│   │   ├── __init__.py
│   │   └── schema.py           ← QuestionnaireItem, QuestionnaireResponse,
│   │                             FollowupResponse, RankedFollowupResponse,
│   │                             VellumFollowupResponse,
│   │                             FollowupQuestionnaireHydrated
│   │
│   ├── dto.py                  ← Add QuestionnaireItemDTO,
│   │                             FollowupQuestionnaireDTO
│   │
│   └── evidence/
│       └── schema.py           ← Unchanged (Reference base class)
│
└── helpers/
    ├── __init__.py             ← Export string helpers
    └── strings.py              ← NEW: normalize_for_hash(), compute_sha256_prefix(),
                                  normalize_and_hash()
```

---

## Legend

```
╔═══════════════════╗
║   NEW TYPE        ║  Double-line box = New type being added
╚═══════════════════╝

┌───────────────────┐
│   Existing type   │  Single-line box = Existing type
└───────────────────┘

◀── NEW              Arrow annotation = New addition

→                    Property/return type indicator
```
