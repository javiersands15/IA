const form = document.getElementById('chatForm');
const input = document.getElementById('messageInput');
const messages = document.getElementById('messages');
const statusBadge = document.getElementById('statusBadge');

function addMessage(text, sender = 'bot') {
  const messageWrap = document.createElement('div');
  messageWrap.className = `message ${sender}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;

  messageWrap.appendChild(bubble);
  messages.appendChild(messageWrap);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(event) {
  event.preventDefault();

  const value = input.value.trim();
  if (!value) return;

  addMessage(value, 'user');
  input.value = '';
  input.style.height = 'auto';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: value,
        session_id: 'web-session',
      }),
    });

    const data = await response.json();
    addMessage(data.reply || 'No pude obtener una respuesta.', 'bot');

    if (data.mode === 'openai') {
      statusBadge.textContent = 'AI mode';
      statusBadge.style.background = 'rgba(110, 168, 254, 0.12)';
      statusBadge.style.color = '#6ea8fe';
      statusBadge.style.borderColor = 'rgba(110, 168, 254, 0.35)';
    } else {
      statusBadge.textContent = 'Demo mode';
      statusBadge.style.background = 'rgba(52, 211, 153, 0.12)';
      statusBadge.style.color = '#34d399';
      statusBadge.style.borderColor = 'rgba(52, 211, 153, 0.35)';
    }
  } catch (error) {
    addMessage('No se pudo conectar con la IA. Comprueba que el servidor esté activo.', 'bot');
  }
}

form.addEventListener('submit', sendMessage);
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
});
