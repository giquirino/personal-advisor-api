"""Instâncias de LLM compartilhadas pela aplicação."""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq

from app.config import GEMINI_API_KEY, GROQ_API_KEY


llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    top_p=0.95,
    google_api_key=GEMINI_API_KEY,
)

llm_groq = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.7,
    groq_api_key=GROQ_API_KEY,
)

llm_rapido = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.0,
    groq_api_key=GROQ_API_KEY,
)

llm = llm_gemini.with_fallbacks([llm_groq])

faq_embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview",
    google_api_key=GEMINI_API_KEY,
)
