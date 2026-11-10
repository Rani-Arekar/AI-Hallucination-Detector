import json
import logging
from pathlib import Path

from app.config import KNOWLEDGE_BASE_PATH
from app.vector_db.simple_store import store

logger = logging.getLogger(__name__)
_loaded_paths: set[Path] = set()


def load_default_kb(path: str | Path | None = None) -> int:
    source = Path(path or KNOWLEDGE_BASE_PATH).resolve()
    if source in _loaded_paths:
        return 0
    if not source.is_file():
        logger.warning("Knowledge base file not found: %s", source)
        return 0

    docs = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping invalid knowledge-base JSON at %s:%d", source, line_number)
            continue
        text = record.get("text") if isinstance(record, dict) else None
        if isinstance(text, str) and text.strip():
            docs.append(text.strip())
        else:
            logger.warning("Skipping knowledge-base row without text at %s:%d", source, line_number)

    if docs:
        store.add_documents(docs)
        _loaded_paths.add(source)
    return len(docs)