import os
import io
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Scope for read-only access to Drive
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def authenticate_gdrive():
    """Authenticates the user and returns the Drive service."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("credentials.json not found. Please follow the setup instructions.")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)
    return service

def list_files(service, query=None, limit=10):
    """Lists files from Google Drive matching the query."""
    # If query is None, list everything (folders excluded typically by mimeType check if needed, but let's be broad)
    # We want to avoid folders though.
    base_query = "mimeType != 'application/vnd.google-apps.folder'"
    
    if query:
        final_query = f"({base_query}) and ({query})"
    else:
        final_query = base_query
        
    results = service.files().list(
        q=final_query,
        pageSize=limit,
        fields="nextPageToken, files(id, name, mimeType)").execute()
    items = results.get('files', [])
    return items

def search_files(service, search_term, limit=5):
    """
    Searches for files containing the search term(s).
    Supports string input (exact phrase) or list of strings (keywords combination).
    """
    if isinstance(search_term, str):
        # Escape single quotes
        term = search_term.replace("'", "\\'")
        # Broad search: name or fullText
        query = f"name contains '{term}' or fullText contains '{term}'"
    elif isinstance(search_term, list):
        # Construct AND query for all keywords
        # (name contains 'k1' and name contains 'k2' ...) or (fullText contains 'k1' and fullText contains 'k2' ...)
        
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

    print(f"DEBUG: Drive Query: {query}")
    return list_files(service, query=query, limit=limit)

import mimetypes

# ... (imports)

def download_file(service, file_id, file_name, mime_type):
    """Downloads a file from Google Drive. Exports Google Docs/Sheets/Slides to appropriate formats."""
    print(f"DEBUG: Downloading {file_name} ({mime_type})")
    
    request = None
    export_mime_type = None
    
    # Map Google Apps types to export types
    if "application/vnd.google-apps.document" in mime_type:
        export_mime_type = 'application/pdf'
        if not file_name.endswith('.pdf'): file_name += ".pdf"
    elif "application/vnd.google-apps.spreadsheet" in mime_type:
        export_mime_type = 'text/csv'
        if not file_name.endswith('.csv'): file_name += ".csv"
    elif "application/vnd.google-apps.presentation" in mime_type:
        export_mime_type = 'application/pdf'
        if not file_name.endswith('.pdf'): file_name += ".pdf"
    elif "application/vnd.google-apps.script" in mime_type:
        export_mime_type = 'application/json' # Scripts as JSON
        if not file_name.endswith('.json'): file_name += ".json"
    elif "application/vnd.google-apps.drawing" in mime_type:
        export_mime_type = 'application/pdf'
        if not file_name.endswith('.pdf'): file_name += ".pdf"
    elif mime_type.startswith("application/vnd.google-apps."):
        # Other Google Apps files (Forms, Sites, Maps, etc.) - cannot be easily exported/downloaded
        print(f"WARNING: Skipping unsupported Google Apps file: {file_name} ({mime_type})")
        return None

    # Prepare request
    if export_mime_type:
        request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
    else:
        # For binary files, ensure extension exists if possible
        root, ext = os.path.splitext(file_name)
        if not ext:
            guessed_ext = mimetypes.guess_extension(mime_type)
            if guessed_ext:
                file_name += guessed_ext
        
        request = service.files().get_media(fileId=file_id)
    
    # Execute download
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    # Save to local directory
    os.makedirs("downloads", exist_ok=True)
    file_path = os.path.join("downloads", file_name)
    with open(file_path, "wb") as f:
        f.write(fh.getbuffer())
    return file_path
