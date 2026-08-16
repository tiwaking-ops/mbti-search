"""
Shared Bonsai / Elasticsearch helpers.

Loads BONSAI_URL, BONSAI_USER, and BONSAI_PASS from a .env file
and talks to the cluster over HTTPS with HTTP Basic auth.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Load .env from the project root (parent of this scripts/ folder).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

INDEX_NAME = os.getenv("BONSAI_INDEX", "mbti-docs")

# Mapping for MBTI document chunks.
INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
    },
    "mappings": {
        "properties": {
            "type": {"type": "keyword"},
            "source_file": {"type": "keyword"},
            "topic": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "tags": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "content": {"type": "text"},
        }
    },
}


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"Missing {name}. Copy .env.example to .env and fill in your Bonsai credentials."
        )
    return value


def get_session() -> tuple[requests.Session, str]:
    """Return an authenticated requests session and the cluster base URL."""
    url = _require_env("BONSAI_URL").rstrip("/")
    user = _require_env("BONSAI_USER")
    password = _require_env("BONSAI_PASS")

    session = requests.Session()
    session.auth = (user, password)
    session.headers.update({"Content-Type": "application/json"})
    return session, url


def ensure_index(session: requests.Session, base_url: str) -> None:
    """Create the mbti-docs index if it does not already exist."""
    index_url = f"{base_url}/{INDEX_NAME}"
    exists = session.head(index_url)
    if exists.status_code == 200:
        print(f"Index '{INDEX_NAME}' already exists.")
        return
    if exists.status_code not in (404, 405):
        # Some clusters reject HEAD; fall back to GET.
        get_resp = session.get(index_url)
        if get_resp.status_code == 200:
            print(f"Index '{INDEX_NAME}' already exists.")
            return
        if get_resp.status_code != 404:
            raise SystemExit(
                f"Could not check index '{INDEX_NAME}': "
                f"{get_resp.status_code} {get_resp.text}"
            )

    create = session.put(index_url, json=INDEX_BODY)
    if create.status_code not in (200, 201):
        raise SystemExit(
            f"Failed to create index '{INDEX_NAME}': {create.status_code} {create.text}"
        )
    print(f"Created index '{INDEX_NAME}'.")


def bulk_index(
    session: requests.Session,
    base_url: str,
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Send documents to Elasticsearch via the bulk API.

    Each document should include a chunk_id used as the document _id
    so re-ingesting the same PDF overwrites previous chunks.
    """
    if not documents:
        return {"errors": False, "items": []}

    lines: list[str] = []
    for doc in documents:
        action = {
            "index": {
                "_index": INDEX_NAME,
                "_id": doc["chunk_id"],
            }
        }
        # NDJSON: action line, then source line.
        lines.append(json.dumps(action))
        lines.append(json.dumps(doc))

    payload = "\n".join(lines) + "\n"
    resp = session.post(
        f"{base_url}/_bulk",
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/x-ndjson"},
    )
    if resp.status_code >= 300:
        raise SystemExit(f"Bulk request failed: {resp.status_code} {resp.text}")

    result = resp.json()
    if result.get("errors"):
        failed = [
            item
            for item in result.get("items", [])
            if list(item.values())[0].get("error")
        ]
        print(f"Bulk completed with {len(failed)} item error(s). First error:")
        print(failed[0] if failed else result)
    return result


def search_chunks(
    session: requests.Session,
    base_url: str,
    query: str,
    mbti_type: str | None = None,
    size: int = 5,
) -> list[dict[str, Any]]:
    """Full-text search over chunk content, optionally filtered by MBTI type."""
    must: list[dict[str, Any]] = [
        {
            "multi_match": {
                "query": query,
                "fields": ["content", "topic", "source_file"],
            }
        }
    ]
    filters: list[dict[str, Any]] = []
    if mbti_type:
        filters.append({"term": {"type": mbti_type.upper()}})

    body = {
        "size": size,
        "query": {
            "bool": {
                "must": must,
                "filter": filters,
            }
        },
        "highlight": {
            "fields": {
                "content": {
                    "fragment_size": 240,
                    "number_of_fragments": 1,
                }
            }
        },
    }

    resp = session.post(f"{base_url}/{INDEX_NAME}/_search", json=body)
    if resp.status_code >= 300:
        raise SystemExit(f"Search failed: {resp.status_code} {resp.text}")

    hits = resp.json().get("hits", {}).get("hits", [])
    return hits
