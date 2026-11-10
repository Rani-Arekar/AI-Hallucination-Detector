from unittest.mock import patch

from app.vector_db.simple_store import SimpleVectorStore
from app.vector_db.load_kb import load_default_kb


def test_loads_text_from_configured_jsonl_without_network_calls(tmp_path):
    corpus = tmp_path / "knowledge.jsonl"
    corpus.write_text(
        '{"title":"Reference","text":"A verified development statement."}\n'
        '{"text":"Another statement."}\n',
        encoding="utf-8",
    )

    with patch("app.vector_db.load_kb.store") as store:
        assert load_default_kb(corpus) == 2

    store.add_documents.assert_called_once_with(
        ["A verified development statement.", "Another statement."]
    )


def test_missing_corpus_does_not_add_documents(tmp_path):
    with patch("app.vector_db.load_kb.store") as store:
        assert load_default_kb(tmp_path / "missing.jsonl") == 0

    store.add_documents.assert_not_called()


def test_adding_documents_does_not_call_embedding_service():
    store = SimpleVectorStore()

    with patch("app.vector_db.simple_store.embed") as embed:
        store.add_documents(["A local factual statement."])

    embed.assert_not_called()
    assert store.docs == ["A local factual statement."]
    assert store.vectors == [[]]