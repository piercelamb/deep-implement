# VRM Agent Follow-up Questionnaire: Merged Analysis

This document synthesizes recommendations from three AI models (Opus, Gemini, ChatGPT) on handling follow-up questionnaire data in the VRM Agent assessment pipeline.

---

## Consensus: The Core Problem

All three models agree on the fundamental issue:

**Relying purely on vector similarity for follow-up response retrieval is fragile and insufficient.**

Reasons:
1. **Semantic drift** - When users modify follow-up questions, the link between original criterion and vendor response is broken
2. **Embedding quality variance** - Short/terse vendor responses embed poorly compared to dense policy documents
3. **Chunking effects** - Follow-up responses may be outweighed by larger document chunks
4. **Volume crowding** - Hundreds of thematically similar policy chunks can crowd out follow-up responses in top_k

---

## Defining "Precedence"

Before choosing a solution, clarify what "precedence" means (ChatGPT):

| Type | Meaning |
|------|---------|
| **Hard precedence** | Follow-up data is *always* included and outweighs older evidence |
| **Soft precedence** | Follow-up data is *more likely* to appear but not guaranteed |
| **Scoped precedence** | Follow-up answers preferred *only* for the specific criteria they address |

**Product expectation is typically: Hard + Scoped** - "If the vendor answered this specific criterion, always use it first for this criterion."

---

## The "No Modify" Case: Mostly Works, But Not Guaranteed

When users don't modify the follow-up questionnaire:

**Why it should work:**
- Same criterion text = consistent query embedding
- Follow-up Q&A semantically matches the criterion

**Why it can still fail:**
- Vendor gives terse/ambiguous response ("Yes, we do this annually")
- SOC2 has detailed passages with high keyword overlap that dominate similarity
- Reranking/MMR/diversity logic demotes short snippets
- Conflicting information: SOC2 says "We don't do X" (old), follow-up says "We now do X" (new) - LLM gets confused

**Recommendation:** Even for the unmodified case, implement deterministic inclusion via content-based hash linkage rather than trusting top_k ranking.

---

## The "Modified" Case: Requires Architectural Intervention

When users modify follow-up questions, semantic similarity breaks down entirely.

**Example:**
```
Original Criterion: "Does the vendor encrypt data at rest using AES-256?"
Modified Question:  "Please describe your storage security practices and certifications."
Vendor Response:    "We use Google Cloud Storage with default encryption and are ISO 27001 certified..."
```

Querying with the original criterion text will likely NOT retrieve this response in top_k.

---

## Recommended Solution: Content-Based Hashing + Hybrid Retrieval

**All three models converge on this approach.** It combines:
1. Content-based hash linking (resilient to criterion ID changes)
2. Semantic search fallback for edge cases + supporting context
3. Prompt engineering for precedence
4. **Multi-round support** with bounded accumulation and recency precedence

### Multi-Round Strategy: Bounded Accumulation

Assessments can go through multiple follow-up rounds:

```
Round 1: Initial assessment → NOT_MET → Follow-up Q1 → Response R1
Round 2: Re-assessment → INCONCLUSIVE → Follow-up Q2 → Response R2
Round 3: Re-assessment → uses R1 + R2 + documents
...
```

**Strategy:** Fetch the N most recent follow-up rounds, present them in reverse chronological order, and instruct the LLM to prefer the most recent response when conflicts exist.

This handles the degenerate case (infinite rounds) by capping retrieval while preserving the most relevant recent context.

### Why Content-Based Hashing Instead of Criterion IDs

Using `criterion_id` for linkage is fragile because criteria can be edited:

```
Time 1: criterion_id="123", text="Does vendor encrypt at rest with AES-256?"
        → Follow-up R1 linked to criterion_id="123"

Time 2: User edits criterion to: "Does vendor have SOC2 Type II?"
        → criterion_id is still "123"
        → R1 (about encryption) incorrectly surfaces for SOC2 question ❌
```

**Solution:** Hash the criterion text content. Linkage is now **content-based** rather than **identity-based**:

```
Time 1: hash("Does vendor encrypt at rest with AES-256?") = "abc123"
        → R1 linked to criterion_question_hash="abc123"

Time 2: hash("Does vendor have SOC2 Type II?") = "xyz789"
        → R1 with hash "abc123" does NOT match "xyz789"
        → R1 is correctly orphaned ✓
```

**Edge case - minor typo fixes:** If a user fixes a typo, the hash changes and old follow-ups won't match via metadata filter. However, the semantic search path (Path 2 below) can still surface these responses since they remain semantically similar. This provides a graceful fallback.

### Implementation

**1. Data Model**

The embedded `content` field combines Question + Answer for better semantic matching.
Raw text is stored separately in metadata for structured access and display.

**Important:** The system supports two types of follow-up responses:
- **Criterion-linked**: Auto-generated from NOT_MET/INCONCLUSIVE criteria
- **Ad-hoc**: User-added questions not tied to any criterion

```python
# Store follow-up responses with content-based linkage AND round tracking
{
    # Embedded content: combines Q&A for semantic search
    "content": "Question: Please describe your encryption practices Answer: We use AES-256 for all data at rest with AWS KMS.",

    "metadata": {
        "source_type": "follow_up_response",
        # content_hash = hash(criterion_question_text || question_text) - ensures uniqueness
        "content_hash": "sha256_of_criterion_plus_question",
        # criterion_question_hash - for retrieval filtering (None for ad-hoc questions)
        "criterion_question_hash": "sha256_of_normalized_criterion",  # or None for ad-hoc
        "original_criterion_question_text": "Does the vendor encrypt data at rest...",  # Empty for ad-hoc
        "question_text": "Please describe your encryption practices",  # Raw question
        "answer_text": "We use AES-256 for all data at rest with AWS KMS.",  # Raw answer
        "vendor_id": "...",
        "round_number": 2,        # Which follow-up iteration this came from
        "timestamp": "...",       # For ordering within/across rounds
    }
}

def compute_content_hash(criterion_question_text: str, question_text: str) -> str:
    """Compute a stable hash for external_id uniqueness.

    This hash ensures uniqueness for:
    - Same criterion with different questions (copy-paste scenario)
    - Ad-hoc questions (criterion_question_text is empty)
    """
    normalized = " ".join(f"{criterion_question_text}||{question_text}".lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]

def compute_criterion_question_hash(criterion_question_text: str) -> str | None:
    """Compute a stable hash for criterion-based retrieval filtering.

    Returns None for ad-hoc questions (empty criterion_question_text).
    """
    if not criterion_question_text:
        return None
    normalized = " ".join(criterion_question_text.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]

def format_embedding_content(question: str, answer: str) -> str:
    """Format Q&A for embedding. Prefixes help the model understand structure."""
    return f"Question: {question} Answer: {answer}"
```

**Why this structure:**
- `content` captures both Q&A → semantic search can match on either the question or the answer
- "Question:"/"Answer:" prefixes give the embedding model structural hints
- Raw `question_text`/`answer_text` in metadata enables structured access, UI display, auditability
- No parsing needed to extract individual fields at retrieval time
- **Two hash fields serve different purposes:**
  - `content_hash` (criterion + question): uniqueness for external_id
  - `criterion_question_hash` (criterion only): retrieval filtering by criterion

**Ad-hoc question example:**
```python
{
    "content": "Question: Do you have a business continuity plan? Answer: Yes, we have a BCP reviewed annually.",
    "metadata": {
        "source_type": "follow_up_response",
        "content_hash": "abc123...",  # hash("" || "Do you have a business continuity plan?")
        "criterion_question_hash": None,  # Ad-hoc - no criterion
        "original_criterion_question_text": "",  # Empty for ad-hoc
        "question_text": "Do you have a business continuity plan?",
        "answer_text": "Yes, we have a BCP reviewed annually.",
        ...
    }
}
```

**2. Retrieval Logic**

```python
from ai_services.vellum.libs.strings import fuzzy_match

MAX_FOLLOWUP_ROUNDS = 3  # Configurable: how many rounds of history to include
FUZZY_MATCH_THRESHOLD = 0.7  # Minimum similarity for question text precedence

async def retrieve_for_criterion_assessment(
    criterion_question_text: str,
    vendor_id: str,
) -> AssessmentContext:
    # Compute content hash for the current criterion
    criterion_question_hash = compute_criterion_question_hash(criterion_question_text)

    # Path 1: Fetch follow-up responses by content hash (deterministic match)
    follow_up_responses_by_hash = await fetch_by_metadata(
        filter={
            "criterion_question_hash": criterion_question_hash,
            "vendor_id": vendor_id,
            "source_type": "follow_up_response",
        },
        order_by="round_number DESC",
        limit=MAX_FOLLOWUP_ROUNDS,
    )

    # Path 2: Semantic search against ALL documents (including follow-ups)
    # This provides fallback for edge cases like typo fixes where hash doesn't match
    semantic_results = await vector_search(
        query=criterion_question_text,
        top_k=10,
    )

    # Separate semantic results into follow-ups and documents
    semantic_follow_ups = [r for r in semantic_results if r.source_type == "follow_up_response"]
    document_chunks = [r for r in semantic_results if r.source_type != "follow_up_response"]

    # Classify follow-ups into precedence tiers using fuzzy_match on question text
    # This handles cases where hash matches but question was modified significantly
    hash_matched_ids = {r.id for r in follow_up_responses_by_hash}

    high_precedence = []  # Hash match AND question text is similar
    medium_precedence = []  # Hash match but question diverged significantly
    low_precedence = []  # No hash match (semantic only)

    for response in follow_up_responses_by_hash:
        # Check how much the follow-up question diverged from the criterion
        similarity = fuzzy_match(
            criterion_question_text.lower(),
            response.metadata.question_text.lower()
        )
        if similarity >= FUZZY_MATCH_THRESHOLD:
            high_precedence.append(response)
        else:
            # Hash matched but question was heavily modified - demote precedence
            medium_precedence.append(response)

    for response in semantic_follow_ups:
        if response.id not in hash_matched_ids:
            low_precedence.append(response)

    # Merge with tiered precedence: high > medium > low
    all_follow_ups = merge_and_dedupe_tiered(
        tiers=[high_precedence, medium_precedence, low_precedence],
        limit=MAX_FOLLOWUP_ROUNDS,
    )

    return AssessmentContext(
        follow_up_responses=all_follow_ups,  # Ordered: precedence tier, then newest first
        supporting_documents=document_chunks,
    )
```

**Precedence Tiers Explained:**

| Tier | Hash Match | Question Similarity | When This Happens |
|------|------------|---------------------|-------------------|
| **High** | ✓ | ≥ threshold | Unmodified or lightly edited question |
| **Medium** | ✓ | < threshold | User heavily rewrote the question |
| **Low** | ✗ | N/A | Semantic match only (typo fix, orphaned) |

**Why fuzzy_match on question text?**

Even when `criterion_question_hash` matches, the user may have significantly modified the follow-up question:

```
Criterion: "Does the vendor encrypt data at rest using AES-256?"
Original Q: "Does the vendor encrypt data at rest using AES-256?"  → similarity: 1.0 (high precedence)
Modified Q: "Please describe ALL your security practices."         → similarity: 0.3 (medium precedence)
```

The modified question's answer might be tangentially related but shouldn't have the same confidence level as an unmodified question's answer. The fuzzy_match check provides this nuance.

**Implementation note:** Uses `ai_services.vellum.libs.strings.fuzzy_match` which wraps `difflib.SequenceMatcher` for string similarity comparison.

### Vector DB Filtering Constraints

**Important:** Many vector databases cannot perform pure metadata queries (like `SELECT * WHERE metadata_x = Y`). They require a query string for vector similarity search, even when filtering by metadata.

This affects our retrieval strategy. The original "Path 1" above assumes we can do a pure metadata lookup by `criterion_question_hash`. If your vector DB requires a query string, the approach must be adjusted based on whether it uses **pre-filtering** or **post-filtering**.

#### Pre-Filtering vs Post-Filtering

| Strategy | How It Works | Impact on Retrieval |
|----------|--------------|---------------------|
| **Pre-filtering** | Filter applied BEFORE vector search. Search only considers documents matching the filter. | Safe. Hash-matched follow-ups will always be returned regardless of similarity score. |
| **Post-filtering** | Vector search runs first (top_k by similarity), THEN filter applied to results. | Risky. Low-similarity follow-ups may not make top_k and get excluded. |

**Visual comparison:**

```
PRE-FILTERING (Safe):
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ All Documents   │ ──▶ │ Filter: hash=X  │ ──▶ │ Vector Search   │
│ (1000 docs)     │     │ (3 docs match)  │     │ (rank 3 docs)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
Result: All 3 hash-matched docs returned, ranked by similarity

POST-FILTERING (Risky):
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ All Documents   │ ──▶ │ Vector Search   │ ──▶ │ Filter: hash=X  │
│ (1000 docs)     │     │ (top 20 by sim) │     │ (maybe 0-1 match)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
Result: Hash-matched docs may be excluded if they didn't rank in top 20
```

#### Our Vector DB: Weaviate (Pre-Filtering)

Our vector DB (Vellum) uses Weaviate under the hood, which implements **pre-filtering**. From [Weaviate documentation](https://weaviate.io/developers/weaviate/concepts/filtering):

> Pre-Filtering describes an approach where eligible candidates are determined before a vector search is started. The vector search then only considers candidates that are present on the "allow" list.

This means our retrieval strategy is safe:

```python
# This query will return ALL follow-ups matching the hash,
# ranked by similarity to criterion_question_text within that filtered set
follow_ups = await vector_search(
    query=criterion_question_text,
    filter={
        "criterion_question_hash": criterion_question_hash,
        "vendor_id": vendor_id,
        "source_type": "follow_up_response",
    },
    top_k=MAX_FOLLOWUP_ROUNDS,
)
```

Even if a follow-up has low semantic similarity (terse answer to modified question), it **will still be returned** because pre-filtering ensures all hash-matched documents are in the candidate set.

#### Strategy for Post-Filtering Vector DBs

If your vector DB uses post-filtering, you need compensating strategies:

**Option 1: Include criterion text in embedded content**

Change the embedded content from:
```
"Question: {modified_question} Answer: {terse_answer}"
```
To:
```
"Criterion: {original_criterion} Question: {modified_question} Answer: {terse_answer}"
```

This ensures high similarity when querying with criterion text, regardless of question/answer content.

**Option 2: Over-fetch and filter in application code**

```python
# Fetch more than needed with broad filter
all_results = await vector_search(
    query=criterion_question_text,
    filter={"vendor_id": vendor_id},  # Broad filter only
    top_k=100,  # Much higher than needed
)

# Filter and prioritize in code
hash_matched = [r for r in all_results
    if r.source_type == "follow_up_response"
    and r.criterion_question_hash == criterion_question_hash]

semantic_matched = [r for r in all_results
    if r.source_type == "follow_up_response"
    and r.criterion_question_hash != criterion_question_hash]

documents = [r for r in all_results
    if r.source_type != "follow_up_response"]

# Prioritize hash-matched, then semantic, then documents
```

**Option 3: External lookup table**

Maintain a separate database (Redis, Postgres) mapping `(vendor_id, criterion_question_hash) → document_ids`, then fetch documents by ID.

**Option 4: Separate index for follow-ups**

Store follow-ups in a dedicated index/collection so they don't compete with the larger document corpus.

**Recommendation for post-filtering DBs:** Combine Options 1 + 2 for near-deterministic behavior without additional infrastructure.

**3. Prompt Structure**

```
You are a security assessor evaluating vendor compliance.

**Source 1: Direct Vendor Responses (HIGHEST PRIORITY)**
The vendor provided these responses across multiple follow-up rounds.
Responses are shown in reverse chronological order (most recent first).

IMPORTANT: If responses from different rounds conflict, prefer the MOST RECENT
response as it represents the vendor's latest position on this topic.

{follow_up_responses_formatted}

**Source 2: General Documentation**
Supporting evidence from vendor policies, SOC2 reports, and other documents.

{supporting_documents}

**Criterion to Evaluate:**
{criterion_question_text}

Assess whether this criterion is MET, NOT_MET, or INCONCLUSIVE.
If you observe contradictions between follow-up rounds, note this in your reasoning.
```

**4. Formatting Follow-up Responses**

```python
def format_follow_up_responses(responses: list[FollowUpResponse]) -> str:
    """Format multiple rounds of follow-ups with clear precedence markers."""
    if not responses:
        return "No direct vendor responses available for this criterion."

    formatted_parts = []
    for i, response in enumerate(responses):  # Already sorted: newest first
        recency_label = "MOST RECENT - " if i == 0 else ""
        # Use metadata fields for clean formatting (not the embedded content)
        formatted_parts.append(f"""
[{recency_label}ROUND {response.round_number} - {response.timestamp}]
Question: {response.metadata.question_text}
Vendor Response: {response.metadata.answer_text}
""".strip())

    return "\n\n---\n\n".join(formatted_parts)
```

### Walkthrough: Multi-Round Example

**Criterion:** "Does the vendor encrypt data at rest using AES-256?"

---

**ROUND 1: Initial Assessment**

*Assessment runs against vendor's SOC2 and policies.*

SOC2 excerpt: "Data is encrypted at rest using industry-standard encryption."

**Result: INCONCLUSIVE** - SOC2 mentions encryption but doesn't specify AES-256.

*System auto-generates follow-up. Customer sends it unmodified.*

---

**ROUND 2: First Follow-up**

Question (unmodified): "Does the vendor encrypt data at rest using AES-256?"

Vendor Response R1: "Yes, we use AES-256 for all data at rest."

*Response R1 stored with:*
```python
{
    "content": "Question: Does the vendor encrypt data at rest using AES-256? Answer: Yes, we use AES-256 for all data at rest.",
    "metadata": {
        "source_type": "follow_up_response",
        "criterion_question_hash": "a1b2c3d4e5f6...",
        "original_criterion_question_text": "Does the vendor encrypt data at rest using AES-256?",
        "question_text": "Does the vendor encrypt data at rest using AES-256?",
        "answer_text": "Yes, we use AES-256 for all data at rest.",
        "round_number": 1,
        ...
    }
}
```

*Re-assessment runs. Retrieval returns:*
- Follow-ups: [R1]
- Documents: [SOC2 excerpt]

**Result: MET** - Vendor explicitly confirmed AES-256.

*But customer wants more detail. They modify the follow-up and send another round.*

---

**ROUND 3: Second Follow-up**

Question (modified): "Please provide documentation or screenshots showing your AES-256 encryption configuration."

Vendor Response R2: "Attached is our AWS KMS configuration showing AES-256-GCM. All S3 buckets use SSE-KMS with this key."

*Response R2 stored with:*
```python
{
    "content": "Question: Please provide documentation or screenshots showing your AES-256 encryption configuration. Answer: Attached is our AWS KMS configuration showing AES-256-GCM. All S3 buckets use SSE-KMS with this key.",
    "metadata": {
        "source_type": "follow_up_response",
        "criterion_question_hash": "a1b2c3d4e5f6...",  # Same hash - criterion unchanged
        "original_criterion_question_text": "Does the vendor encrypt data at rest using AES-256?",
        "question_text": "Please provide documentation or screenshots showing your AES-256 encryption configuration.",
        "answer_text": "Attached is our AWS KMS configuration showing AES-256-GCM. All S3 buckets use SSE-KMS with this key.",
        "round_number": 2,
        ...
    }
}
```

*Re-assessment runs. Retrieval returns:*
- Follow-ups: [R2, R1] (ordered by round DESC)
- Documents: [SOC2 excerpt]

*LLM prompt receives:*

```
**Source 1: Direct Vendor Responses (HIGHEST PRIORITY)**

[MOST RECENT - ROUND 2 - 2024-01-15]
Question: Please provide documentation or screenshots showing your AES-256 encryption configuration.
Vendor Response: Attached is our AWS KMS configuration showing AES-256-GCM. All S3 buckets use SSE-KMS with this key.

---

[ROUND 1 - 2024-01-10]
Question: Does the vendor encrypt data at rest using AES-256?
Vendor Response: Yes, we use AES-256 for all data at rest.

**Source 2: General Documentation**

SOC2 excerpt: "Data is encrypted at rest using industry-standard encryption."

**Criterion to Evaluate:**
Does the vendor encrypt data at rest using AES-256?
```

**Result: MET** - Round 2 provides concrete evidence (KMS config) supporting Round 1's claim.

---

**ROUND 4+ (Degenerate Case)**

If customer continues sending follow-ups:

- Round 3 response stored with `round_number: 3`
- Round 4 response stored with `round_number: 4`
- ...

*Retrieval with `MAX_FOLLOWUP_ROUNDS = 3` returns:*
- [R4, R3, R2] - only the 3 most recent rounds
- R1 is excluded (too old)

This bounds token usage and keeps context focused on the most relevant recent exchanges.

### Handling Contradictions Across Rounds

If vendor contradicts themselves:

```
[MOST RECENT - ROUND 3 - 2024-01-20]
Question: Can you clarify your encryption standard?
Vendor Response: We actually use AES-128 for most data, AES-256 only for PII.

---

[ROUND 2 - 2024-01-15]
Question: Please provide documentation showing AES-256 configuration.
Vendor Response: All S3 buckets use AES-256-GCM.

---

[ROUND 1 - 2024-01-10]
Question: Does the vendor encrypt data at rest using AES-256?
Vendor Response: Yes, we use AES-256 for all data at rest.
```

The LLM, instructed to prefer the most recent response, would assess:

**Result: NOT_MET** - Most recent clarification (Round 3) indicates AES-256 is only used for PII, not all data at rest. Notes contradiction with earlier claims.

---

## Bulk Ingestion API

When the vendor submits a follow-up questionnaire, ingest all responses in a single API call rather than individual calls per response.

### API Design

```
POST /api/v1/vrm/followup-questionnaire/index
```

**Request:**

```python
{
    "vendor_id": "vendor_123",
    "round_number": 2,
    "timestamp": "2024-01-15T10:30:00Z",
    "responses": [
        {
            # Criterion-linked response
            "criterion_question_text": "Does the vendor encrypt data at rest using AES-256?",
            "question_text": "Please describe your encryption practices",
            "answer_text": "We use AES-256 for all data at rest with AWS KMS."
        },
        {
            # Ad-hoc question (no criterion)
            "criterion_question_text": null,  # or omitted
            "question_text": "Do you have a business continuity plan?",
            "answer_text": "Yes, we have a BCP reviewed annually."
        }
    ]
}
```

**Response:**

```python
{
    "indexed_count": 2,
    "round_number": 2,
    "vendor_id": "vendor_123"
}
```

### Internal Processing

```python
async def index_followup_questionnaire(request: FollowupQuestionnaireRequest) -> IndexResult:
    chunks_to_index = []

    for response in request.responses:
        criterion_question_text = response.criterion_question_text or ""

        # content_hash for uniqueness (criterion + question)
        content_hash = compute_content_hash(criterion_question_text, response.question_text)

        # criterion_question_hash for retrieval filtering (None for ad-hoc)
        criterion_question_hash = compute_criterion_question_hash(criterion_question_text)

        chunks_to_index.append({
            "content": format_embedding_content(response.question_text, response.answer_text),
            "external_id": f"followup-{request.vendor_id}-{content_hash}-round{request.round_number}",
            "metadata": {
                "source_type": "follow_up_response",
                "content_hash": content_hash,
                "criterion_question_hash": criterion_question_hash,  # None for ad-hoc
                "original_criterion_question_text": criterion_question_text,
                "question_text": response.question_text,
                "answer_text": response.answer_text,
                "vendor_id": request.vendor_id,
                "round_number": request.round_number,
                "timestamp": request.timestamp,
            }
        })

    # Bulk index to vector DB (single call or parallel internal calls)
    await vector_db.bulk_upsert(
        chunks=chunks_to_index,
        namespace=f"vendor_{request.vendor_id}"
    )

    return IndexResult(
        indexed_count=len(chunks_to_index),
        round_number=request.round_number,
        vendor_id=request.vendor_id,
    )
```

### Design Considerations

| Consideration | Recommendation |
|---------------|----------------|
| **Failure mode** | All-or-nothing (atomic) - if one fails, rollback all |
| **Payload size limit** | Max 100 responses per call (reasonable for questionnaires) |
| **Idempotency** | Re-indexing same round should upsert, not duplicate. Key on `(vendor_id, content_hash, round_number)` where `content_hash = hash(criterion_question_text \|\| question_text)` |
| **Timeout** | Set generous timeout (30s+) for large questionnaires |

### Why Bulk vs Individual Calls

| Aspect | Bulk Endpoint | Individual Calls |
|--------|---------------|------------------|
| HTTP round-trips | 1 | N (one per response) |
| Atomicity | Easy (all-or-nothing) | Hard (partial failures) |
| Client complexity | Simple | Must handle parallelization |
| Internal optimization | Can batch vector DB calls | Each call is independent |


---

## Implementation Checklist

**Data Model:**
- [ ] Implement `compute_content_hash(criterion_question_text, question_text)` for external_id uniqueness
- [ ] Implement `compute_criterion_question_hash(criterion_question_text)` for retrieval filtering (returns None for empty)
- [ ] Implement `format_embedding_content()` to create "Question: ... Answer: ..." content
- [ ] Add `content_hash` metadata field (criterion + question hash)
- [ ] Add `criterion_question_hash` metadata field (criterion only, None for ad-hoc)
- [ ] Add `original_criterion_question_text` metadata field for auditability (empty for ad-hoc)
- [ ] Add `question_text` and `answer_text` metadata fields (raw values for display)
- [ ] Add `round_number` metadata field for multi-round tracking
- [ ] Support ad-hoc questions (criterion_question_text is optional/nullable)

**Bulk Ingestion API:**
- [ ] Create `POST /api/v1/vrm/followup-questionnaire/index` endpoint
- [ ] Make `criterion_question_text` optional in API model
- [ ] Implement atomic (all-or-nothing) failure handling
- [ ] Implement idempotent upsert keyed on `(vendor_id, content_hash, round_number)`
- [ ] Add payload size validation (max 100 responses)
- [ ] Validate unique `(criterion_question_text, question_text)` pairs within batch

**Retrieval:**
- [ ] Implement hybrid retrieval: hash-based filter (Path 1) + semantic search fallback (Path 2)
- [ ] Implement `merge_and_dedupe()` to combine hash-matched and semantic results
- [ ] Implement round-ordered retrieval with configurable `MAX_FOLLOWUP_ROUNDS`

**Prompt Engineering:**
- [ ] Structure prompts with explicit precedence hierarchy (most recent first)
- [ ] Add provenance tracking (source type, timestamp, round number)
- [ ] Handle conflict detection in assessment logic

**Testing:**
- [ ] Modified question uses completely different terminology
- [ ] Vendor answer is extremely short (1-2 words)
- [ ] Vendor answer contradicts existing documentation
- [ ] Multiple rounds (3+) of follow-ups for same criterion
- [ ] Vendor contradicts themselves across rounds
- [ ] Many rounds exceed `MAX_FOLLOWUP_ROUNDS` threshold
- [ ] Criterion text edited (hash changes) - verify semantic fallback works
- [ ] Minor typo fix in criterion - verify old follow-ups still surface via semantic search
- [ ] Bulk API: partial failure handling (verify rollback)
- [ ] Bulk API: idempotent re-indexing (no duplicates)

---

## Summary Decision Matrix

| Constraint | Recommended Approach |
|------------|---------------------|
| Minimal code changes | Composite Embedding (Option B) |
| Bounded follow-ups (<20) | Context Injection (Option A) |
| Need flexibility for many criteria | Content-Based Hashing + Hybrid Retrieval (Recommended) |
| Want pure vector search | Multi-Vector Embedding (Option C) |
| Complex question modifications | LLM-Assisted Mapping (Option E) |

**Default recommendation:** Content-Based Hashing + Hybrid Retrieval + Bulk Ingestion API

This provides:
- **Content-based linkage** via criterion text hash (resilient to criterion edits)
- **Structured embedding content** ("Question: ... Answer: ...") with raw metadata for display
- Deterministic retrieval (no semantic drift risk)
- **Semantic search fallback** for edge cases (typo fixes, minor edits)
- Clear precedence via prompt structure
- Flexibility to still use semantic search for supporting context
- Preserved provenance and auditability
- **Multi-round support** with bounded accumulation (configurable `MAX_FOLLOWUP_ROUNDS`)
- **Bulk ingestion API** for atomic, idempotent questionnaire indexing
- Graceful handling of degenerate cases (infinite follow-up loops)
