"""Bounded local specialist adapters used by the ALETHEIA benchmark.

Adapters receive only a fixture payload.  Network providers deliberately do not
appear here; deployments may supply an adapter conforming to ``SpecialistAdapter``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
from math import sqrt
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Protocol


TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)


class SpecialistAdapter(Protocol):
    identifier: str
    capability: str
    license: str
    local: bool

    def run(self, payload: dict[str, Any]) -> Any: ...


def tokens(text: str) -> Counter[str]:
    return Counter(TOKEN_RE.findall(text.lower()))


def cosine(left: Counter[str], right: Counter[str]) -> float:
    dot = sum(value * right.get(key, 0) for key, value in left.items())
    left_norm = sqrt(sum(value * value for value in left.values()))
    right_norm = sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


@dataclass(frozen=True)
class LexicalRetrieval:
    identifier: str = "local.lexical-tf"
    capability: str = "retrieval"
    license: str = "MIT"
    local: bool = True

    def run(self, payload: dict[str, Any]) -> list[str]:
        query = tokens(str(payload["query"]))
        documents = payload["documents"]
        ranked = sorted(
            ((cosine(query, tokens(str(document["text"]))), str(document["id"])) for document in documents),
            key=lambda item: (-item[0], item[1]),
        )
        return [document_id for _, document_id in ranked]


@dataclass(frozen=True)
class HashEmbeddingRetrieval:
    """A deterministic, dependency-free embedding baseline (not an adoption candidate)."""

    identifier: str = "local.hash-embedding-v1"
    capability: str = "embedding"
    license: str = "MIT"
    local: bool = True

    def run(self, payload: dict[str, Any]) -> list[str]:
        def vector(text: str) -> Counter[int]:
            return Counter(
                int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:2], "big") % 256
                for token in TOKEN_RE.findall(text.lower())
            )

        query = vector(str(payload["query"]))
        ranked = sorted(
            ((cosine(query, vector(str(document["text"]))), str(document["id"])) for document in payload["documents"]),
            key=lambda item: (-item[0], item[1]),
        )
        return [document_id for _, document_id in ranked]


@dataclass(frozen=True)
class LexicalReranker:
    identifier: str = "local.lexical-reranker"
    capability: str = "reranking"
    license: str = "MIT"
    local: bool = True

    def run(self, payload: dict[str, Any]) -> list[str]:
        query = tokens(str(payload["query"]))
        candidates = payload["candidates"]
        ranked = sorted(
            ((cosine(query, tokens(str(candidate["text"]))), str(candidate["id"])) for candidate in candidates),
            key=lambda item: (-item[0], item[1]),
        )
        return [document_id for _, document_id in ranked]


@dataclass(frozen=True)
class PlainTextParser:
    identifier: str = "local.plaintext-parser"
    capability: str = "parsing"
    license: str = "MIT"
    local: bool = True

    def run(self, payload: dict[str, Any]) -> str:
        return str(payload["text"]).replace("\r\n", "\n").strip()


@dataclass(frozen=True)
class TesseractOCR:
    identifier: str = "local.tesseract"
    capability: str = "ocr"
    license: str = "Apache-2.0"
    local: bool = True

    @property
    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    def run(self, payload: dict[str, Any]) -> str:
        if not self.available:
            raise RuntimeError("tesseract executable is unavailable")
        image_path = Path(str(payload["image_path"]))
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "6"],
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
        return result.stdout.strip()


def available_local_candidates() -> list[SpecialistAdapter]:
    """Return only local/free candidates. Optional provider adapters are opt-in."""
    candidates: list[SpecialistAdapter] = [
        LexicalRetrieval(), HashEmbeddingRetrieval(), LexicalReranker(), PlainTextParser()
    ]
    ocr = TesseractOCR()
    if ocr.available:
        candidates.append(ocr)
    return candidates
