import os
import pandas as pd
from typing import List, Union
from pathlib import Path
import io
import logging

from haystack import Pipeline, component, Document
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.converters import PyPDFToDocument, TextFileToDocument
from haystack.components.routers import FileTypeRouter
from haystack.components.joiners import DocumentJoiner
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.components.embedders import SentenceTransformersDocumentEmbedder, SentenceTransformersTextEmbedder
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.generators.google_ai import GoogleAIGeminiGenerator
from haystack.dataclasses import ByteStream
from haystack.utils import Secret
from src.core.config import settings

logger = logging.getLogger(__name__)

@component
class TableToDocument:
    """
    A component to convert Excel and CSV files to Haystack Documents using pandas.
    """
    @component.output_types(documents=List[Document])
    def run(self, sources: List[Union[str, Path, ByteStream]]):
        documents = []
        for source in sources:
            try:
                # Handle different input types
                if isinstance(source, ByteStream):
                    # For ByteStream, we need to handle bytes directly
                    source_data = io.BytesIO(source.data)
                    file_path = source.meta.get("file_path", "unknown")
                    file_name = source.meta.get("name", "unknown")
                elif isinstance(source, Path):
                    source_data = source
                    file_path = str(source)
                    file_name = source.name
                else:
                    source_data = source
                    file_path = str(source)
                    file_name = file_path.split("/")[-1]

                # Determine file type based on extension
                if file_name.lower().endswith('.csv'):
                    df = pd.read_csv(source_data)
                    # Chunking logic for CSV
                    chunk_size = 50
                    for i in range(0, len(df), chunk_size):
                        chunk = df.iloc[i:i+chunk_size]
                        try:
                            content = chunk.to_markdown(index=False)
                        except ImportError:
                            content = chunk.to_string(index=False)
                        
                        full_content = f"File: {file_name}\nFormat: CSV\n\n{content}"
                        documents.append(Document(content=full_content, meta={"file_path": file_path, "name": file_name, "row_start": i}))
                else:
                    # Assume Excel for .xlsx, .xls, etc.
                    xls = pd.ExcelFile(source_data)
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet_name)
                        # Chunking logic for Excel
                        chunk_size = 50
                        for i in range(0, len(df), chunk_size):
                            chunk = df.iloc[i:i+chunk_size]
                            try:
                                table_text = chunk.to_markdown(index=False)
                            except ImportError:
                                table_text = chunk.to_string(index=False)
                            
                            full_content = f"File: {file_name}\nSheet: {sheet_name}\n\n{table_text}"
                            documents.append(Document(content=full_content, meta={"file_path": file_path, "name": file_name, "sheet": sheet_name, "row_start": i}))
                    
            except Exception as e:
                logger.error(f"Error converting table file {source}: {e}")
        return {"documents": documents}

class RAGService:
    def __init__(self):
        self.document_store = InMemoryDocumentStore()
        self.indexing_pipeline = Pipeline()
        self.rag_pipeline = Pipeline()
        self._setup_indexing_pipeline()
        self._setup_rag_pipeline()

    def _setup_indexing_pipeline(self):
        # Router to handle different file types
        file_router = FileTypeRouter(mime_types=[
            "application/pdf", 
            "text/plain", 
            "text/csv", 
            "application/json", 
            "text/markdown",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ])
        
        # Converters
        pdf_converter = PyPDFToDocument()
        text_converter = TextFileToDocument()
        table_converter = TableToDocument()
        
        # Joiners
        text_joiner = DocumentJoiner()
        final_joiner = DocumentJoiner()
        
        cleaner = DocumentCleaner()
        splitter = DocumentSplitter(split_by="word", split_length=500, split_overlap=50)
        embedder = SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
        writer = DocumentWriter(document_store=self.document_store)
        
        # Add components
        self.indexing_pipeline.add_component("router", file_router)
        self.indexing_pipeline.add_component("pdf_converter", pdf_converter)
        self.indexing_pipeline.add_component("text_converter", text_converter)
        self.indexing_pipeline.add_component("table_converter", table_converter)
        self.indexing_pipeline.add_component("text_joiner", text_joiner)
        self.indexing_pipeline.add_component("final_joiner", final_joiner)
        self.indexing_pipeline.add_component("cleaner", cleaner)
        self.indexing_pipeline.add_component("splitter", splitter)
        self.indexing_pipeline.add_component("embedder", embedder)
        self.indexing_pipeline.add_component("writer", writer)
        
        # Connections
        # Route PDF
        self.indexing_pipeline.connect("router.application/pdf", "pdf_converter.sources")
        
        # Route Text
        self.indexing_pipeline.connect("router.text/plain", "text_converter.sources")
        self.indexing_pipeline.connect("router.application/json", "text_converter.sources")
        self.indexing_pipeline.connect("router.text/markdown", "text_converter.sources")
        
        # Route Table (Excel & CSV)
        self.indexing_pipeline.connect("router.application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "table_converter.sources")
        self.indexing_pipeline.connect("router.text/csv", "table_converter.sources")
        
        # Text Processing Flow (PDF + Text)
        self.indexing_pipeline.connect("pdf_converter", "text_joiner")
        self.indexing_pipeline.connect("text_converter", "text_joiner")
        
        self.indexing_pipeline.connect("text_joiner", "cleaner")
        self.indexing_pipeline.connect("cleaner", "splitter")
        
        # Final Join (Processed Text + Raw Table Chunks)
        self.indexing_pipeline.connect("splitter", "final_joiner")
        self.indexing_pipeline.connect("table_converter", "final_joiner")
        
        self.indexing_pipeline.connect("final_joiner", "embedder")
        self.indexing_pipeline.connect("embedder", "writer")

    def _setup_rag_pipeline(self):
        # Components
        text_embedder = SentenceTransformersTextEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
        retriever = InMemoryEmbeddingRetriever(document_store=self.document_store, top_k=20)
        
        template = """
        Anda adalah asisten analisis data cerdas yang membantu menjawab pertanyaan berdasarkan dokumen yang diberikan.
        Tugas Anda adalah memberikan jawaban yang LENGKAP, DETAIL, dan AKURAT berdasarkan konteks.
        
        Instruksi:
        1. Baca semua konteks dengan teliti.
        2. Jika ada tabel, perhatikan header dan nilai-nilainya.
        3. Jika pertanyaan meminta ringkasan atau detail tertentu, berikan semua informasi yang relevan.
        4. Jangan menyingkat informasi penting.
        5. Jika konteks tidak memuat informasi yang cukup, katakan "Saya tidak menemukan informasi tersebut dalam dokumen".
        6. Gunakan Bahasa Indonesia yang formal dan jelas.
        
        Context:
        {% for document in documents %}
            {{ document.content }}
        {% endfor %}
        
        Question: {{ question }}
        Answer:
        """
        prompt_builder = PromptBuilder(template=template)
        
        # Gemini Generator
        # Using 'gemini-2.5-flash' which is the latest available model for the key
        generator = GoogleAIGeminiGenerator(model="gemini-2.5-flash", api_key=Secret.from_token(settings.GOOGLE_API_KEY))
        
        # Pipeline connection
        self.rag_pipeline.add_component("text_embedder", text_embedder)
        self.rag_pipeline.add_component("retriever", retriever)
        self.rag_pipeline.add_component("prompt_builder", prompt_builder)
        self.rag_pipeline.add_component("llm", generator)
        
        self.rag_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        self.rag_pipeline.connect("retriever", "prompt_builder.documents")
        self.rag_pipeline.connect("prompt_builder", "llm")

    def index_files(self, file_paths):
        """Indexes a list of files."""
        # The router will distribute files to correct converters
        self.indexing_pipeline.run({"router": {"sources": file_paths}})

    def ask(self, query):
        """Runs the RAG pipeline."""
        result = self.rag_pipeline.run({
            "text_embedder": {"text": query},
            "prompt_builder": {"question": query}
        })
        return result["llm"]["replies"][0]

    def summarize(self):
        """Summarizes all indexed documents."""
        # Retrieve all documents
        docs = self.document_store.filter_documents()
        
        if not docs:
            return "Belum ada dokumen yang diindeks. Silakan pilih dan indeks file terlebih dahulu."
            
        # Concatenate content
        full_text = "\n\n".join([d.content for d in docs])
        
        prompt = """
        Buatlah ringkasan yang komprehensif dan terstruktur dari dokumen-dokumen berikut.
        Identifikasi poin-poin utama, kesimpulan, dan informasi penting lainnya.
        Gunakan Bahasa Indonesia yang baik.
        
        Dokumen:
        """ + full_text + """
        
        Ringkasan:
        """
        
        generator = self.rag_pipeline.get_component("llm")
        # GoogleAIGeminiGenerator expects 'parts'
        result = generator.run(parts=[prompt])
        return result["replies"][0]

    def clear_index(self):
        """Clears the document store."""
        docs = self.document_store.filter_documents()
        ids = [d.id for d in docs]
        if ids:
            self.document_store.delete_documents(ids)
