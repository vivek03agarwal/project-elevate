"""Track B — OKF retrieval tools.

The agent uses these to *navigate* the Open Knowledge Format bundle in knowledge/:
first list what concepts exist, then read the most relevant one. No vector DB.
"""
import os
import re
import yaml

from .. import config  # config.KNOWLEDGE_DIR points at the knowledge/ bundle

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
RESERVED = {"index.md", "log.md"}


def _parse_file(filepath: str):
    """Parse YAML frontmatter and body from a markdown file."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    body = m.group(2)
    return data, body


def list_concepts() -> dict:
    """List the policy concepts available in the OKF bundle.

    Returns:
        {"concepts": [{"id": str, "title": str, "description": str}, ...]}
        where `id` is the concept path without the .md suffix,
        e.g. "01-paid-time-off-leave-operations/1.2-paid-vacation-leave-singapore".
    """
    concepts = []
    knowledge_dir = os.path.abspath(config.KNOWLEDGE_DIR)
    for dirpath, _dirs, files in os.walk(knowledge_dir):
        for name in sorted(files):
            if not name.endswith(".md") or name in RESERVED:
                continue
            full_path = os.path.join(dirpath, name)
            rel_path = os.path.relpath(full_path, knowledge_dir)
            concept_id = os.path.splitext(rel_path)[0]
            data, _ = _parse_file(full_path)
            concepts.append({
                "id": concept_id,
                "title": data.get("title", concept_id),
                "description": data.get("description", ""),
            })
    return {"concepts": concepts}


def read_concept(concept_id: str) -> dict:
    """Read one OKF concept's content and citation.

    Args:
        concept_id: e.g. "03-other-compassionate-unpaid-leaves/3.1-bereavement-leave-global" (no .md).

    Returns:
        {"content": str, "title": str, "resource": str | None}
        where `content` is the markdown body (after the frontmatter) and
        `resource` is the frontmatter `source` (or `resource`) reference if present.
    """
    knowledge_dir = os.path.abspath(config.KNOWLEDGE_DIR)
    if not concept_id:
        return {
            "error": "concept_id is required",
            "content": "",
            "title": "",
            "resource": None,
        }

    # Normalize concept_id (strip leading slash, trailing .md)
    clean_id = concept_id.lstrip("/\\")
    if clean_id.endswith(".md"):
        clean_id = clean_id[:-3]

    target_path = os.path.abspath(os.path.join(knowledge_dir, f"{clean_id}.md"))

    # Guard against path traversal
    if not target_path.startswith(knowledge_dir + os.sep) and target_path != knowledge_dir:
        return {
            "error": f"Invalid concept_id '{concept_id}': path traversal detected.",
            "content": "",
            "title": "",
            "resource": None,
        }

    if not os.path.isfile(target_path):
        return {
            "error": f"Concept '{concept_id}' not found.",
            "content": "",
            "title": "",
            "resource": None,
        }

    data, body = _parse_file(target_path)
    title = data.get("title", "")
    resource = data.get("source") or data.get("resource")
    return {
        "content": body,
        "title": title,
        "resource": resource,
    }
