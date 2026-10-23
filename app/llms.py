"""InstÃƒÆ’Ã‚Â¢ncias de LLM compartilhadas pela aplicaÃƒÆ’Ã‚Â§ÃƒÆ’Ã‚Â£o."""

from langchain_google_genai import ChatGoogleGenerativeAI
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
    model="openai/gpt-oss-20b",
    temperature=0.0,
    groq_api_key=GROQ_API_KEY,
)

llm = llm_gemini.with_fallbacks([llm_groq])
