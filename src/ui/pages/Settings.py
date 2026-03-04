import streamlit as st
import os
from src.services.gdrive import GDriveService
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)

st.title("⚙️ Settings")

# Connection Status
st.header("Google Drive Connection")

if "gdrive_wrapper" not in st.session_state:
    st.session_state.gdrive_wrapper = GDriveService()

if "gdrive_connected" not in st.session_state:
    if st.session_state.gdrive_wrapper.service:
        st.session_state.gdrive_connected = True
    else:
        st.session_state.gdrive_connected = False

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
if "indexed_file_ids" not in st.session_state:
    st.session_state.indexed_file_ids = set()

st.header(f"📚 Knowledge Base ({len(st.session_state.indexed_file_ids)} documents)")

if st.session_state.indexed_file_ids:
    if st.button("🗑️ Clear Index"):
        if "rag_service" in st.session_state:
            st.session_state.rag_service.clear_index()
            st.session_state.indexed_file_ids = set()
            st.success("Memory cleared!")
            st.rerun()
        else:
            st.error("RAG Service not initialized.")
            
    if st.button("📝 Summarize Context"):
         with st.spinner("Summarizing all indexed content..."):
            try:
                if "rag_service" in st.session_state:
                    summary = st.session_state.rag_service.summarize()
                    st.info(f"**Context Summary:**\n\n{summary}")
                else:
                     st.error("RAG Service not initialized.")
            except Exception as e:
                st.error(f"Error: {e}")
else:
    st.info("No documents indexed yet. Ask a question in the Chat to start searching!")
