import math
import re
from collections import Counter
from threading import Lock

from app.utils.embeddings import embed
from app.utils.similarity import cosine

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_BM25_K1 = 1.5
_BM25_B = 0.75
_RRF_CONSTANT = 60


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.casefold())


class SimpleVectorStore:
    def __init__(self):
        self.docs: list[str] = []
        self.vectors: list[list[float]] = []
        self._embedding_lock = Lock()

    def add_documents(self, docs: list[str]) -> None:
        self.docs.extend(docs)
        self.vectors.extend([[] for _ in docs])

    def query_keyword(self, text: str, k: int = 3) -> list[tuple[float, str]]:
        """Rank local documents with BM25 without an additional dependency."""
        query_terms = _tokens(text)
        if not query_terms or not self.docs or k <= 0:
            return []

        tokenized_docs = [_tokens(doc) for doc in self.docs]
        document_frequencies = Counter(
            term for terms in tokenized_docs for term in set(terms)
        )
        average_length = sum(map(len, tokenized_docs)) / len(tokenized_docs) or 1.0
        query_counts = Counter(query_terms)
        scored = []

        for doc, terms in zip(self.docs, tokenized_docs):
            term_counts = Counter(terms)
            document_length = len(terms)
            score = 0.0
            for term, query_frequency in query_counts.items():
                frequency = term_counts[term]
                if not frequency:
                    continue
                doc_frequency = document_frequencies[term]
                inverse_frequency = math.log(
                    1 + (len(self.docs) - doc_frequency + 0.5) / (doc_frequency + 0.5)
                )
                denominator = frequency + _BM25_K1 * (
                    1 - _BM25_B + _BM25_B * document_length / average_length
                )
                score += query_frequency * inverse_frequency * (
                    frequency * (_BM25_K1 + 1) / denominator
                )
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:k]

    def query(self, text: str, k: int = 3) -> list[tuple[float, str]]:
        if not self.docs:
            return []

        with self._embedding_lock:
            missing = [index for index, vector in enumerate(self.vectors) if not vector]
            if missing:
                document_vectors = embed([self.docs[index] for index in missing])
                for index, vector in zip(missing, document_vectors):
                    self.vectors[index] = vector or []

        query_vec = embed([text])[0]
        if not query_vec:
            # embedding failed; degrade to "no local evidence" rather than
            # raising and taking down the whole claim check.
            return []

        sims = [
            (cosine(query_vec, vector), document)
            for vector, document in zip(self.vectors, self.docs)
            if vector
        ]
        sims.sort(key=lambda pair: pair[0], reverse=True)
        return sims[:k]

    def query_hybrid(self, text: str, k: int = 3) -> list[dict]:
        """Fuse semantic and BM25 rankings without treating either as truth."""
        if not self.docs or k <= 0:
            return []

        fused: dict[str, dict] = {}

        def entry_for(document: str) -> dict:
            key = " ".join(document.casefold().split())
            return fused.setdefault(
                key,
                {
                    "text": document,
                    "semantic_similarity": None,
                    "keyword_score": 0.0,
                    "retrieval_score": 0.0,
                },
            )

        semantic_results = [
            item for item in self.query(text, len(self.docs)) if item[0] > 0
        ]
        keyword_results = self.query_keyword(text, len(self.docs))

        for rank, (score, document) in enumerate(semantic_results, start=1):
            entry = entry_for(document)
            entry["semantic_similarity"] = score
            entry["retrieval_score"] += 1 / (_RRF_CONSTANT + rank)

        for rank, (score, document) in enumerate(keyword_results, start=1):
            entry = entry_for(document)
            entry["keyword_score"] = score
            entry["retrieval_score"] += 1 / (_RRF_CONSTANT + rank)

        ranked = sorted(
            fused.values(), key=lambda item: item["retrieval_score"], reverse=True
        )
        return ranked[:k]


# global instance
store = SimpleVectorStore()
