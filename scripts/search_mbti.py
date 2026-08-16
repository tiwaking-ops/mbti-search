"""
Search the mbti-docs index and print matching chunks.

Usage (from the project root):

    python scripts/search_mbti.py "Ni vs Ne"
    python scripts/search_mbti.py "cognitive functions" --type INTJ
    python scripts/search_mbti.py "loop" --type ENFP --size 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bonsai_client import INDEX_NAME, get_session, search_chunks


def snippet_from_hit(hit: dict, max_len: int = 280) -> str:
    """Prefer Elasticsearch highlight fragments; otherwise trim content."""
    highlights = hit.get("highlight", {}).get("content") or []
    if highlights:
        text = " ".join(highlights)
    else:
        text = (hit.get("_source") or {}).get("content") or ""
    text = " ".join(text.split())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Search the {INDEX_NAME} index.")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--type",
        dest="mbti_type",
        default=None,
        help="Optional MBTI type filter, e.g. INTJ or ENFP",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=5,
        help="Number of hits to return (default: 5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session, base_url = get_session()
    hits = search_chunks(
        session,
        base_url,
        query=args.query,
        mbti_type=args.mbti_type,
        size=args.size,
    )

    if not hits:
        print("No matches.")
        return

    print(f"Found {len(hits)} hit(s) in '{INDEX_NAME}':\n")
    for i, hit in enumerate(hits, start=1):
        source = hit.get("_source") or {}
        score = hit.get("_score")
        print(f"[{i}] score={score:.4f}" if isinstance(score, (int, float)) else f"[{i}]")
        print(f"    type:        {source.get('type')}")
        print(f"    source_file: {source.get('source_file')}")
        print(f"    chunk_id:    {source.get('chunk_id')}")
        print(f"    snippet:     {snippet_from_hit(hit)}")
        print()


if __name__ == "__main__":
    main()
