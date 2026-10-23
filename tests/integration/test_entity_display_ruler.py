"""A2: the entity_extraction tool labels domain terms; ingestion and query NER do not change.

Needs the real spaCy model (tests/unit mocks spaCy out).
"""

from types import SimpleNamespace

import pytest

from src.mcp.request_router import handle_entity_extraction
from src.services import entity_service as es
from src.services.entity_service import EntityService

SENT = (
    "Paperclip and GlobalMOO built a Lean 4 proof with Logan. WeRAI and "
    "Proprioceptive AI use n8n and LiteLLM. Anthropic tracks the EU AI Act."
)
EXPECTED = {
    "Paperclip": "ORG",
    "GlobalMOO": "ORG",
    "WeRAI": "ORG",
    "Proprioceptive AI": "ORG",
    "Anthropic": "ORG",
    "Lean 4": "PRODUCT",
    "n8n": "PRODUCT",
    "LiteLLM": "PRODUCT",
    "Logan": "PERSON",
    "EU AI Act": "LAW",
}
CONTROL = "Apple hired Tim Cook in California"


@pytest.fixture(scope="module")
def service():
    svc = EntityService()
    if svc.nlp is None:
        pytest.skip("spaCy model not available")
    return svc


def _fresh_nlp():
    import spacy

    return spacy.load("en_core_web_sm")


def _plain(nlp, text):
    return [(e.text, e.label_) for e in nlp(text).ents]


def _handler_lines(svc, args):
    out = handle_entity_extraction(args, SimpleNamespace(entity_service=svc))
    assert out["isError"] is False
    return out["content"][0]["text"]


def test_t2a_handler_labels_all_gazetteer_terms(service):
    text = _handler_lines(service, {"text": SENT})
    for term, label in EXPECTED.items():
        assert f"- {term} ({label})" in text


def test_t2b_explicit_entity_types_are_honored(service):
    text = _handler_lines(
        service, {"text": "The 3 audits", "entity_types": ["CARDINAL"]}
    )
    assert "- 3 (CARDINAL)" in text


def test_t2h_ingestion_and_query_ner_unchanged(service):
    fresh = _fresh_nlp()
    assert "entity_ruler" in service.nlp.component_names
    for text in (SENT, CONTROL):
        got = [(e["text"], e["type"]) for e in service.extract_entities(text)]
        assert got == _plain(fresh, text)


def test_t2_negative_control_keeps_labels(service):
    types = ["PERSON", "ORG", "GPE"]
    shown = service.extract_entities_for_display(CONTROL, types)
    plain = service.extract_entities_by_type(CONTROL, types)
    assert [(e["text"], e["type"]) for e in shown] == [
        (e["text"], e["type"]) for e in plain
    ]
    assert ("Apple", "ORG") in [(e["text"], e["type"]) for e in shown]


@pytest.mark.parametrize("content", [None, "", "{not json\n"])
def test_t2i_missing_or_bad_pattern_file_means_no_ruler(tmp_path, service, content):
    path = tmp_path / "entity_patterns.jsonl"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    nlp = _fresh_nlp()
    es._add_display_ruler(nlp, path)
    assert "entity_ruler" not in nlp.component_names
    svc = EntityService.__new__(EntityService)
    svc.nlp = nlp
    text = _handler_lines(svc, {"text": CONTROL})
    assert "- Apple (ORG)" in text
