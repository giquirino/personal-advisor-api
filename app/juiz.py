"""
Juiz de fidelidade. Na ordem desta aula ele fala por último.
Quem decide é o JEV: choice e noul, sem redação.
A frase fixa, quando entra, é deste arquivo.
"""
import json
import urllib.error
import urllib.request

from app.config import TYPESAFE_API_KEY

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODELO = "jev-latest"
LIMIAR = 0.70
FRASE_SEGURA = "Não tenho evidência para afirmar isso."

REGRAS = (
    "A pergunta do usuário também é evidência do que ele disse que fez. "
    "Somas, contagens, datas convertidas para o horário de Brasília e "
    "reformatação de valores tirados da evidência contam como apoiada. "
    "Esclarecimento, saudação, oferta de ajuda, sugestão de próximo passo "
    "e ausência de registro contam como apoiada. "
    "Opinião do usuário pode ser citada como fala dele. "
    "A moeda de cada valor é a que aparece no source_text ou na fala do usuário. "
    "Moeda trocada, valores de moedas diferentes somados num total só, "
    "opinião dita como fato do sistema, número, data, telefone ou regra "
    "que não saiam da evidência contam como sem_apoio."
)


def _texto(mensagem) -> str:
    conteudo = getattr(mensagem, "content", "")
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        pedacos = []
        for parte in conteudo:
            if isinstance(parte, str):
                pedacos.append(parte)
            elif isinstance(parte, dict):
                pedacos.append(str(parte.get("text") or ""))
        return "\n".join(p for p in pedacos if p)
    return str(conteudo or "")


def _coleta(estado):
    pergunta = ""
    resposta = ""
    evidencias = []
    for mensagem in estado["messages"]:
        tipo = getattr(mensagem, "type", "")
        texto = _texto(mensagem).strip()
        if tipo == "human" and texto:
            pergunta = texto
            evidencias = []
        elif tipo == "tool" and texto:
            nome = getattr(mensagem, "name", "") or "tool"
            evidencias.append(f"[{nome}]\n{texto}")
        elif tipo == "ai":
            for chamada in getattr(mensagem, "tool_calls", None) or []:
                argumentos = json.dumps(chamada.get("args", {}), ensure_ascii=False)
                evidencias.append(f"[chamada {chamada.get('name')}]\n{argumentos}")
            if texto:
                resposta = texto
    evidencia = "\n\n".join(evidencias).strip()
    if not evidencia:
        evidencia = "(nenhuma tool devolveu conteúdo neste turno)"
    return pergunta, resposta, evidencia[-6000:]


def _publicar(texto, rotulo, resposta_original):
    print(f"[juiz] {rotulo}")
    if texto.strip() == (resposta_original or "").strip():
        return {"agentes_chamados": [f"juiz:{rotulo}"]}
    return {
        "messages": [{"role": "assistant", "content": texto.strip()}],
        "agentes_chamados": [f"juiz:{rotulo}"],
    }


def _julgar_jev(pergunta, resposta, evidencia):
    if not TYPESAFE_API_KEY:
        return _publicar(FRASE_SEGURA, "sem_chave", resposta)
    corpo = json.dumps({
        "model": JEV_MODELO,
        "state": {
            "pergunta": pergunta,
            "resposta": resposta,
            "evidencia": evidencia,
            "regras": REGRAS,
        },
        "questions": {
            "veredito": {
                "type": "choice",
                "instructions": "Seguindo as regras, a resposta só afirma o que a evidência sustenta?",
                "criteria": {
                    "apoiada": "toda afirmação factual aparece na evidência",
                    "parcial": "parte aparece e parte não",
                    "sem_apoio": "há fato, número, regra ou opinião sem evidência",
                },
            },
            "apoiada": {
                "type": "noul",
                "instructions": (
                    "Seguindo as regras, a resposta é fiel à evidência: todo valor, moeda, "
                    "data e fato dela sai da evidência, da fala do usuário ou de contas sobre elas?"
                ),
            },
        },
    }).encode()
    pedido = urllib.request.Request(
        JEV_URL,
        data=corpo,
        headers={
            "Authorization": f"Bearer {TYPESAFE_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resp:
            dados = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return _publicar(FRASE_SEGURA, f"erro http {exc.code}", resposta)
    respostas = dados["answers"]
    choice = respostas["veredito"]["choice"]
    noul = float(respostas["apoiada"]["noul"])
    if choice == "apoiada" and noul >= LIMIAR:
        return _publicar(resposta, f"apoiada noul={noul:.2f}", resposta)
    rotulo = "apoiada:abaixo_do_limiar" if choice == "apoiada" else choice
    return _publicar(FRASE_SEGURA, f"{rotulo} noul={noul:.2f}", resposta)


def no_juiz(estado: dict) -> dict:
    pergunta, resposta, evidencia = _coleta(estado)
    if not resposta:
        return {"agentes_chamados": ["juiz:sem_resposta"]}
    try:
        return _julgar_jev(pergunta, resposta, evidencia)
    except Exception as exc:
        print(f"[juiz] erro {exc}")
        return _publicar(FRASE_SEGURA, "erro", resposta)