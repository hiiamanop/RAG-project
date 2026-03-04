import streamlit as st
import os
import gdrive_utils
from rag_pipeline import RAGPipeline
from chat_database import ChatDatabase
import uuid

st.set_page_config(page_title="GDrive Chatbot", layout="wide")

st.title("🤖 Chat with your Google Drive")

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
if "GOOGLE_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# --- Initialization ---
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "room_id" not in st.session_state:
    st.session_state.room_id = "general" # Default room

if "db" not in st.session_state:
    # Initialize DB (will use mock if no URI provided, safe for demo)
    st.session_state.db = ChatDatabase()

if "rag_pipeline" not in st.session_state:
    st.session_state.rag_pipeline = RAGPipeline()

if "indexed_file_ids" not in st.session_state:
    st.session_state.indexed_file_ids = set()

if "messages" not in st.session_state:
    # Load history from DB
    try:
        history = st.session_state.db.get_history(st.session_state.room_id)
        st.session_state.messages = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in history
        ]
    except Exception as e:
        print(f"Failed to load history: {e}")
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
        print(f"Failed to save message: {e}")

def extract_keywords_with_gemini(prompt):
    """Uses Gemini to extract search keywords from a user prompt."""
    try:
        # Use gemini-2.5-flash as it is available and faster
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
        print(f"Error extracting keywords: {e}")
        # Fallback: Simple split
        return prompt.split()

# --- Authentication & Connection ---
if "gdrive_service" not in st.session_state:
    try:
        # Try silent authentication if token exists
        if os.path.exists('token.pickle'):
            st.session_state.gdrive_service = gdrive_utils.authenticate_gdrive()
            st.toast("Auto-connected to Google Drive!", icon="✅")
    except Exception as e:
        st.error(f"Auto-connect failed: {e}")

# --- Sidebar ---
with st.sidebar:
    st.header("Status & Controls")
    
    # Connection Status
    if "gdrive_service" in st.session_state:
        st.success("✅ Connected to Google Drive")
        if st.button("Reconnect / Switch Account"):
            try:
                # Force re-auth (might need to delete token.pickle manually or modify auth flow)
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                st.session_state.gdrive_service = gdrive_utils.authenticate_gdrive()
                st.rerun()
            except Exception as e:
                st.error(f"Re-connection failed: {e}")
    else:
        st.warning("⚠️ Not Connected")
        if st.button("Connect to Google Drive"):
            try:
                st.session_state.gdrive_service = gdrive_utils.authenticate_gdrive()
                st.rerun()
            except Exception as e:
                st.error(f"Connection failed: {e}")
                st.info("Ensure 'credentials.json' is present.")

    st.markdown("---")
    
    # Indexed Files List
    st.subheader(f"📚 Indexed Documents ({len(st.session_state.indexed_file_ids)})")
    if st.session_state.indexed_file_ids:
        # We don't store names in session state set, maybe we should?
        # For now, just show count or list if we tracked names.
        if st.button("🗑️ Clear Index"):
            st.session_state.rag_pipeline.clear_index()
            st.session_state.indexed_file_ids = set()
            st.success("Memory cleared!")
            st.rerun()
            
        if st.button("📝 Summarize Context"):
             with st.spinner("Summarizing all indexed content..."):
                try:
                    summary = st.session_state.rag_pipeline.summarize()
                    save_message("assistant", f"**Context Summary:**\n\n{summary}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("No documents indexed yet. Ask a question to start searching!")

# --- Chat Logic ---
st.subheader("Chat")

# Display history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input handling
if prompt := st.chat_input("Tanyakan sesuatu (saya akan cari file relevan di Drive)..."):
    # Add user message
    save_message("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process
    with st.chat_message("assistant"):
        status_container = st.status("🤔 Memproses...", expanded=True)
        
        try:
            # 1. Check Connection
            if "gdrive_service" not in st.session_state:
                status_container.error("Please connect to Google Drive first!")
                st.stop()
            
            # 2. Search in Drive
            status_container.write(f"🔍 Mencari dokumen relevan untuk: '{prompt}'...")
            
            # Step 1: Extract keywords
            search_keywords = extract_keywords_with_gemini(prompt)
            status_container.write(f"🔑 Keywords: {', '.join(search_keywords)}")
            
            # Step 2: Search with extracted keywords (AND logic first)
            found_files = gdrive_utils.search_files(st.session_state.gdrive_service, search_keywords, limit=5)
            
            # Step 3: Fallback if no files found (Try broader search OR logic)
            if not found_files and len(search_keywords) > 1:
                status_container.write("⚠️ Pencarian spesifik nihil, mencoba pencarian lebih luas...")
                # Flatten search: try each keyword individually
                broad_files = []
                for kw in search_keywords:
                    res = gdrive_utils.search_files(st.session_state.gdrive_service, kw, limit=2)
                    broad_files.extend(res)
                
                # Remove duplicates
                seen_ids = set()
                for f in broad_files:
                    if f['id'] not in seen_ids:
                        found_files.append(f)
                        seen_ids.add(f['id'])
            
            if not found_files:
                status_container.warning("Tidak ditemukan dokumen yang relevan di Google Drive.")
                # Fallback: Try to answer from existing context if any, or just say sorry
                if not st.session_state.indexed_file_ids:
                    response = "Maaf, saya tidak menemukan dokumen yang relevan dengan pertanyaan Anda di Google Drive, dan belum ada dokumen yang saya ingat."
                    st.markdown(response)
                    save_message("assistant", response)
                    status_container.update(label="Selesai", state="complete", expanded=False)
                    st.stop()
            
            # 3. Download & Index New Files
            new_files_to_index = []
            for f in found_files:
                if f['id'] not in st.session_state.indexed_file_ids:
                    status_container.write(f"⬇️ Mengunduh: {f['name']}...")
                    try:
                        file_path = gdrive_utils.download_file(st.session_state.gdrive_service, f['id'], f['name'], f['mimeType'])
                        if file_path:
                            new_files_to_index.append(file_path)
                            st.session_state.indexed_file_ids.add(f['id'])
                        else:
                            status_container.warning(f"⚠️ Format file tidak didukung: {f['name']}")
                    except Exception as e:
                        print(f"Error downloading {f['name']}: {e}")
                        status_container.warning(f"Gagal mengunduh {f['name']}. Lihat log untuk detail.")
                else:
                    status_container.write(f"✅ Sudah ada di memori: {f['name']}")
            
            if new_files_to_index:
                status_container.write(f"🧠 Membaca {len(new_files_to_index)} dokumen baru...")
                st.session_state.rag_pipeline.index_files(new_files_to_index)
            
            # 4. Generate Answer
            status_container.write("✨ Menyusun jawaban...")
            response = st.session_state.rag_pipeline.ask(prompt)
            
            status_container.update(label="Selesai!", state="complete", expanded=False)
            
            st.markdown(response)
            save_message("assistant", response)

        except Exception as e:
            status_container.error(f"Terjadi kesalahan: {e}")
