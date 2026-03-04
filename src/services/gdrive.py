import os
import io
import pickle
import logging
from typing import List, Optional, Union, Dict, Any
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaIoBaseDownload
import mimetypes
from src.core.config import settings

logger = logging.getLogger(__name__)

# Scope for read-only access to Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GDriveService:
    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self) -> Resource:
        """Authenticates the user and returns the Drive service."""
        creds = None
        
        token_path = settings.TOKEN_PATH
        creds_path = settings.CREDENTIALS_PATH

        if os.path.exists(token_path):
            try:
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                logger.error(f"Error loading token: {e}")

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                     logger.error(f"Error refreshing token: {e}")
                     creds = None
            
            if not creds:
                if not os.path.exists(creds_path):
                    raise FileNotFoundError(f"{creds_path} not found. Please follow the setup instructions.")
                
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                # In a real server environment, run_local_server might not work headless.
                # For this local app, it's fine.
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)

        return build('drive', 'v3', credentials=creds)

    def list_files(self, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Lists files from Google Drive matching the query."""
        base_query = "mimeType != 'application/vnd.google-apps.folder'"
        
        if query:
            final_query = f"({base_query}) and ({query})"
        else:
            final_query = base_query
            
        results = self.service.files().list(
            q=final_query,
            pageSize=limit,
            fields="nextPageToken, files(id, name, mimeType)").execute()
        return results.get('files', [])

    def search_files(self, search_term: Union[str, List[str]], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Searches for files containing the search term(s).
        """
        if isinstance(search_term, str):
            term = search_term.replace("'", "\\'")
            query = f"name contains '{term}' or fullText contains '{term}'"
        elif isinstance(search_term, list):
            name_conditions = []
            fulltext_conditions = []
            
            for term in search_term:
                t = term.replace("'", "\\'")
                name_conditions.append(f"name contains '{t}'")
                fulltext_conditions.append(f"fullText contains '{t}'")
                
            name_query = " and ".join(name_conditions)
            fulltext_query = " and ".join(fulltext_conditions)
            
            query = f"({name_query}) or ({fulltext_query})"
        else:
            return []

        logger.debug(f"Drive Query: {query}")
        return self.list_files(query=query, limit=limit)

    def download_file(self, file_id: str, file_name: str, mime_type: str) -> Optional[str]:
        """Downloads a file from Google Drive."""
        logger.info(f"Downloading {file_name} ({mime_type})")
        
        request = None
        export_mime_type = None
        final_file_name = file_name
        
        # Map Google Apps types
        if "application/vnd.google-apps.document" in mime_type:
            export_mime_type = 'application/pdf'
            if not final_file_name.endswith('.pdf'): final_file_name += ".pdf"
        elif "application/vnd.google-apps.spreadsheet" in mime_type:
            export_mime_type = 'text/csv'
            if not final_file_name.endswith('.csv'): final_file_name += ".csv"
        elif "application/vnd.google-apps.presentation" in mime_type:
            export_mime_type = 'application/pdf'
            if not final_file_name.endswith('.pdf'): final_file_name += ".pdf"
        elif "application/vnd.google-apps.script" in mime_type:
            export_mime_type = 'application/json'
            if not final_file_name.endswith('.json'): final_file_name += ".json"
        elif "application/vnd.google-apps.drawing" in mime_type:
            export_mime_type = 'application/pdf'
            if not final_file_name.endswith('.pdf'): final_file_name += ".pdf"
        elif mime_type.startswith("application/vnd.google-apps."):
            logger.warning(f"Skipping unsupported Google Apps file: {file_name} ({mime_type})")
            return None

        try:
            if export_mime_type:
                request = self.service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            else:
                # Binary files
                root, ext = os.path.splitext(final_file_name)
                if not ext:
                    guessed_ext = mimetypes.guess_extension(mime_type)
                    if guessed_ext:
                        final_file_name += guessed_ext
                
                request = self.service.files().get_media(fileId=file_id)
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            # Save
            downloads_dir = settings.DOWNLOADS_DIR
            os.makedirs(downloads_dir, exist_ok=True)
            file_path = os.path.join(downloads_dir, final_file_name)
            
            with open(file_path, "wb") as f:
                f.write(fh.getbuffer())
                
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return None
