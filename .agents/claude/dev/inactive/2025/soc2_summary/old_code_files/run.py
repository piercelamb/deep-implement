import time
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any

from vellum import FunctionDefinition, SearchWeightsRequest, SearchResultMergingRequest
from vellum.workflows.nodes.displayable.bases.types import SearchFilters

from ai_services.shared.runtime.context import ExecutionSource
from ai_services.shared.schema.artifact.metadata import ArtifactType
from ai_services.shared.schema.evidence.schema import VellumDocExcerpt
from ai_services.shared.utils import dumps
from ai_services.shared.vellum.api.documents import retrieve
from ai_services.shared.vellum.search import parse_vellum_retrieval
from ai_services.vellum.support.artifact_intelligence_q2_fy26.soc2_summary.prompts.validate_soc2.prompt import IsSOC2, \
    SOC2Classification

DENSE_PROPORTION = 0.4  # We favor sparse because these queries are very keyword heavy
SPARSE_PROPORTION = 0.6  # We favor sparse because these queries are very keyword heavy
TOP_FIRST_STAGE_N = 20 # Taken from original SOC2 Summary


@dataclass(frozen=True, slots=True, kw_only=True)
class Soc2SummaryContext:
    tenant_id: str
    tenant_name: str
    vendor_id: str
    vendor_name: str
    source: ExecutionSource
    artifact_type: ArtifactType | None
    document_index_id: str
    document_id: str

    @classmethod
    def from_invoke(cls, workflow_input: dict) -> "Soc2SummaryContext":
        artifact_type = workflow_input.get("artifact_type")
        if artifact_type is not None:
            artifact_type = ArtifactType(artifact_type)
        return cls(
            tenant_id=workflow_input["tenant_id"],
            tenant_name=workflow_input["tenant_name"],
            vendor_id=workflow_input["vendor_id"],
            vendor_name=workflow_input["vendor_name"],
            source=ExecutionSource(workflow_input["source"]),
            artifact_type=artifact_type,
            document_index_id=workflow_input["document_index_id"],
            document_id=workflow_input["document_id"],
        )
    def to_log(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def execute_queries(
    *,
    queries: list[str],
    document_index_id: str,
    document_id: str,
    client: Any,
    logger: Any,
    category_name: str,
    dense_proportion: float = DENSE_PROPORTION,
    sparse_proportion: float = SPARSE_PROPORTION,
    limit: int = TOP_FIRST_STAGE_N,
    top_n_per_query: int | None = None,
) -> list[list[VellumDocExcerpt]]:
    """
    Execute vector searches for a list of queries and return results organized by query.

    This function is designed to be called by individual retrieval nodes that each
    handle one category of queries (e.g., overview, exceptions). Each node can run
    concurrently, improving overall workflow performance.

    Args:
        queries: List of query strings to execute
        document_index_id: ID of the Vellum document index to search
        document_id: External ID of the specific document to filter results to
        client: Vellum client instance
        logger: Logger for tracking search execution
        category_name: Name of the category for logging (e.g., "overview", "exceptions")
        dense_proportion: Weight for semantic similarity search (default: 0.6)
        sparse_proportion: Weight for keyword search (default: 0.4)
        limit: Maximum results to retrieve from Vellum per query (default: 20)
        top_n_per_query: Maximum results to keep per query after retrieval. If None, keeps all.
            Use this to get consistent result merging by fetching more results (high limit) but
            only using the top N best results (e.g., limit=20, top_n_per_query=5)

    Returns:
        List of excerpt lists, one per query. Deduplication happens later in merge_query_excerpts.
    """
    weights = SearchWeightsRequest(semantic_similarity=dense_proportion, keywords=sparse_proportion)
    result_merging = SearchResultMergingRequest(enabled=True)
    filters = SearchFilters(external_ids=[document_id])

    excerpts_by_query: list[list[VellumDocExcerpt]] = []

    logger.info(f"Executing {category_name} searches", extra={"num_queries": len(queries)})

    for query_idx, query in enumerate(queries):
        start_time = time.perf_counter()

        resp = retrieve(
            query=query,
            document_index_id=document_index_id,
            limit=limit,
            weights=weights,
            result_merging=result_merging,
            filters=filters,
            client=client,
            logger=logger,
            logger_extra={"category": category_name, "query_idx": query_idx},
        )

        logger.info(
            f"Retrieved excerpts for {category_name} query {query_idx + 1}",
            extra={
                "num_excerpts": len(resp.results),
                "elapsed": time.perf_counter() - start_time,
                "category": category_name,
            },
        )

        query_excerpts = parse_vellum_retrieval(
            search_results=resp.results,
            document_ids=[document_id],
        )

        # Apply top_n_per_query limit if specified (results are already sorted by score)
        if top_n_per_query is not None:
            query_excerpts = query_excerpts[:top_n_per_query]

        excerpts_by_query.append(query_excerpts)

    total_excerpts = sum(len(excerpts) for excerpts in excerpts_by_query)
    logger.info(
        f"Completed {category_name} searches",
        extra={"total_excerpts": total_excerpts},
    )

    return excerpts_by_query


def merge_query_excerpts(
    *,
    excerpts_by_query: list[list[VellumDocExcerpt]],
    max_length: int,
) -> list[VellumDocExcerpt]:
    """
    Merge excerpts from multiple queries within the same category into a single list.

    Ensures fair representation across queries while respecting the maximum length constraint.
    Each query gets an equal quota of slots. If a query has fewer excerpts than its quota,
    the unused slots are allocated to a pool filled by the highest-scoring remaining excerpts.

    Args:
        excerpts_by_query: List of excerpt lists, one per query.
                          Each inner list should already be deduplicated and sorted by score descending.
        max_length: Maximum number of excerpts to return

    Returns:
        List of excerpts, length <= max_length, sorted by score descending
    """
    if not excerpts_by_query:
        return []

    num_queries = len(excerpts_by_query)
    per_query_quota = max_length // num_queries

    selected_excerpts: list[VellumDocExcerpt] = []
    pool_excerpts: list[VellumDocExcerpt] = []
    unused_slots = 0

    for excerpts in excerpts_by_query:
        sorted_excerpts = sorted(excerpts, key=lambda e: e.first_stage_score, reverse=True)

        query_selected = sorted_excerpts[:per_query_quota]
        query_remaining = sorted_excerpts[per_query_quota:]

        selected_excerpts.extend(query_selected)
        pool_excerpts.extend(query_remaining)

        # Track unused quota slots
        if len(query_selected) < per_query_quota:
            unused_slots += per_query_quota - len(query_selected)

    # Fill unused slots from pool (highest scores first)
    if unused_slots > 0 and pool_excerpts:
        pool_sorted = sorted(pool_excerpts, key=lambda e: e.first_stage_score, reverse=True)
        selected_excerpts.extend(pool_sorted[:unused_slots])

    # Deduplicate by content_hash, keeping highest score
    seen_hashes: dict[str, VellumDocExcerpt] = {}
    for excerpt in selected_excerpts:
        if excerpt.content_hash not in seen_hashes:
            seen_hashes[excerpt.content_hash] = excerpt
        else:
            existing = seen_hashes[excerpt.content_hash]
            if excerpt.first_stage_score > existing.first_stage_score:
                seen_hashes[excerpt.content_hash] = excerpt

    deduplicated = list(seen_hashes.values())

    # If deduplication freed space, backfill from pool
    space_available = max_length - len(deduplicated)

    if space_available > 0 and pool_excerpts:
        selected_hashes = set(seen_hashes.keys())
        available_pool = [e for e in pool_excerpts if e.content_hash not in selected_hashes]

        if available_pool:
            pool_sorted = sorted(available_pool, key=lambda e: e.first_stage_score, reverse=True)

            for excerpt in pool_sorted[:space_available]:
                deduplicated.append(excerpt)

    result = sorted(deduplicated, key=lambda e: e.first_stage_score, reverse=True)
    return result[:max_length]


def to_llm_ready_xml(validation_chunks: list[VellumDocExcerpt]) -> str:
    chunks_str = ""
    for i, r in enumerate(validation_chunks, start=1):
        content_with_metadata = f"Filename: {r.metadata['FILENAME']}\n{r.content}"
        chunk = f"<index_{i}>\n" + f"{content_with_metadata}\n" + f"</index_{i}>\n"
        chunks_str = chunks_str + chunk
    return chunks_str

def get_dynamic_structured_out(
    validation_chunks: list[VellumDocExcerpt],
) -> list[FunctionDefinition]:
    """
    We build the structured output def below since we need to pass runtime context into it.
    """
    excerpt_indexes = [str(i) for i in range(1, len(validation_chunks) + 1)]
    return IsSOC2.json_to_function_defn(
        forced=True,
        strict=True,
        SOC2_TYPES=[e for e in SOC2Classification],
        EXCERPT_INDICES=excerpt_indexes,
    )