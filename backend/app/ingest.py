from pathlib import Path
import hashlib
import re

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.db import SessionLocal, Chunk


_embedding_model = None


def get_embedding_model():
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    return _embedding_model


def clean(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = 180, overlap: int = 30):
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    chunks = []
    current_words = []
    current_size = 0

    for paragraph in paragraphs:
        words = paragraph.split()

        if len(words) > size:
            if current_words:
                chunks.append(" ".join(current_words))
                current_words = []
                current_size = 0

            start = 0

            while start < len(words):
                end = min(start + size, len(words))

                chunks.append(" ".join(words[start:end]))

                if end >= len(words):
                    break

                start = max(end - overlap, start + 1)

            continue

        if current_words and current_size + len(words) > size:
            chunks.append(" ".join(current_words))

            if overlap > 0:
                current_words = current_words[-overlap:]
                current_size = len(current_words)
            else:
                current_words = []
                current_size = 0

        current_words.extend(words)
        current_size += len(words)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def read_file(path: Path):
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(str(path))

        for page_number, page in enumerate(reader.pages, start=1):
            yield page_number, page.extract_text() or ""

    elif suffix in {".txt", ".md"}:
        yield None, path.read_text(encoding="utf-8")


def embed(texts):
    model = get_embedding_model()

    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return vectors.tolist()


def ingest_file(
    path: Path,
    original_filename: str | None = None
):
    source_name = original_filename or path.name

    try:
        content_bytes = path.read_bytes()
    except Exception as e:
        raise ValueError(f"Could not read file: {e}")

    # Combine filename and content to generate doc_id
    # Changed policy: duplicate document detection based on content alone.
    doc_id = hashlib.sha256(
        content_bytes
    ).hexdigest()[:32]

    # Check if this exact file (name + content) is already indexed
    with SessionLocal() as db:
        existing_chunks = db.query(Chunk).filter(
            Chunk.document_id == doc_id
        ).count()
        if existing_chunks > 0:
            return doc_id, existing_chunks

    parts = []

    try:
        for page, text in read_file(path):
            cleaned = clean(text)
            if not cleaned:
                continue

            chunks = chunk_text(
                cleaned,
                settings.chunk_size,
                settings.chunk_overlap
            )

            for idx, chunk in enumerate(chunks):
                if chunk.strip():
                    parts.append((page, idx, chunk))
    except UnicodeDecodeError:
        raise ValueError("File is not valid UTF-8 text.")
    except Exception as e:
        raise ValueError(f"Failed to parse document: {e}")

    if not parts:
        return None, 0

    vectors = embed([item[2] for item in parts])

    with SessionLocal() as db:
        try:
            # Just in case, clean up any partial or old chunks for this doc_id
            db.query(Chunk).filter(
                Chunk.document_id == doc_id
            ).delete()

            for (page, chunk_index, content), vector in zip(
                parts,
                vectors
            ):
                db.add(
                    Chunk(
                        document_id=doc_id,
                        source=source_name,
                        page=page,
                        chunk_index=chunk_index,
                        content=content,
                        metadata_json={
                            "filename": source_name,
                            "page": page,
                            "chunk_index": chunk_index
                        },
                        embedding=vector
                    )
                )

            db.commit()
        except Exception as e:
            db.rollback()
            raise ValueError(f"Database insertion failed: {e}")

    return doc_id, len(parts)


def ingest_dir(directory):
    results = []

    for path in sorted(Path(directory).rglob("*")):
        if path.suffix.lower() in {".pdf", ".txt", ".md"}:
            doc_id, count = ingest_file(path)

            results.append(
                (path.name, doc_id, count)
            )

    return results
