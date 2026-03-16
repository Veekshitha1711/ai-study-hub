import streamlit as st
import google.generativeai as genai
import yt_dlp
import os
import json
import re
from dotenv import load_dotenv
load_dotenv()

# --- 1. CONFIG ---
st.set_page_config(page_title="AI Master Study Hub", page_icon="🧠", layout="wide")
genai.configure(api_key="GEMINI_API_KEY")
model = genai.GenerativeModel('gemini-2.5-flash')
DB_FILE = "study_data.json"

# --- 2. PERSISTENCE ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"history": []}

def save_to_db(lesson):
    db = load_db()
    db["history"].append(lesson)
    with open(DB_FILE, "w") as f: json.dump(db, f)

# --- 3. STATE ---
if 'history' not in st.session_state: st.session_state.history = load_db()["history"]
if 'current_lesson' not in st.session_state: st.session_state.current_lesson = None
if 'score' not in st.session_state: st.session_state.score = 0
if 'total_answered' not in st.session_state: st.session_state.total_answered = 0
if 'submitted_questions' not in st.session_state: st.session_state.submitted_questions = set()

def submit_answer(q_idx, user_choice, correct_answer):
    st.session_state.total_answered += 1
    st.session_state.submitted_questions.add(q_idx)
    if user_choice == correct_answer: st.session_state.score += 1

# --- 4. STYLING ---
st.markdown("""
    <style>
    .summary-box { background-color: #f0f4f8; padding: 25px; border-radius: 15px; border-left: 8px solid #4A90E2; color: #1a1a1a; }
    .flashcard { background-color: #ffffff; border: 2px solid #4A90E2; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("📂 History")
    for idx, item in enumerate(st.session_state.history):
        if st.button(f"📖 {item['title'][:25]}...", key=f"hist_{idx}"):
            st.session_state.current_lesson = item
            st.session_state.score, st.session_state.total_answered = 0, 0
            st.session_state.submitted_questions = set()
    st.divider()
    if st.button("🗑️ Clear All History"):
        if os.path.exists(DB_FILE): os.remove(DB_FILE)
        st.session_state.history, st.session_state.current_lesson = [], None
        st.rerun()

# --- 6. MAIN LOGIC ---
st.title("🧠 AI Master Study Hub")
url = st.text_input("Paste Link (YouTube, Pinterest, etc.):")

if st.button("Analyze & Learn ✨"):
    if not url:
        st.warning("Paste a link first.")
    else:
        with st.spinner("Deep dive in progress..."):
            try:
                ydl_opts = {'format': 'm4a/bestaudio/best', 'outtmpl': 'temp.%(ext)s', 'nocheckcertificate': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'Untitled Video')
                
                sample_file = genai.upload_file(path="temp.m4a")
                
                # UPDATED PROMPT: Requesting Flashcards
                prompt = """Analyze this video. Provide:
                1. A deep summary (Markdown).
                2. 5 challenging MCQs.
                3. 5 Key Terms & Definitions for Flashcards.
                Output ONLY JSON: 
                {"title": "...", "summary": "...", "quiz": [...], "flashcards": [{"term": "...", "definition": "..."}]}"""
                
                response = model.generate_content(
                    [sample_file, prompt],
                    generation_config={"response_mime_type": "application/json"}
                )
                
                data = json.loads(response.text)
                save_to_db(data)
                st.session_state.history = load_db()["history"]
                st.session_state.current_lesson = data
                os.remove("temp.m4a")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- 7. DISPLAY TABS ---
if st.session_state.current_lesson:
    cur = st.session_state.current_lesson
    tab1, tab2, tab3 = st.tabs(["📝 Summary", "🧪 Quiz", "🗂️ Flashcards"])
    
    with tab1:
        st.markdown(f'<div class="summary-box">{cur["summary"]}</div>', unsafe_allow_html=True)
        
    with tab2:
        m1, m2 = st.columns(2)
        m1.metric("Correct", st.session_state.score)
        m2.metric("Attempted", st.session_state.total_answered)
        for i, q in enumerate(cur["quiz"]):
            st.write(f"**Q{i+1}: {q['question']}**")
            choice = st.radio("Options:", q["options"], index=None, key=f"r_{i}")
            done = i in st.session_state.submitted_questions
            if st.button("Submit", key=f"b_{i}", disabled=done or choice is None, on_click=submit_answer, args=(i, choice, q["answer"])): pass
            if done:
                if choice == q["answer"]: st.success("Correct!")
                else: st.error(f"Answer: {q['answer']}")
            st.divider()

    with tab3:
        st.subheader("Interactive Flashcards")
        st.write("Click to reveal the definition.")
        if "flashcards" in cur:
            for f in cur["flashcards"]:
                with st.expander(f"📌 **Term: {f['term']}**"):
                    st.markdown(f'<div class="flashcard">{f["definition"]}</div>', unsafe_allow_html=True)
        else:
            st.info("No flashcards available for this lesson.")