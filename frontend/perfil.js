/* ====================================================
   Tela Perfil — envio do formulário.

   Esta tela só ESCREVE. Ela não carrega o perfil salvo ao abrir,
   e a API não precisa expor rota de leitura.
   ==================================================== */

// Precisa ser o mesmo usuário que o chat usa. Se o backend usar outro
// identificador quando o front não manda user_id, o assessor não vai
// encontrar o perfil cadastrado aqui.
const USER_ID = localStorage.getItem('assistente_user_id') || 'usuario_teste';

// A rota que a sua API precisa expor.
const ENDPOINT = '/perfil';

const API_BASE =
  window.location.protocol === 'file:' ? 'http://localhost:8000' : '';

const els = {
  badge: document.getElementById('user-badge'),
  renda: document.getElementById('renda_mensal'),
  objetivo: document.getElementById('objetivo'),
  tolerancia: document.getElementById('tolerancia_risco'),
  preferencias: document.getElementById('preferencias'),
  status: document.getElementById('status'),
  submit: document.getElementById('submit'),
  echo: document.getElementById('echo'),
  echoBody: document.getElementById('echo-body'),
};

els.badge.textContent = USER_ID;

function setStatus(text, kind) {
  els.status.textContent = text;
  els.status.className = 'sheet__status' + (kind ? ` is-${kind}` : '');
}

function montarPayload() {
  const renda = els.renda.value.trim();

  // Campos vazios viram null de propósito: quem decide o que é obrigatório
  // é a API, não esta tela.
  return {
    user_id: USER_ID,
    renda_mensal: renda === '' ? null : Number(renda),
    objetivo: els.objetivo.value.trim() || null,
    tolerancia_risco: els.tolerancia.value || null,
    preferencias: els.preferencias.value.trim() || null,
  };
}

function mostrarResposta(dados) {
  els.echoBody.textContent = JSON.stringify(dados, null, 2);
  els.echo.hidden = false;
}

async function salvar() {
  const payload = montarPayload();

  els.submit.disabled = true;
  setStatus('enviando...');
  els.echo.hidden = true;

  try {
    const resposta = await fetch(API_BASE + ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    let corpo = null;
    try {
      corpo = await resposta.json();
    } catch {
      corpo = { detail: 'a resposta não era JSON' };
    }

    if (!resposta.ok) {
      setStatus(`a api recusou (${resposta.status})`, 'error');
      mostrarResposta(corpo);
      return;
    }

    setStatus('perfil salvo', 'ok');
    mostrarResposta(corpo);
  } catch (erro) {
    setStatus('não consegui falar com a api', 'error');
    mostrarResposta({ erro: String(erro) });
  } finally {
    els.submit.disabled = false;
  }
}

els.submit.addEventListener('click', salvar);
