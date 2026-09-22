const form = document.getElementById('chatForm');
const input = document.getElementById('messageInput');
const messages = document.getElementById('messages');
const statusBadge = document.getElementById('statusBadge');
const sendButton = form.querySelector('button');
const sessionId = `web-${crypto.randomUUID ? crypto.randomUUID() : Date.now()}`;

function addMessage(text, sender = 'bot', extraClass = '') {
  const messageWrap = document.createElement('div');
  messageWrap.className = `message ${sender} ${extraClass}`.trim();
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  messageWrap.appendChild(bubble);
  messages.appendChild(messageWrap);
  messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
  return messageWrap;
}

function setStatus(text, kind = 'success') {
  statusBadge.textContent = text;
  statusBadge.dataset.kind = kind;
}

async function sendMessage(event) {
  event.preventDefault();
  const value = input.value.trim();
  if (!value || sendButton.disabled) return;

  addMessage(value, 'user');
  input.value = '';
  input.style.height = 'auto';
  sendButton.disabled = true;
  sendButton.textContent = 'Pensando…';
  setStatus('Conectando…', 'loading');

  const typing = addMessage('Escribiendo…', 'bot', 'typing');

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: value, session_id: sessionId }),
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Respuesta inválida del servidor (${response.status})`);
    }

    typing.remove();
    if (!response.ok) {
      throw new Error(data.detail || `Error del servidor (${response.status})`);
    }

    addMessage(data.reply || 'La IA no devolvió texto.', 'bot');
    setStatus(data.mode === 'openai' ? 'IA conectada' : 'Modo demo', data.mode === 'openai' ? 'ai' : 'success');
  } catch (error) {
    typing.remove();
    addMessage(`No pude responder: ${error.message}. Comprueba que PowerShell muestre el servidor activo.`, 'bot', 'error');
    setStatus('Sin conexión', 'error');
    console.error('Chat error:', error);
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = 'Enviar';
    input.focus();
  }
}

form.addEventListener('submit', sendMessage);
input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
});
