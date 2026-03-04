import streamlit as st
import os
import uuid
import logging
from src.services.gdrive import GDriveService
from src.services.rag import RAGService
from src.database.repository import ChatRepository
from src.core.agent import ChatAgent
from src.utils.helpers import create_pdf
import google.generativeai as genai
from src.core.config import settings

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title=settings.APP_NAME, layout="wide")
st.title("🤖 Chat with your Google Drive")

# Configure Gemini
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

# --- Initialization ---
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "room_id" not in st.session_state:
    st.session_state.room_id = str(uuid.uuid4())

if "db" not in st.session_state:
    st.session_state.db = ChatRepository()

if "rag_service" not in st.session_state:
    st.session_state.rag_service = RAGService()

if "agent" not in st.session_state:
    st.session_state.agent = ChatAgent()

if "gdrive_service" not in st.session_state:
    st.session_state.gdrive_wrapper = GDriveService()
    if st.session_state.gdrive_wrapper.service:
        st.session_state.gdrive_connected = True
    else:
        st.session_state.gdrive_connected = False

if "indexed_file_ids" not in st.session_state:
    st.session_state.indexed_file_ids = set()

if "force_search" not in st.session_state:
    st.session_state.force_search = None

# Helper to load messages
def load_messages():
    try:
        history = st.session_state.db.get_history(st.session_state.room_id)
        st.session_state.messages = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in history
        ]
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        st.session_state.messages = []

if "messages" not in st.session_state:
    load_messages()

def save_message(role, content):
    st.session_state.messages.append({"role": role, "content": content})
    try:
        st.session_state.db.save_message(
            user_id=st.session_state.user_id,
            room_id=st.session_state.room_id,
            role=role,
            content=content
        )
    except Exception as e:
        logger.error(f"Failed to save message: {e}")

def extract_keywords_with_gemini(prompt):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            f"Extract 1-3 main search keywords/phrases from this user prompt for searching in Google Drive. "
            f"Ignore common words like 'carikan', 'tolong', 'dokumen', 'file'. "
            f"Return ONLY the keywords separated by commas. "
            f"Prompt: '{prompt}'"
        )
        keywords = [k.strip() for k in response.text.split(',') if k.strip()]
        return keywords
    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")
        return prompt.split()

def log_action(action, details=""):
    logger.info(f"ANALYTICS: User {st.session_state.user_id} performed {action} | Details: {details}")

# --- Sidebar: Chat Rooms ---
with st.sidebar:
    st.header("💬 Chats")
    
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.room_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.subheader("History")
    
    rooms = st.session_state.db.get_user_rooms(st.session_state.user_id)
    
    for room in rooms:
        room_id = room["_id"]
        title = room.get("first_message", "New Chat")
        if title:
            title = (title[:30] + '..') if len(title) > 30 else title
        else:
            title = "New Chat"
            
        if room_id == st.session_state.room_id:
            st.button(f"👉 {title}", key=room_id, disabled=True, use_container_width=True)
        else:
            if st.button(f"🗨️ {title}", key=room_id, use_container_width=True):
                st.session_state.room_id = room_id
                load_messages()
                st.rerun()

# --- Main Chat Interface ---

# Display chat history
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Action Cards for Assistant messages
        if message["role"] == "assistant":
            # Identify the corresponding query (simple heuristic: preceding message)
            query = ""
            if i > 0 and st.session_state.messages[i-1]["role"] == "user":
                query = st.session_state.messages[i-1]["content"]
                # If the user message was a forced search (starts with "🔄 *Force Internet Search:* "), clean it
                if query.startswith("🔄 *Force Internet Search:* "):
                    query = query.replace("🔄 *Force Internet Search:* ", "")

            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                 # Removed Markdown button
                 pass
            with col2:
                 # Center the remaining buttons using a container or columns
                 pass
            
            # New Centered Layout for Action Cards
            st.markdown("---") # Optional separator
            c1, c2, c3, c4 = st.columns([2, 3, 3, 2])
            
            with c2:
                 if st.button("🌐 Cari di Internet", key=f"web_{i}", use_container_width=True):
                     log_action("force_internet_search", f"msg_{i}")
                     if query:
                         st.session_state.force_search = query
                         st.rerun()
                     else:
                         st.warning("Query not found for this message.")
            
            with c3:
                 try:
                     pdf_bytes = create_pdf(message["content"])
                     st.download_button(
                         label="📄 Convert ke PDF",
                         data=pdf_bytes,
                         file_name=f"response_{i}.pdf",
                         mime="application/pdf",
                         key=f"pdf_{i}",
                         on_click=log_action,
                         args=("download_pdf", f"msg_{i}"),
                         use_container_width=True
                     )
                 except Exception as e:
                     st.error(f"PDF Error: {e}")


# Chat Input
user_input = st.chat_input("Tanyakan sesuatu...")

# Determine if we have a prompt to process (User input or Forced Search)
prompt = None
is_forced_internet = False

if st.session_state.force_search:
    prompt = st.session_state.force_search
    st.session_state.force_search = None
    is_forced_internet = True
elif user_input:
    prompt = user_input
    is_forced_internet = False

if prompt:
    # Display and Save User Message
    if is_forced_internet:
        display_text = f"🔄 *Force Internet Search:* {prompt}"
        save_message("user", display_text)
        with st.chat_message("user"):
            st.markdown(display_text)
    else:
        save_message("user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

    with st.chat_message("assistant"):
        status_container = st.status("🤔 Memproses...", expanded=True)
        
        try:
            # DECISION ENGINE
            search_keywords = []
            
            if is_forced_internet:
                pipeline = 'internet'
                status_container.write("🔄 Mode: Forced Internet Search")
            else:
                # Use new NLP-based intent analysis
                analysis = st.session_state.agent.analyze_intent(prompt)
                pipeline = analysis.get("pipeline", "llm")
                search_keywords = analysis.get("keywords", [])
                confidence = analysis.get("confidence", 0.0)
                
                status_container.write(f"🧠 Intent Analysis: {pipeline.upper()} (Confidence: {confidence:.2f})")
                if search_keywords:
                    status_container.write(f"🔑 Keywords: {', '.join(search_keywords)}")

            response_text = ""
            source = ""
            
            # --- PIPELINE 1: DRIVE SEARCH ---
            if pipeline == 'drive':
                status_container.write("📂 Pipeline: Google Drive Search")
                
                # Check Connection
                if not st.session_state.gdrive_connected:
                    status_container.warning("⚠️ Google Drive not connected. Checking internal memory...")
                    pipeline = 'llm'
                else:
                    status_container.write(f"🔍 Mencari dokumen relevan...")
                    
                    # Use keywords from analysis if available, otherwise fallback
                    if not search_keywords:
                         search_keywords = extract_keywords_with_gemini(prompt)

                    gdrive = st.session_state.gdrive_wrapper
                    found_files = gdrive.search_files(search_keywords, limit=5)
                    
                    # Fallback broad search
                    if not found_files and len(search_keywords) > 1:
                        status_container.write("⚠️ Pencarian spesifik nihil, mencoba pencarian luas...")
                        for kw in search_keywords:
                            res = gdrive.search_files(kw, limit=2)
                            found_files.extend(res)
                            
                    # Process Found Files
                    if found_files:
                        new_files = []
                        for f in found_files:
                            if f['id'] not in st.session_state.indexed_file_ids:
                                status_container.write(f"⬇️ Mengunduh: {f['name']}...")
                                path = gdrive.download_file(f['id'], f['name'], f['mimeType'])
                                if path:
                                    new_files.append(path)
                                    st.session_state.indexed_file_ids.add(f['id'])
                        
                        if new_files:
                            status_container.write(f"🧠 Membaca {len(new_files)} dokumen baru...")
                            st.session_state.rag_service.index_files(new_files)
                            
                        status_container.write("✨ Menyusun jawaban dari dokumen...")
                        response_text = st.session_state.rag_service.ask(prompt)
                        source = "drive"
                    else:
                        status_container.warning("❌ Tidak ditemukan dokumen relevan di Drive.")
                        pipeline = 'internet'

            # --- PIPELINE 2: LLM NATIVE ---
            if pipeline == 'llm':
                status_container.write("🤖 Pipeline: Knowledge Base Internal")
                answer, confidence = st.session_state.agent.generate_native_response(prompt)
                
                status_container.write(f"📊 Confidence Score: {confidence:.2f}")
                
                if confidence < settings.LLM_CONFIDENCE_THRESHOLD:
                    status_container.warning("⚠️ Confidence rendah. Beralih ke pencarian internet...")
                    pipeline = 'internet'
                else:
                    response_text = answer
                    source = "llm"

            # --- PIPELINE 3: INTERNET SEARCH ---
            if pipeline == 'internet':
                status_container.write("🌐 Pipeline: Internet Search")
                answer, results = st.session_state.agent.generate_internet_response(prompt)
                response_text = answer
                source = "internet"
                
                if results:
                    with st.expander("📚 Sumber Internet"):
                        for r in results:
                            st.write(f"- [{r['title']}]({r['href']})")

            status_container.update(label="Selesai!", state="complete", expanded=False)
            
            st.markdown(response_text)
            save_message("assistant", response_text)
            
            # Action Cards for this new message (Immediate feedback)
            st.markdown("---")
            c1, c2, c3, c4 = st.columns([2, 3, 3, 2])
            
            with c2:
                 if st.button("🌐 Cari di Internet", key="web_new", use_container_width=True):
                     log_action("force_internet_search", "new_msg")
                     st.session_state.force_search = prompt
                     st.rerun()
            
            with c3:
                 try:
                     pdf_bytes = create_pdf(response_text)
                     st.download_button(
                         label="📄 PDF", 
                         data=pdf_bytes, 
                         file_name="response_new.pdf", 
                         mime="application/pdf", 
                         key="pdf_new", 
                         on_click=log_action, 
                         args=("download_pdf", "new_msg"),
                         use_container_width=True
                     )
                 except Exception as e:
                     st.error(f"PDF Error: {e}")

        except Exception as e:
            status_container.error(f"Terjadi kesalahan: {e}")
            logger.error(f"Runtime error: {e}", exc_info=True)
