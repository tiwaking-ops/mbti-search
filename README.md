# MBTI document search + Q&A (Bonsai / Elasticsearch)

Personal toolkit for indexing local MBTI PDFs into a [Bonsai.io](https://bonsai.io) Elasticsearch cluster, searching them, and building a retrieval-augmented prompt for later use with an LLM.

Cluster this project is meant to talk to: **assertive-idesia-5** (put the full URL and credentials in `.env`, never in git).

## What you get

| Piece | Role |
| --- | --- |
| `pdfs/<TYPE>/*.pdf` | Local corpus, one folder per MBTI type (`INTJ`, `ENFP`, …) |
| `scripts/ingest_pdfs.py` | Extract text with PyMuPDF, chunk it, bulk-index into `mbti-docs` |
| `scripts/search_mbti.py` | Full-text search; optional `--type` filter |
| `scripts/ask_mbti.py` | Retrieve top-k chunks and print the LLM prompt (API call is a TODO) |
| `scripts/bonsai_client.py` | Shared `.env` loading, index create, bulk, and search helpers |

Each indexed chunk has these fields:

- `type` — MBTI type inferred from the first folder under `pdfs/` (for example `pdfs/INTJ/notes.pdf` → `INTJ`)
- `source_file` — PDF filename
- `topic` — derived from the filename stem
- `tags` — type plus simple filename tokens
- `chunk_id` — stable id `{TYPE}_{filename}_{n}` (re-ingest overwrites the same chunks)
- `content` — overlapping ~1500-character text window

## 1. Create a `.env` file

Copy the example and fill in values from the Bonsai console (Access → credentials). Do **not** put a username or password in the URL if you are using `BONSAI_USER` / `BONSAI_PASS`.

```bash
copy .env.example .env
```

On macOS/Linux: `cp .env.example .env`

Edit `.env`:

```
BONSAI_URL=https://YOUR-CLUSTER.region.bonsaisearch.net:443
BONSAI_USER=your-bonsai-username
BONSAI_PASS=your-bonsai-password
```

Optional:

```
BONSAI_INDEX=mbti-docs
```

`.env` is listed in `.gitignore`. Never commit real credentials.

## 2. Virtualenv and dependencies

From the project root (`mbti-search`):

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`argparse` is part of the Python standard library; it is not listed in `requirements.txt`.

## 3. Organize PDFs

Create one folder per type and drop PDFs inside:

```
pdfs/
  INTJ/
    cognitive-functions.pdf
    career-notes.pdf
  ENFP/
    loops-and-grips.pdf
  INFJ/
    ...
```

Folder names must be a four-letter type (`INTJ`, `ENFP`, `ISTP`, …). Other folders are skipped.

## 4. Ingest

Creates the `mbti-docs` index if needed, then bulk-indexes chunks:

```powershell
python scripts/ingest_pdfs.py
```

Useful flags:

```powershell
python scripts/ingest_pdfs.py --pdfs-dir pdfs --chunk-size 1500 --overlap 200
```

## 5. Search

```powershell
python scripts/search_mbti.py "cognitive functions"
python scripts/search_mbti.py "Ni vs Ne" --type INTJ
python scripts/search_mbti.py "loop" --type ENFP --size 10
```

Prints `type`, `source_file`, `chunk_id`, and a short content snippet for each hit.

## 6. Q&A prompt (no LLM call yet)

```powershell
python scripts/ask_mbti.py "How does an INTJ typically handle conflict?"
python scripts/ask_mbti.py "What is a Ne-Si loop?" --type ENFP
python scripts/ask_mbti.py "Compare Fi and Fe" --k 8
```

This retrieves top-k chunks from Bonsai, builds a prompt, and **prints it**. It does not call an LLM until you implement `call_llm()` in `scripts/ask_mbti.py`.

## Plugging in a real LLM later

1. Choose a provider (OpenAI, Anthropic, a local model, etc.).
2. Add the client library to `requirements.txt` and an API key to `.env` (and `.gitignore` already covers `.env`).
3. Implement `call_llm(prompt)` in `scripts/ask_mbti.py` (there are commented examples).
4. Uncomment the `call_llm(prompt)` lines at the bottom of `main()`.

Keep retrieval and generation separate: Bonsai remains the source of excerpts; the model only answers from those excerpts.

## Project layout

```
mbti-search/
  .env.example
  .gitignore
  README.md
  requirements.txt
  pdfs/
  scripts/
    bonsai_client.py
    ingest_pdfs.py
    search_mbti.py
    ask_mbti.py
```
