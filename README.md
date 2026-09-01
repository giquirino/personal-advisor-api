<div align="center">

# Personal Advisor API

### Artificial Intelligence Academic Project

**Developed by Giovanna Quirino**<br>
**Artificial Intelligence Course — 2026**

Academic advisor: **Professor Marcelo Bezerra Grilo Junior**<br>
**School of Technology — Instituto J&F**

</div>

---

An AI-powered personal assistant for financial management and scheduling, built with FastAPI, LangChain, and LangGraph.

The application uses a multi-agent workflow to route user requests to specialized financial, agenda, and FAQ agents. Conversation data is persisted in MongoDB, while summaries are indexed in Qdrant for semantic retrieval across sessions.

## Features

- Multi-agent orchestration with LangGraph
- Financial transaction creation, search, balance calculation, and updates
- Persistent calendar event creation, listing, updating, and cancellation
- Long-term conversation memory persisted in MongoDB and indexed in Qdrant
- FAQ retrieval from a PDF using embeddings and Qdrant
- Input and output guardrails for PII, prompt injection, and compliance
- Gemini models with Groq fallback
- Browser-based chat interface
- Interactive API documentation provided by FastAPI

## Architecture

```text
User -> FastAPI /chat -> Input guardrail -> Router agent
                                           |       |       |
                                           v       v       v
                                      Financial  Agenda   FAQ
                                           |       |       |
                                           v       v       v
                                      PostgreSQL MongoDB  Qdrant
                                           |       |
                                           +---+---+
                                               v
                                      Orchestrator agent
                                               |
                                               v
                                        Output guardrail

Long-term memory: MongoDB sessions -> summaries -> Qdrant semantic index
FAQ knowledge: PDF -> one-time ingestion -> Qdrant semantic index
```

MongoDB stores session messages, summaries, calendar events, and conversation metadata. Qdrant provides semantic retrieval for both conversation summaries and FAQ chunks.

## Technology Stack

- Python 3.11+
- FastAPI and Uvicorn
- LangChain and LangGraph
- Google Gemini and Groq
- PostgreSQL
- MongoDB
- Qdrant
- HTML, CSS, and JavaScript

## Project Structure

```text
.
|-- app/
|   |-- routes/
|   |   |-- chat.py
|   |   `-- sessions.py
|   |-- tools/
|   |   |-- agenda.py
|   |   |-- db.py
|   |   |-- faq.py
|   |   |-- financeiro.py
|   |   `-- memoria.py
|   |-- config.py
|   |-- graph.py
|   |-- guardrail.py
|   |-- llms.py
|   |-- main.py
|   |-- memory.py
|   |-- prompts.py
|   `-- schemas.py
|-- data/
|   `-- FAQ_assessor_v1.1.pdf
|-- frontend/
|   |-- app.js
|   |-- index.html
|   `-- style.css
|-- requirements.txt
`-- README.md
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/giquirino/personal-advisor-api.git
cd personal-advisor-api
```

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure the environment

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/database
MONGODB_URI=mongodb://localhost:27017
QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key
FAQ_PDF_PATH=data/FAQ_assessor_v1.1.pdf
```

Never commit the `.env` file or real credentials.

### 5. Run the application

```bash
python -m uvicorn app.main:app --reload
```

Index the FAQ once before the first FAQ query, or whenever the PDF changes:

```bash
python -m app.ingest_faq
```

Open the following URLs:

- Web interface: `http://localhost:8000`
- Swagger documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## API Endpoints

### Send a message

```http
POST /chat
Content-Type: application/json
```

```json
{
  "session_id": "user-session-01",
  "pergunta": "How much did I spend today?"
}
```

Example response:

```json
{
  "resposta": "Your current financial summary is...",
  "agentes_chamados": ["roteador", "financeiro", "orquestrador"]
}
```

### Close and summarize a session

```http
POST /sessions/{session_id}/encerrar
```

Example response:

```json
{
  "session_id": "user-session-01",
  "resumo": "The user reviewed recent expenses and discussed a savings plan."
}
```

Calling this endpoint again for an already closed session returns `null` as the summary without raising an error.

### Check application health

```http
GET /health
```

## Long-Term Memory

Messages are stored during an active session. When the session is closed, the assistant generates a concise summary and saves it in MongoDB.

The router, financial agent, and agenda agent can search summaries from previous closed sessions when the current request depends on information the user mentioned earlier. The FAQ agent does not access personal conversation memory.

Conversation summaries are indexed in Qdrant and retrieved through semantic similarity, allowing related concepts and synonyms to find relevant memories even when the wording differs.

## Security Notes

- Personal data is anonymized before being sent to the models.
- Responses are checked for sensitive data and financial compliance.
- Prompt injection and requests for internal credentials are blocked.
- Database credentials and API keys must remain in `.env`.
- This project is an educational assistant and does not replace professional financial advice.

## Development Status

The project currently supports the full FastAPI workflow, persistent sessions, financial tools, calendar tools, FAQ retrieval, and long-term memory. External services must be configured and available for end-to-end operation.
