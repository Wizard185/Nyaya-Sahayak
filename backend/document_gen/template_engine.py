"""
Template-driven document generation via docxtpl (Jinja2-over-docx).

Templates and their field manifests live in corpus/templates/manifest.json.
Each template's fields are substituted directly into its .docx via Jinja2
`{{ field }}` placeholders — no LLM call needed except for fields marked
"narrative": true, which get an optional single polish pass
(see llm/drafting.py:polish_narrative) before being handed to render_template.
"""
import json
import os
from typing import Dict, List, Optional

from docxtpl import DocxTemplate

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus", "templates")
_MANIFEST_PATH = os.path.join(_TEMPLATES_DIR, "manifest.json")

_manifest_cache: Optional[List[dict]] = None


def load_manifest() -> List[dict]:
    global _manifest_cache
    if _manifest_cache is None:
        with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
            _manifest_cache = json.load(f)
    return _manifest_cache


def reload_manifest() -> None:
    global _manifest_cache
    _manifest_cache = None
    load_manifest()


def find_template(template_id: str) -> dict:
    for t in load_manifest():
        if t["id"] == template_id:
            return t
    raise KeyError(f"Unknown template id: {template_id}")


def search_templates(query: str) -> List[dict]:
    """Matches on name, description, and aliases. Empty query returns all templates."""
    query = (query or "").strip().lower()
    templates = load_manifest()
    if not query:
        return templates
    results = []
    for t in templates:
        haystack = " ".join([t["name"], t.get("description", ""), *t.get("aliases", [])]).lower()
        if query in haystack:
            results.append(t)
    return results


def render_template(template_id: str, field_values: Dict[str, str], output_path: str) -> str:
    template = find_template(template_id)
    docx_path = os.path.join(_TEMPLATES_DIR, template["docx_template"])

    doc = DocxTemplate(docx_path)
    context = {f["key"]: field_values.get(f["key"], "") for f in template["fields"]}
    doc.render(context)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path
