import time
from typing import Optional

from vellum import SearchWeightsRequest, SearchResultMergingRequest, SearchResponse
from vellum.workflows.nodes import BaseNode, ConditionalNode
from vellum.workflows.nodes.displayable.bases.types import SearchFilters
from vellum.workflows.ports import Port
from vellum.workflows.references import LazyReference

from ai_services.shared.schema.artifact.metadata import ArtifactType
from ai_services.shared.schema.evidence.schema import VellumDocExcerpt
from ai_services.shared.vellum.api.documents import retrieve
from ai_services.shared.vellum.search import parse_vellum_retrieval
from ai_services.vellum.libs.logger.json_logger import logger
from ai_services.vellum.libs.vellum_tools import InjectSlack, vellum_trace, get_node_inputs
from ai_services.vellum.support.artifact_intelligence_q2_fy26.soc2_summary.run import Soc2SummaryContext, \
    to_llm_ready_xml, get_dynamic_structured_out, DENSE_PROPORTION, SPARSE_PROPORTION, \
    TOP_FIRST_STAGE_N
from ..inputs import Inputs

log = logger(__name__)

SOC2_VALIDATION_QUERY = "SOC or SOC 2 Test Results" # Taken from original SOC2 Summary

class ParseAndValidate(BaseNode, metaclass=InjectSlack):
    tenant_id = Inputs.tenant_id
    tenant_name = Inputs.tenant_name
    vendor_id = Inputs.vendor_id
    vendor_name = Inputs.vendor_name
    source = Inputs.source
    artifact_type = Inputs.artifact_type
    document_index_id = Inputs.document_index_id
    document_id = Inputs.document_id

    class Outputs(BaseNode.Outputs):
        ctx: Soc2SummaryContext
        artifact_type: Optional[ArtifactType]
        validation_excerpts: list[VellumDocExcerpt]
        validation_context: Optional[str]
        structured_output: Optional[str]
        logs: str

    class Ports(ConditionalNode.Ports):
        process_soc2 = Port.on_if(LazyReference("ParseAndValidate.Outputs.artifact_type").equals(ArtifactType.SOC_2_TYPE_2))
        validate_soc2 = Port.on_if(LazyReference("ParseAndValidate.Outputs.artifact_type").is_null())
        invalid_artifact_type = Port.on_else()

    def run(self) -> BaseNode.Outputs:
        with vellum_trace(self.source, self) as (out_buf, err_buf, exe_id, deploy_id, run_type):
            ctx = Soc2SummaryContext.from_invoke(get_node_inputs(self))
            log.info("Validating SOC2 Summary inputs", extra=ctx.to_log())
            validation_chunks, validation_context, structured_out = [], None, None
            if ctx.artifact_type is None:
                log.info("Detected an empty artifact_type, retrieving sources for validation")
                weights = SearchWeightsRequest(semantic_similarity=DENSE_PROPORTION, keywords=SPARSE_PROPORTION)
                result_merging = SearchResultMergingRequest(enabled=True)
                filters = SearchFilters(
                    external_ids=[ctx.document_id]
                )
                first_stage_start = time.perf_counter()
                resp: SearchResponse = retrieve(
                    query=SOC2_VALIDATION_QUERY,
                    document_index_id=ctx.document_index_id,
                    limit=TOP_FIRST_STAGE_N,
                    weights=weights,
                    result_merging=result_merging,
                    filters=filters,
                    client=self._context.vellum_client,
                    logger=log
                )
                log.info(
                    "Retrieved excerpts",
                    extra={"num_excerpts": len(resp.results), "elapsed": time.perf_counter() - first_stage_start},
                )
                validation_chunks = parse_vellum_retrieval(
                    search_results=resp.results,
                    document_ids=[ctx.document_id]
                )
                validation_context = to_llm_ready_xml(validation_chunks)
                structured_out = get_dynamic_structured_out(validation_chunks)
            return self.Outputs(
                ctx=ctx,
                artifact_type=ctx.artifact_type,
                validation_excerpts=validation_chunks,
                validation_context=validation_context,
                structured_output=structured_out,
                logs=err_buf.getvalue(),
            )