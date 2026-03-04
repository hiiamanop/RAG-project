import logging
import re
import json
from typing import List, Dict, Any, Tuple
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.generators.google_ai import GoogleAIGeminiGenerator
from haystack.utils import Secret
from haystack.dataclasses import ByteStream

from src.core.config import settings
from src.services.search import SearchService

logger = logging.getLogger(__name__)

class ChatAgent:
    def __init__(self):
        self.search_service = SearchService()
        
        # Initialize Gemini Generator
        self.llm = GoogleAIGeminiGenerator(
            model="gemini-2.5-flash",
            api_key=Secret.from_token(settings.GOOGLE_API_KEY)
        )

        # Regex patterns for Pipeline 1 (Fallback)
        self.drive_keywords = [
            r"baca file",
            r"cari di drive",
            r"dokumen mengenai",
            r"file terkait",
            r"carikan data",
            r"tentang dokumen",
            r"analisa file",
            r"berikan saya summary dari",
            r"tolong bacakan file",
        ]

    def analyze_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyze user intent using LLM (Gemini) to determine the best pipeline.
        Returns dict with intent, keywords, entities, confidence.
        """
        prompt = f"""
        Analyze the following user query to determine the user's intent and extract relevant search parameters.
        
        Query: "{query}"
        
        Context: The user is interacting with an AI assistant that has access to their Google Drive files and the Internet.
        
        Determine:
        1. Intent:
           - "search_drive": If the user wants to find, read, summarize, or analyze specific files/documents in their Drive (e.g., "find the contract", "summarize the meeting notes", "what does the report say about X", "baca file ...").
           - "search_internet": If the user asks for current events, external facts, or general information likely not in their private files (e.g., "weather today", "latest stock price", "who is the president of X").
           - "general_chat": If the user is greeting, thanking, or asking general questions that don't require external data (e.g., "hello", "help me write an email", "what is 2+2").
        2. Keywords: Extract 1-3 specific search terms for finding relevant documents/info. Ignore stop words.
        3. Entities: Identify key entities (people, organizations, dates, filenames).
        4. Confidence: Score (0.0-1.0) indicating how sure you are about the intent.
        
        Return JSON object only:
        {{
          "intent": "search_drive" | "search_internet" | "general_chat",
          "keywords": ["keyword1", "keyword2"],
          "entities": ["entity1", "entity2"],
          "confidence": 0.95
        }}
        """
        
        try:
            logger.info(f"Analyzing intent for query: {query}")
            result = self.llm.run(parts=[prompt])
            response_text = result["replies"][0]
            
            # Clean and parse JSON
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            
            # Normalize intent to match our pipeline names: 'drive', 'internet', 'llm'
            intent_map = {
                "search_drive": "drive",
                "search_internet": "internet",
                "general_chat": "llm"
            }
            data["pipeline"] = intent_map.get(data.get("intent"), "llm")
            
            logger.info(f"Intent Analysis Result: {data}")
            return data
            
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            # Fallback to regex/basic logic
            return self._fallback_intent_analysis(query)

    def _fallback_intent_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback logic using Regex if LLM fails."""
        logger.warning("Using fallback regex for intent analysis.")
        for pattern in self.drive_keywords:
            if re.search(pattern, query, re.IGNORECASE):
                return {
                    "intent": "search_drive", 
                    "pipeline": "drive", 
                    "keywords": query.split(), 
                    "entities": [], 
                    "confidence": 0.5
                }
        return {
            "intent": "general_chat", 
            "pipeline": "llm", 
            "keywords": [], 
            "entities": [], 
            "confidence": 0.5
        }

    def decide_pipeline(self, query: str) -> str:
        """
        Legacy method. Use analyze_intent instead.
        """
        analysis = self.analyze_intent(query)
        return analysis["pipeline"]

    def generate_native_response(self, query: str) -> Tuple[str, float]:
        """
        Pipeline 2: LLM Native Response with Confidence Score.
        Returns: (answer, confidence)
        """
        prompt_template = """
        You are a helpful AI assistant. Answer the following question based on your internal knowledge.
        
        Question: {{ query }}
        
        Provide your response in JSON format with the following keys:
        - "answer": The answer to the question (can be markdown).
        - "confidence": A float between 0.0 and 1.0 indicating your confidence in the answer.
        
        JSON Response:
        """
        
        try:
            builder = PromptBuilder(template=prompt_template)
            prompt = builder.run(query=query)
            result = self.llm.run(parts=[prompt["prompt"]])
            response_text = result["replies"][0]
            
            # Clean formatting if wrapped in code blocks
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            try:
                data = json.loads(clean_text)
                return data.get("answer", "No answer generated."), float(data.get("confidence", 0.0))
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                logger.warning(f"Failed to parse JSON response: {response_text}")
                return response_text, 0.5 # Default low confidence
                
        except Exception as e:
            logger.error(f"Native LLM generation failed: {e}")
            return "Error generating response.", 0.0

    def generate_internet_response(self, query: str) -> Tuple[str, List[Dict]]:
        """
        Pipeline 3: Internet Search + LLM Synthesis.
        Returns: (answer, search_results)
        """
        # 1. Search
        search_results = self.search_service.search(query, max_results=settings.MAX_SEARCH_RESULTS)
        
        if not search_results:
            return "Maaf, saya tidak dapat menemukan informasi yang relevan di internet saat ini.", []

        # 2. Synthesize
        context_str = "\n\n".join([f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}" for r in search_results])
        
        prompt_template = """
        You are a helpful AI assistant. Answer the following question based ONLY on the provided search results.
        If the search results do not contain the answer, say "I cannot answer based on the search results."
        
        Search Results:
        {{ context }}
        
        Question: {{ query }}
        
        Answer (in Markdown):
        """
        
        try:
            builder = PromptBuilder(template=prompt_template)
            prompt = builder.run(query=query, context=context_str)
            result = self.llm.run(parts=[prompt["prompt"]])
            answer = result["replies"][0]
            return answer, search_results
        except Exception as e:
            logger.error(f"Internet RAG failed: {e}")
            return "Error synthesizing internet search results.", []
