import re
import uuid

from app.llms import llm_rapido as llm

# ==============================================================================
# PII — padrões usados tanto na entrada quanto na saída
# ==============================================================================
PII = [
    ("CPF",      r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),
    ("CNPJ",     r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"),
    ("TELEFONE", r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}"),
    ("EMAIL",    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    ("CONTA",    r"\d{4,6}-\d{1}"),
    ("CARTAO",   r"\d{4}\s?\d{4}\s?\d{4}\s?\d{4}"),
]

# ==============================================================================
# HELPERS
# ==============================================================================
def _bloquear(motivo, mensagem):
    return {"bloqueado": True, "motivo": motivo, "mensagem": mensagem}

def _aprovado():
    return {"bloqueado": False, "motivo": "aprovado", "mensagem": ""}

def _saida_ok(conteudo):
    return {"bloqueado": False, "motivo": "saida_revisada", "conteudo": conteudo}

# ==============================================================================
# ANONIMIZAÇÃO
# ==============================================================================
def anonimizar_entrada(texto):
    mapa = {}

    for tipo, padrao in PII:
        matches = re.findall(padrao, texto)
        for valor in matches:
            token = f"[PII_{tipo}_{uuid.uuid4().hex[:6]}]"
            mapa[token] = valor
            texto = texto.replace(valor, token, 1)

    return texto, mapa

def desanonimizar_saida(texto, mapa, restaurar=False):
    """Resolve tokens de PII na saída. Por padrão omite — não repete dado pessoal."""
    for token, valor in mapa.items():
        if token in texto:
            substituto = valor if restaurar else f"[{token.split('_')[1]} OMITIDO]"
            texto = texto.replace(token, substituto)
    return texto

# ==============================================================================
# GUARDRAIL DE ENTRADA
# ==============================================================================
_PADROES_INJECAO = [
    r"ignore\s+(as\s+)?instru[çc][oõ]es",
    r"ignore\s+previous\s+instructions",
    r"forget\s+your\s+instructions",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+)?",
    r"pretend\s+(you\s+are|to\s+be)",
    r"jailbreak",
    r"dan\s+mode",
    r"modo\s+irrestrito",
    r"system\s*prompt",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"###\s*instruction",
    r"override\s+(your\s+)?instructions",
    r"desconsider[ea]\s+(suas\s+)?instru[çc][oõ]es",
]

_KEYWORDS_DADOS_INTERNOS = [
    "prompt do sistema", "system prompt", "suas instruções", "your instructions",
    "variável de ambiente", "chave de api", "api key", "senha do sistema",
    "token de acesso", "banco de dados interno", "tabela interna",
    "dados de outros clientes", "lista de clientes", "credenciais",
]

# Uma chamada LLM para as 5 categorias semânticas
_PROMPT_CLASSIFICADOR = """\
Você é um classificador de segurança de um sistema de assessoria financeira e agenda.
Classifique a mensagem em UMA categoria. Responda SOMENTE:

CATEGORIA: [categoria]
JUSTIFICATIVA: [uma linha]

Categorias:
APROVADO        - mensagem legítima sobre finanças (informativa), agenda ou operações
OFENSIVO        - xingamentos, assédio, discurso de ódio
PERIGOSO        - instruções que causam dano físico, psicológico ou coletivo
ILICITO         - pedido de auxílio para atividades ilegais ou fraudulentas
POLITICO        - opiniões ou debates políticos, partidos, eleições
INDICACAO_INVEST - recomendação direta de ativo específico para comprar/vender/manter

Mensagem: {mensagem}
"""

_RESPOSTAS_BLOQUEIO = {
    "OFENSIVO":         ("conteudo_ofensivo",      "Por favor, mantenha um tom respeitoso para que eu possa te ajudar."),
    "PERIGOSO":         ("pedido_perigoso",         "Não posso ajudar com esse tipo de solicitação."),
    "ILICITO":          ("pedido_ilicito",           "Não posso auxiliar com atividades ilegais ou irregulares."),
    "POLITICO":         ("pergunta_politica",        "Não me envolvo em temas políticos. Posso ajudar com finanças ou sua agenda."),
    "INDICACAO_INVEST": ("indicacao_investimento",   "Por regulação, não forneço indicações diretas de ativos. Posso explicar classes de investimento ou agendar uma reunião com seu assessor."),
}

def guardrail_entrada(mensagem_anonimizada):
    """
    Executa as verificações de entrada em ordem de custo crescente:
    determinístico primeiro, LLM só se necessário.
    Retorna dict com bloqueado, motivo e mensagem.
    """
    # 1. Prompt injection
    for padrao in _PADROES_INJECAO:
        if re.search(padrao, mensagem_anonimizada, re.IGNORECASE):
            return _bloquear("prompt_injection", "Não consigo processar essa solicitação.")

    # 2. Tentativa de acesso a dados internos
    texto_lower = mensagem_anonimizada.lower()
    for kw in _KEYWORDS_DADOS_INTERNOS:
        if kw in texto_lower:
            return _bloquear("acesso_dados_internos", "Não tenho como compartilhar informações internas do sistema.")

    # 3. Classificação semântica via LLM (ofensivo, perigoso, ilícito, político, indicação)
    resposta = llm.invoke(_PROMPT_CLASSIFICADOR.format(mensagem=mensagem_anonimizada)).content

    categoria = "APROVADO"
    for linha in resposta.splitlines():
        if linha.strip().upper().startswith("CATEGORIA:"):
            categoria = linha.split(":", 1)[1].strip().upper()
            break

    if categoria in _RESPOSTAS_BLOQUEIO:
        motivo, mensagem = _RESPOSTAS_BLOQUEIO[categoria]
        return _bloquear(motivo, mensagem)

    return _aprovado()

# ==============================================================================
# GUARDRAIL DE SAÍDA
# ==============================================================================
_PROMPT_COMPLIANCE = """\
Você é um revisor de compliance para assessoria financeira regulada pela CVM e ANBIMA.
Corrija a resposta SOMENTE se ela garantir rentabilidade futura, recomendar ativo específico
sem disclaimer de risco, ou afirmar certeza sobre comportamento futuro do mercado.
Se estiver adequada, repita-a sem alterações.

Responda SOMENTE:
STATUS: APROVADO ou CORRIGIDO
RESPOSTA:
[texto final]

Resposta para revisar:
{resposta}
"""

def guardrail_saida(resposta, mapa_pii, restaurar_pii=False):
    """
    Limpa e revisa a resposta do especialista antes de entregar ao usuário.
    Nunca bloqueia — sempre retorna o texto revisado em 'conteudo'.
    """
    # 1. Remove PII que o modelo tenha gerado
    for tipo, padrao in PII:
        resposta = re.sub(padrao, f"[{tipo} OMITIDO]", resposta)

    # 2. Resolve tokens de PII da entrada
    resposta = desanonimizar_saida(resposta, mapa_pii, restaurar=restaurar_pii)

    # 3. Revisão de compliance financeiro
    saida = llm.invoke(_PROMPT_COMPLIANCE.format(resposta=resposta)).content.strip()
    if "RESPOSTA:" in saida:
        resposta = saida.split("RESPOSTA:", 1)[1].strip() or resposta

    return _saida_ok(resposta)
