import os
import streamlit as st
from dotenv import load_dotenv
from scripts.bonsai_client import get_session, search_chunks
import google.generativeai as genai

load_dotenv()

st.set_page_config(page_title="MBTI Search", page_icon="🔍")
st.title("MBTI Personal Search")

# --- Sidebar / controls ---
types = [
    "Any", "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP"
]

col1, col2 = st.columns(2)
with col1:
    my_type = st.selectbox("My type", types, index=types.index("INTP"))
with col2:
    their_type = st.selectbox("Their type / focus", types, index=0)

question = st.text_area(
    "Your question",
    placeholder="e.g. How can I improve communication with an INFP about an assignment?",
    height=100,
)

col_a, col_b = st.columns(2)
search_clicked = col_a.button("Search only", use_container_width=True)
answer_clicked = col_b.button("Generate answer", type="primary", use_container_width=True)

def get_relevant_chunks(query: str, mbti_filter: str | None, size: int = 6):
    session, base_url = get_session()
    return search_chunks(session, base_url, query, mbti_type=mbti_filter, size=size)

def generate_answer(question: str, my_type: str, their_type: str, chunks: list) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "GEMINI_API_KEY not found in .env"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    context_parts = []
    for i, hit in enumerate(chunks, 1):
        src = hit["_source"]
        context_parts.append(
            f"[Source {i} | Type: {src.get('type')} | File: {src.get('source_file')}]\n{src.get('content', '')}"
        )
    context = "\n\n".join(context_parts)

    prompt = f"""You are a helpful assistant that answers questions about MBTI using only the provided source material.

My type: {my_type}
Their type / focus: {their_type}

Question: {question}

Source material from my documents:
{context}

Instructions:
- Answer clearly and practically.
- Base your answer mainly on the source material above.
- If the sources are limited, you may add brief general MBTI knowledge, but prefer the sources.
- Structure the answer so it is easy to read (short paragraphs or bullet points).
- Speak directly to me (the {my_type}).
"""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error calling Gemini: {e}"

# --- Main logic ---
if search_clicked or answer_clicked:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        mbti_filter = None if their_type == "Any" else their_type

        with st.spinner("Searching your documents..."):
            hits = get_relevant_chunks(question, mbti_filter, size=6)

        if not hits:
            st.info("No matching chunks found.")
        else:
            if answer_clicked:
                with st.spinner("Generating answer with Gemini..."):
                    answer = generate_answer(question, my_type, their_type, hits)
                st.subheader("Answer")
                st.markdown(answer)
                st.divider()

            st.subheader("Source passages")
            for i, hit in enumerate(hits, 1):
                src = hit["_source"]
                score = hit.get("_score", 0)
                with st.expander(f"{i}. {src.get('type', '')} — {src.get('source_file', '')} (score: {score:.2f})"):
                    st.write(src.get("content", ""))