import streamlit as st
import os
import uuid
import logging
from src.services.gdrive import GDriveService
from src.services.rag import RAGService
from src.database.repository import ChatRepository
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
    st.session_state.room_id = "general"

if "db" not in st.session_state:
    st.session_state.db = ChatRepository()

if "rag_service" not in st.session_state:
    st.session_state.rag_service = RAGService()

if "gdrive_service" not in st.session_state:
    # Initialize GDrive Service wrapper (lazy auth)
    # We will instantiate it but auth might happen later or be reused
    st.session_state.gdrive_wrapper = GDriveService()
    # Check if we are already authenticated by checking internal service
    if st.session_state.gdrive_wrapper.service:
        st.session_state.gdrive_connected = True
    else:
        st.session_state.gdrive_connected = False

if "indexed_file_ids" not in st.session_state:
    st.session_state.indexed_file_ids = set()

if "messages" not in st.session_state:
    try:
        history = st.session_state.db.get_history(st.session_state.room_id)
        st.session_state.messages = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in history
        ]
    except Exception as e:
        logger.error(f"Failed to load history: {e}")
        st.session_state.messages = []

def save_message(role, content):
    """Save message to DB and session state"""
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
    """Uses Gemini to extract search keywords from a user prompt."""
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

# --- Sidebar ---
with st.sidebar:
    st.header("Status & Controls")
    
    # Connection Status
    if st.session_state.gdrive_connected:
        st.success("✅ Connected to Google Drive")
        if st.button("Reconnect / Switch Account"):
            try:
                if os.path.exists(settings.TOKEN_PATH):
                    os.remove(settings.TOKEN_PATH)
                # Re-init
                st.session_state.gdrive_wrapper = GDriveService()
                if st.session_state.gdrive_wrapper.service:
                    st.session_state.gdrive_connected = True
                    st.rerun()
                else:
                    st.error("Re-connection failed (Service is None)")
            except Exception as e:
                st.error(f"Re-connection failed: {e}")
    else:
        st.warning("⚠️ Not Connected")
        if st.button("Connect to Google Drive"):
            try:
                # Force auth
                st.session_state.gdrive_wrapper = GDriveService()
                if st.session_state.gdrive_wrapper.service:
                    st.session_state.gdrive_connected = True
                    st.rerun()
                else:
                    st.error("Connection failed. Check logs.")
            except Exception as e:
                st.error(f"Connection failed: {e}")
                st.info("Ensure 'credentials.json' is present.")

    st.markdown("---")
    
    # Indexed Files List
    st.subheader(f"📚 Indexed Documents ({len(st.session_state.indexed_file_ids)})")
    if st.session_state.indexed_file_ids:
        if st.button("🗑️ Clear Index"):
            st.session_state.rag_service.clear_index()
            st.session_state.indexed_file_ids = set()
            st.success("Memory cleared!")
            st.rerun()
            
        if st.button("📝 Summarize Context"):
             with st.spinner("Summarizing all indexed content..."):
                try:
                    summary = st.session_state.rag_service.summarize()
                    save_message("assistant", f"**Context Summary:**\n\n{summary}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("No documents indexed yet. Ask a question to start searching!")

# --- Chat Logic ---
st.subheader("Chat")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Tanyakan sesuatu (saya akan cari file relevan di Drive)..."):
    save_message("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status_container = st.status("🤔 Memproses...", expanded=True)
        
        try:
            # 1. Check Connection
            if not st.session_state.gdrive_connected:
                status_container.error("Please connect to Google Drive first!")
                st.stop()
            
            # 2. Search in Drive
            status_container.write(f"🔍 Mencari dokumen relevan untuk: '{prompt}'...")
            
            # Step 1: Extract keywords
            search_keywords = extract_keywords_with_gemini(prompt)
            status_container.write(f"🔑 Keywords: {', '.join(search_keywords)}")
            
            # Step 2: Search
            gdrive = st.session_state.gdrive_wrapper
            found_files = gdrive.search_files(search_keywords, limit=5)
            
            # Step 3: Fallback
            if not found_files and len(search_keywords) > 1:
                status_container.write("⚠️ Pencarian spesifik nihil, mencoba pencarian lebih luas...")
                broad_files = []
                for kw in search_keywords:
                    res = gdrive.search_files(kw, limit=2)
                    broad_files.extend(res)
                
                seen_ids = set()
                for f in broad_files:
                    if f['id'] not in seen_ids:
                        found_files.append(f)
                        seen_ids.add(f['id'])
            
            if not found_files:
                status_container.warning("Tidak ditemukan dokumen yang relevan di Google Drive.")
                if not st.session_state.indexed_file_ids:
                    response = "Maaf, saya tidak menemukan dokumen yang relevan dengan pertanyaan Anda di Google Drive, dan belum ada dokumen yang saya ingat."
                    st.markdown(response)
                    save_message("assistant", response)
                    status_container.update(label="Selesai", state="complete", expanded=False)
                    st.stop()
            
            # 3. Download & Index
            new_files_to_index = []
            for f in found_files:
                if f['id'] not in st.session_state.indexed_file_ids:
                    status_container.write(f"⬇️ Mengunduh: {f['name']}...")
                    try:
                        file_path = gdrive.download_file(f['id'], f['name'], f['mimeType'])
                        if file_path:
                            new_files_to_index.append(file_path)
                            st.session_state.indexed_file_ids.add(f['id'])
                        else:
                            status_container.warning(f"⚠️ Format file tidak didukung: {f['name']}")
                    except Exception as e:
                        logger.error(f"Error downloading {f['name']}: {e}")
                        status_container.warning(f"Gagal mengunduh {f['name']}.")
                else:
                    status_container.write(f"✅ Sudah ada di memori: {f['name']}")
            
            if new_files_to_index:
                status_container.write(f"🧠 Membaca {len(new_files_to_index)} dokumen baru...")
                st.session_state.rag_service.index_files(new_files_to_index)
            
            # 4. Generate Answer
            status_container.write("✨ Menyusun jawaban...")
            response = st.session_state.rag_service.ask(prompt)
            
            status_container.update(label="Selesai!", state="complete", expanded=False)
            
            st.markdown(response)
            save_message("assistant", response)

        except Exception as e:
            status_container.error(f"Terjadi kesalahan: {e}")
            logger.error(f"Runtime error: {e}", exc_info=True)
