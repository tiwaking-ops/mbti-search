"""
Walk pdfs/<TYPE>/*.pdf, extract text, chunk it, and bulk-index into Bonsai.

Usage (from the project root):

    python scripts/ingest_pdfs.py
    python scripts/ingest_pdfs.py --pdfs-dir pdfs
    python scripts/ingest_pdfs.py --chunk-size 1500 --overlap 200
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Allow `python scripts/ingest_pdfs.py` to import sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz  # pymupdf

from bonsai_client import bulk_index, ensure_index, get_session

# Four-letter MBTI type, e.g. INTJ, ENFP.
MBTI_TYPE_RE = re.compile(r"^[IE][NS][TF][JP]$", re.IGNORECASE)

DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP = 200


def extract_pdf_text(pdf_path: Path) -> str:
    """Return concatenated text from every page of a PDF."""
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text") or "")
    # Collapse extra whitespace so chunks are closer to real paragraphs.
    text = "\n".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping character windows of about chunk_size."""
    if not text:
        return []
    if overlap >= chunk_size:
        raise SystemExit("--overlap must be smaller than --chunk-size")

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = end - overlap
    return chunks


def infer_type_from_folder(folder_name: str) -> str | None:
    """Return an MBTI type if the folder name looks like INTJ, ENFP, etc."""
    name = folder_name.strip().upper()
    if MBTI_TYPE_RE.match(name):
        return name
    return None


def topic_and_tags(mbti_type: str, pdf_path: Path) -> tuple[str, list[str]]:
    """
    Derive a simple topic from the filename and a few tags.

    Easy to extend later (e.g. read a sidecar JSON, or parse PDF metadata).
    """
    stem = pdf_path.stem.replace("_", " ").replace("-", " ").strip()
    topic = stem or mbti_type
    tags = [mbti_type, "mbti", "pdf"]
    extra = [part.lower() for part in re.split(r"[\s_\-]+", stem) if part]
    tags.extend(extra)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_tags: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    return topic, unique_tags


def collect_documents(
    pdfs_dir: Path,
    chunk_size: int,
    overlap: int,
) -> list[dict]:
    """Walk pdfs/<TYPE>/*.pdf and build Elasticsearch documents."""
    if not pdfs_dir.is_dir():
        raise SystemExit(
            f"PDF directory not found: {pdfs_dir}\n"
            "Create folders like pdfs/INTJ/ and put PDFs inside them."
        )

    documents: list[dict] = []
    type_folders = sorted(p for p in pdfs_dir.iterdir() if p.is_dir())
    if not type_folders:
        raise SystemExit(
            f"No type folders under {pdfs_dir}. Expected pdfs/INTJ/, pdfs/ENFP/, etc."
        )

    for folder in type_folders:
        mbti_type = infer_type_from_folder(folder.name)
        if not mbti_type:
            print(f"Skipping folder '{folder.name}' (not an MBTI type name).")
            continue

        pdfs = sorted(folder.glob("*.pdf"))
        if not pdfs:
            print(f"No PDFs in {folder}.")
            continue

        for pdf_path in pdfs:
            print(f"Extracting {pdf_path} ...")
            text = extract_pdf_text(pdf_path)
            chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            if not chunks:
                print(f"  (no text extracted, skipping)")
                continue

            topic, tags = topic_and_tags(mbti_type, pdf_path)
            source_file = pdf_path.name
            for i, content in enumerate(chunks):
                chunk_id = f"{mbti_type}_{source_file}_{i}"
                documents.append(
                    {
                        "type": mbti_type,
                        "source_file": source_file,
                        "topic": topic,
                        "tags": tags,
                        "chunk_id": chunk_id,
                        "content": content,
                    }
                )
            print(f"  {len(chunks)} chunk(s)")

    return documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest MBTI PDFs into the Bonsai mbti-docs index."
    )
    parser.add_argument(
        "--pdfs-dir",
        default="pdfs",
        help="Root folder that contains pdfs/<TYPE>/*.pdf (default: pdfs)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Target chunk length in characters (default: {DEFAULT_CHUNK_SIZE})",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=DEFAULT_OVERLAP,
        help=f"Character overlap between chunks (default: {DEFAULT_OVERLAP})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdfs_dir = Path(args.pdfs_dir)
    if not pdfs_dir.is_absolute():
        pdfs_dir = Path(__file__).resolve().parent.parent / pdfs_dir

    session, base_url = get_session()
    ensure_index(session, base_url)

    documents = collect_documents(
        pdfs_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    if not documents:
        raise SystemExit("Nothing to ingest.")

    print(f"Sending {len(documents)} chunk(s) to Bonsai via bulk API ...")
    result = bulk_index(session, base_url, documents)
    took = result.get("took", "?")
    errors = result.get("errors", False)
    print(f"Done. took={took}ms errors={errors}")


if __name__ == "__main__":
    main()
