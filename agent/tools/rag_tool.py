"""Track A — RAG retrieval tool (Vertex AI Search).

The agent uses this to semantically search the handbook corpus you ingested into
a Vertex AI Search data store (see rag/). It returns grounded context + citations.

Prerequisite: complete rag/README.md (terraform apply, ingest, verify) first.
"""
from typing import Any
from google.api_core.client_options import ClientOptions
from .. import config

try:
    from google.cloud import discoveryengine_v1 as discoveryengine
except ImportError:
    discoveryengine = None


def search_policy_docs(query: str) -> dict[str, Any]:
    """Semantic search over the HR policy corpus in Vertex AI Search.

    Args:
        query: a natural-language policy question or search phrase.

    Returns:
        {"grounded_context": str, "citations": [str, ...]}
    """
    if not discoveryengine:
        return {
            "grounded_context": "Error: google-cloud-discoveryengine is not installed.",
            "citations": [],
        }

    project = config.GOOGLE_CLOUD_PROJECT
    location = config.VERTEX_AI_SEARCH_LOCATION or "global"
    engine_id = config.VERTEX_AI_SEARCH_ENGINE_ID

    if not project or not engine_id:
        return {
            "grounded_context": "Error: GOOGLE_CLOUD_PROJECT or VERTEX_AI_SEARCH_ENGINE_ID is not configured.",
            "citations": [],
        }

    client_options = (
        ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
        if location != "global"
        else None
    )
    client = discoveryengine.SearchServiceClient(client_options=client_options)
    serving_config = (
        f"projects/{project}/locations/{location}/collections/default_collection"
        f"/engines/{engine_id}/servingConfigs/default_search"
    )
    content_spec = discoveryengine.SearchRequest.ContentSearchSpec(
        extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
            max_extractive_answer_count=3,
            max_extractive_segment_count=3,
        )
    )
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=3,
        content_search_spec=content_spec,
    )

    try:
        response = client.search(request)
    except Exception as e:
        return {
            "grounded_context": f"Search error: {e}",
            "citations": [],
        }

    contexts = []
    citations = []
    for result in response.results:
        d = result.document.derived_struct_data
        title = d.get("title", "")
        link = d.get("link", "")
        if link and link not in citations:
            citations.append(link)

        # Extract segments / snippets
        segments = []
        extractive_segments = d.get("extractive_segments", [])
        if isinstance(extractive_segments, list):
            for seg in extractive_segments:
                if isinstance(seg, dict) and "content" in seg:
                    segments.append(seg["content"])
                elif isinstance(seg, str):
                    segments.append(seg)
        snippets = d.get("snippets", [])
        if isinstance(snippets, list):
            for snip in snippets:
                if isinstance(snip, dict) and "snippet" in snip:
                    segments.append(snip["snippet"])
                elif isinstance(snip, str):
                    segments.append(snip)

        context_body = "\n".join(segments) if segments else ""
        if title or context_body:
            header = f"### {title}" if title else ""
            contexts.append(f"{header}\n{context_body}".strip())

    grounded_context = "\n\n".join(contexts) if contexts else "No relevant policy documents found."
    return {
        "grounded_context": grounded_context,
        "citations": citations,
    }
