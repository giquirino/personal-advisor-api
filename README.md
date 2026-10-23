<div align="center">

# Personal Advisor API

### Projeto Acadêmico de Inteligência Artificial

**Desenvolvido por Giovanna Quirino**<br>
**Curso de Inteligência Artificial — 2026**

Orientador: **Professor Marcelo Bezerra Grilo Junior**<br>
**Escola de Tecnologia — Instituto J&F**

</div>

---

Um assistente pessoal com inteligência artificial para gestão financeira e organização de compromissos, desenvolvido com FastAPI, LangChain e LangGraph.

O aplicativo usa um fluxo multiagente para encaminhar solicitações a agentes especializados em finanças, agenda e perguntas frequentes. As conversas são armazenadas no MongoDB, e seus resumos são indexados no Qdrant para busca semântica entre sessões.

## Funcionalidades

- Orquestração multiagente com LangGraph
- Criação, busca e atualização de transações financeiras e cálculo de saldo
- Criação, consulta, atualização e cancelamento de compromissos persistidos
- Memória de longo prazo das conversas armazenada no MongoDB e indexada no Qdrant
- Busca em perguntas frequentes a partir de PDF, embeddings e Qdrant
- Proteções de entrada e saída contra dados pessoais, injeção de prompt e violações de conformidade
- Modelos Gemini com Groq como alternativa
- Interface de chat acessível pelo navegador
- Ferramentas financeiras disponíveis para clientes MCP via stdio
- Painel de monitoramento do processo para turnos, uso de modelos, latência e custo estimado
- Verificação de evidências nas respostas finais com TypeSafe JEV
- Documentação interativa da API fornecida pelo FastAPI

## Arquitetura

```text
Navegador -> FastAPI /chat -> Proteção de entrada -> Agente roteador
                                            |       |       |
                                            v       v       v
                                       Financeiro Agenda   Perguntas frequentes
                                            |       |       |
                                            v       v       v
                                       PostgreSQL MongoDB  Qdrant
                                            |       |
                                            +---+---+       |
                                                v           |
                                           Orquestrador      |
                                                |           |
                                                +-----+-----+
                                                      v
                                               Proteção de saída
                                                      |
                                                      v
                                            Juiz de evidências (TypeSafe JEV)
                                                      |
                                                      v
                                                  Resposta do chat

Cliente MCP -> servidor stdio -> ferramentas financeiras -> PostgreSQL
Turno de chat -> métricas em memória -> GET /monitor -> painel de monitoramento

Memória de longo prazo: sessões MongoDB -> resumos -> índice semântico Qdrant
Perguntas frequentes: PDF -> ingestão inicial -> índice semântico Qdrant
```

O MongoDB armazena mensagens e resumos das sessões, compromissos e metadados das conversas. O Qdrant permite busca semântica nos resumos e nos trechos das perguntas frequentes.
Os fluxos financeiro e de agenda passam pelo orquestrador; o fluxo de perguntas frequentes se conecta à proteção de saída. O juiz de evidências é executado por último nas respostas que chegam a essa proteção. Solicitações bloqueadas pela proteção de entrada não chamam o juiz.
O servidor MCP é uma entrada separada que reutiliza as mesmas ferramentas financeiras do fluxo de chat.

## Tecnologias

- Python 3.11+
- FastAPI e Uvicorn
- LangChain e LangGraph
- MCP Python SDK
- Google Gemini e Groq
- TypeSafe JEV para verificação de respostas
- PostgreSQL
- MongoDB
- Qdrant
- HTML, CSS, and JavaScript

## Estrutura do projeto

```text
.
|-- .github/
|   |-- pull_request_template.md
|   `-- workflows/
|       `-- ci.yml
|-- .cursor/
|   `-- mcp.json
|-- app/
|   |-- routes/
|   |   |-- chat.py
|   |   |-- monitor.py
|   |   |-- perfil.py
|   |   `-- sessions.py
|   |-- tools/
|   |   |-- agenda.py
|   |   |-- db.py
|   |   |-- faq.py
|   |   |-- financeiro.py
|   |   |-- memoria.py
|   |   `-- perfil.py
|   |-- config.py
|   |-- graph.py
|   |-- guardrail.py
|   |-- ingest_faq.py
|   |-- juiz.py
|   |-- llms.py
|   |-- main.py
|   |-- mcp_server.py
|   |-- memory.py
|   |-- observabilidade.py
|   |-- perfil.py
|   |-- prompts.py
|   |-- schemas.py
|   `-- vectorstore.py
|-- data/
|   `-- FAQ_assessor_v1.1.pdf
|-- frontend/
|   |-- app.js
|   |-- index.html
|   |-- monitor.html
|   |-- perfil.css
|   |-- perfil.html
|   |-- perfil.js
|   `-- style.css
|-- tests/
|   `-- test_integrations.py
|-- .env.example
|-- requirements.txt
`-- README.md
```

## Como começar

### 1. Clone o repositório

```bash
git clone https://github.com/giquirino/personal-advisor-api.git
cd personal-advisor-api
```

### 2. Crie um ambiente virtual

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
python -m pip install -r requirements.txt
```

### 4. Configure o ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
TYPESAFE_API_KEY=your_typesafe_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/database
MONGODB_URI=mongodb://localhost:27017
QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key
FAQ_PDF_PATH=data/FAQ_assessor_v1.1.pdf
```

Não envie o arquivo `.env` nem credenciais reais ao repositório.

### 5. Execute o aplicativo

```bash
python -m uvicorn app.main:app --reload
```

Indexe as perguntas frequentes antes da primeira consulta ou sempre que o PDF mudar:

```bash
python -m app.ingest_faq
```

Acesse os seguintes endereços:

- Interface web: `http://localhost:8000`
- Documentação Swagger: `http://localhost:8000/docs`
- Verificação de saúde: `http://localhost:8000/health`
- Painel de monitoramento: `http://localhost:8000/monitor.html`

O endpoint de monitoramento está disponível em `GET /monitor`. As métricas cobrem o processo atual do servidor e são reiniciadas quando ele é reiniciado. O custo usa preços fixos por token e, portanto, é uma estimativa. Sem `TYPESAFE_API_KEY`, a verificação de evidências retorna uma resposta segura predefinida para mensagens não verificadas.

Para conectar um cliente MCP, configure-o para executar `python -m app.mcp_server` a partir da raiz do projeto. O arquivo `.cursor/mcp.json` já contém essa configuração para o Cursor.
O servidor MCP usa o mesmo `DATABASE_URL` da API e disponibiliza as cinco ferramentas financeiras existentes. Ele não inicia um servidor HTTP.

## Integração contínua

O GitHub Actions instala as dependências, compila a aplicação e os testes e executa os testes automatizados em pull requests e em envios para a branch `main`. Novas pull requests usam o modelo `.github/pull_request_template.md`.

## Endpoints da API

### Enviar uma mensagem

```http
POST /chat
Content-Type: application/json
```

```json
{
  "session_id": "user-session-01",
  "pergunta": "Quanto gastei hoje?"
}
```

Exemplo de resposta:

```json
{
  "resposta": "Seu resumo financeiro atual é...",
  "agentes_chamados": ["roteador", "financeiro", "orquestrador", "juiz:apoiada noul=0.91"]
}
```

### Encerrar e resumir uma sessão

```http
POST /sessions/{session_id}/encerrar?user_id={user_id}
```

Exemplo de resposta:

```json
{
  "session_id": "user-session-01",
  "resumo": "A pessoa revisou as despesas recentes e conversou sobre um plano de economia."
}
```

O parâmetro `user_id` deve corresponder à pessoa proprietária da sessão. Se o endpoint for chamado novamente para uma sessão já encerrada, o resumo retornado será `null`, sem gerar erro.

### Verificar a saúde do aplicativo

```http
GET /health
```

O endpoint verifica as configurações necessárias e a conectividade com MongoDB, PostgreSQL e Qdrant. A resposta segue este contrato:

```json
{
  "status": "ok | degraded",
  "checks": {
    "mongodb": {
      "status": "ok | not_configured | unavailable",
      "message": "Diagnóstico legível sem credenciais."
    }
  }
}
```

`not_configured` indica que falta uma variável obrigatória do `.env`; `unavailable` indica que a variável existe, mas o serviço não pôde ser acessado. As chaves de API são verificadas apenas quanto à presença, sem consumir a cota dos modelos.

## Memória de longo prazo

As mensagens são armazenadas durante a sessão. Quando ela é encerrada, o assistente gera um resumo conciso e o salva no MongoDB.

O agente roteador e os agentes financeiro e de agenda podem buscar resumos de sessões encerradas quando a solicitação atual depende de informações mencionadas anteriormente. O agente de perguntas frequentes não acessa a memória pessoal das conversas.

Os resumos são indexados no Qdrant e recuperados por similaridade semântica. Assim, conceitos relacionados e sinônimos podem localizar memórias relevantes mesmo quando as palavras usadas são diferentes.

## Segurança

- As mensagens são anonimizadas antes de serem processadas pelos agentes especializados.
- As respostas são verificadas quanto a dados sensíveis e conformidade financeira.
- Quando configurada, a verificação final envia a pergunta, a resposta e as evidências das ferramentas ao TypeSafe JEV.
- Tentativas de injeção de prompt e solicitações de credenciais internas são bloqueadas.
- Credenciais de banco de dados e chaves de API devem permanecer no `.env`.
- Este projeto é um assistente educacional e não substitui orientação financeira profissional.

## Status do desenvolvimento

O projeto oferece o fluxo de chat com FastAPI, sessões persistentes, ferramentas financeiras e de agenda, busca em perguntas frequentes, memória de longo prazo, servidor financeiro MCP, monitoramento no processo e verificação de respostas. Os serviços externos precisam estar configurados e disponíveis para a execução completa.
