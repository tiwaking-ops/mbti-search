"""
Retrieve relevant MBTI chunks and build an LLM prompt for a question.

The actual LLM API call is left as a clearly marked TODO. For now this
script prints the constructed prompt so you can inspect what would be sent.

Usage (from the project root):

    python scripts/ask_mbti.py "How does an INTJ typically handle conflict?"
    python scripts/ask_mbti.py "What is a Ne-Si loop?" --type ENFP
    python scripts/ask_mbti.py "Compare Fi and Fe" --k 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bonsai_client import get_session, search_chunks


SYSTEM_INSTRUCTIONS = """You are a careful assistant answering questions about MBTI using only the retrieved document excerpts below.
If the excerpts are not enough, say so instead of inventing details.
Cite source_file and MBTI type when you use a passage."""


def build_prompt(question: str, hits: list[dict], mbti_type: str | None) -> str:
    """Assemble a single prompt string from the question and retrieved chunks."""
    type_note = (
        f"The user asked to focus on type: {mbti_type.upper()}."
        if mbti_type
        else "No type filter was applied; excerpts may cover several types."
    )

    context_blocks: list[str] = []
    for i, hit in enumerate(hits, start=1):
        source = hit.get("_source") or {}
        content = (source.get("content") or "").strip()
        context_blocks.append(
            "\n".join(
                [
                    f"[Excerpt {i}]",
                    f"type: {source.get('type')}",
                    f"source_file: {source.get('source_file')}",
                    f"topic: {source.get('topic')}",
                    f"chunk_id: {source.get('chunk_id')}",
                    "content:",
                    content,
                ]
            )
        )

    if context_blocks:
        context = "\n\n".join(context_blocks)
    else:
        context = "(No matching excerpts were retrieved from the index.)"

    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"{type_note}\n\n"
        f"--- Retrieved excerpts ---\n\n"
        f"{context}\n\n"
        f"--- Question ---\n\n"
        f"{question}\n\n"
        f"--- Answer ---\n"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve MBTI chunks and print a Q&A prompt (LLM call is a TODO)."
    )
    parser.add_argument("question", help="Natural-language question")
    parser.add_argument(
        "--type",
        dest="mbti_type",
        default=None,
        help="Optional MBTI type filter, e.g. INTJ or ENFP",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Number of chunks to retrieve (default: 5)",
    )
    return parser.parse_args()


def call_llm(prompt: str) -> str:
    """
    TODO: Plug in a real LLM API here.

    Example with OpenAI (install openai and set OPENAI_API_KEY):

        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    Example with Anthropic (install anthropic and set ANTHROPIC_API_KEY):

        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-0",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    Until this is implemented, we only print the prompt.
    """
    raise NotImplementedError("LLM API call is not wired up yet. See TODO in call_llm().")


def main() -> None:
    args = parse_args()
    session, base_url = get_session()
    hits = search_chunks(
        session,
        base_url,
        query=args.question,
        mbti_type=args.mbti_type,
        size=args.k,
    )

    prompt = build_prompt(args.question, hits, args.mbti_type)

    print("=" * 72)
    print("Constructed LLM prompt (not sent — LLM call is a TODO)")
    print("=" * 72)
    print(prompt)
    print("=" * 72)
    print(f"Retrieved {len(hits)} chunk(s). Replace call_llm() when you are ready.")

    # TODO: Uncomment when you have wired up an LLM provider in call_llm().
    # answer = call_llm(prompt)
    # print("\n--- Model answer ---\n")
    # print(answer)


if __name__ == "__main__":
    main()
