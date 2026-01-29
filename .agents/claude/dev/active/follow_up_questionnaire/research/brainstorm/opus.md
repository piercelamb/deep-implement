VRM Agent Follow-up Questionnaire Retrieval: Analysis & Brainstorm

  Scenario A: Unmodified Follow-up Questionnaire

  You're partially right, but I'd add some caveats:

  Why it should work:
  - The follow-up question is semantically identical to the criterion
  - Vector search should return high similarity scores

  Why it might not be bulletproof:
  1. Vendor response quality variance - If the vendor gives a terse or tangential response, the semantic similarity between the criterion and their answer may be lower than similarity to the original comprehensive SOC2/policy documents
  2. Chunking effects - How you chunk the follow-up response matters. A short response might get less embedding "weight" than a dense policy paragraph
  3. Document volume - If there are hundreds of policy chunks that are thematically similar, they could crowd out the follow-up response in top_k

  My take: It's a reasonable assumption for the happy path, but relying purely on semantic similarity is fragile.

  ---
  Scenario B: Modified Follow-up Questionnaire (The Hard Problem)

  You've correctly identified the core issue: semantic drift between the original criterion and the modified question breaks the implicit link.

  Concrete Example

  Original Criterion: "Does the vendor encrypt data at rest using AES-256?"

  User-Modified Question: "Please describe your storage security practices
  and any relevant certifications."

  Vendor Response: "We use Google Cloud Storage with default encryption
  and are ISO 27001 certified..."

  When re-assessing the original criterion, the vendor's response about "storage security practices" and "ISO 27001" may not semantically match "AES-256 encryption at rest" well enough to surface in top_k.

  ---
  Proposed Solutions

  1. Explicit Criterion Linkage (Recommended)

  Store follow-up responses with explicit metadata linking them to the original criterion ID:

  # When storing follow-up response in vector DB
  {
      "content": vendor_response_text,
      "metadata": {
          "source_type": "follow_up_response",
          "original_criterion_id": "criterion_123",
          "modified_question": "Please describe your storage...",
          "assessment_id": "...",
      }
  }

  During retrieval, use hybrid retrieval:
  1. Vector search for top_k relevant chunks
  2. Always fetch follow-up responses where original_criterion_id matches the criterion being assessed
  3. Merge and dedupe

  Pros: Guarantees follow-up responses are seen regardless of semantic similarity
  Cons: Requires metadata filtering capability in your vector DB

  ---
  2. Dual-Path Retrieval

  Don't rely solely on vector search for follow-up responses:

  async def retrieve_for_assessment(criterion_id: str, query: str) -> list[Document]:
      # Path 1: Semantic search against all documents
      vector_results = await vector_db.search(query, top_k=10)

      # Path 2: Direct lookup of follow-up responses for this criterion
      follow_up_responses = await db.get_follow_up_responses(criterion_id)

      # Merge with follow-up responses taking precedence
      return merge_with_precedence(follow_up_responses, vector_results)

  Pros: Clean separation of concerns, guaranteed retrieval
  Cons: Requires maintaining the criterion→response mapping outside vector DB

  ---
  3. Multi-Vector Embedding at Ingest

  When storing a follow-up response, embed it multiple ways:

  # Store the same response content with multiple embedding vectors
  chunks = [
      {
          "content": vendor_response,
          "embedding": embed(vendor_response),  # Natural embedding
      },
      {
          "content": vendor_response,
          "embedding": embed(original_criterion),  # Criterion-aligned embedding
      },
      {
          "content": vendor_response,
          "embedding": embed(modified_question),  # Question-aligned embedding
      }
  ]

  This creates multiple "entry points" to the same content.

  Pros: Works with pure vector search, no metadata filtering needed
  Cons: Storage bloat, potential for duplicate retrieval

  ---
  4. Context Injection (Simplest)

  Bypass vector search entirely for follow-up responses:

  async def assess_criterion(criterion: Criterion, assessment_id: str):
      # Always include follow-up response if it exists
      follow_up = await db.get_follow_up_response(assessment_id, criterion.id)

      # Vector search for supporting documents
      documents = await vector_search(criterion.text, top_k=8)

      # Inject follow-up with explicit framing
      context = build_context(
          follow_up_response=follow_up,  # Presented first with special framing
          supporting_documents=documents,
      )

      return await llm.assess(criterion, context)

  Pros: Dead simple, guaranteed to work, clear precedence
  Cons: Doesn't scale if there are many follow-up responses (token limits)

  ---
  5. LLM-Assisted Mapping at Ingest

  When the user modifies a question and vendor responds, use an LLM to map the response back to relevant original criteria:

  async def ingest_follow_up_response(
      modified_question: str,
      vendor_response: str,
      all_criteria: list[Criterion],
  ):
      # Ask LLM: "Which of these criteria does this response address?"
      relevant_criteria = await llm.identify_relevant_criteria(
          question=modified_question,
          response=vendor_response,
          criteria=all_criteria,
      )

      # Store with multi-criterion linkage
      await vector_db.store(
          content=vendor_response,
          metadata={"addresses_criteria": [c.id for c in relevant_criteria]}
      )

  Pros: Handles semantic drift intelligently, one modified question might address multiple criteria
  Cons: Adds LLM call during ingest, potential for mapping errors

  ---
  My Recommendation

  Use approach #2 (Dual-Path Retrieval) or #4 (Context Injection) depending on your constraints:

  - If follow-up responses per assessment are bounded (say, <20): Use Context Injection. It's simple, deterministic, and the "precedence" requirement is trivially satisfied by prompt ordering.
  - If you need to scale to many follow-ups or want cleaner architecture: Use Dual-Path Retrieval with explicit criterion linkage stored in your relational DB alongside the follow-up questionnaire data.

  The key insight is: don't rely on semantic similarity for data that has an explicit structural relationship. You know which criterion generated which follow-up question—preserve that relationship and use it at retrieval time.

  ---
  Additional Consideration: Precedence Semantics

  You mentioned follow-up data should "take precedence." This is a prompt engineering concern as much as a retrieval concern:

  When assessing this criterion, note that the vendor has provided
  a direct response to a follow-up question about this topic.
  This response should be weighted more heavily than general
  policy documents when determining the assessment outcome.

  VENDOR'S DIRECT RESPONSE:
  {follow_up_response}

  SUPPORTING DOCUMENTATION:
  {vector_search_results}

  Explicit framing in the prompt ensures the LLM understands the precedence hierarchy.

  ---
  Want me to dig into any of these approaches in more detail, or explore how they'd integrate with your existing assessment workflow?