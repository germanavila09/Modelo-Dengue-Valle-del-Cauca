// ── GeoSalud Chatbot Widget ─────────────────────────────────────────────────
// Conecta el frontend del Observatorio con el servidor FastAPI (server.py)
// que envuelve el agente ADK de dengue.
//
// Arranque del servidor:
//   cd chatbot && uvicorn server:app --port 8080 --reload
// ────────────────────────────────────────────────────────────────────────────

const CHATBOT_API = (() => {
  if (window.CHATBOT_API_URL) return window.CHATBOT_API_URL;
  return window.location.protocol.startsWith("http")
    ? window.location.origin + "/api/geosalud"
    : "http://localhost:8080";
})();

// Genera un session_id único por pestaña (persiste en sessionStorage)
const CHAT_SESSION_ID = (() => {
  const key = 'geosalud_chat_session';
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = 'session_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
    sessionStorage.setItem(key, id);
  }
  return id;
})();

// Sugerencias de preguntas rápidas
const SUGGESTED_QUESTIONS = [
  'Abre el módulo de demografía',
  '¿Cuál es la población de Cali?',
  'Población por ciclo de vida en Palmira',
  'Top 5 municipios con más casos en 2024',
  'Mapa de casos del Valle del Cauca en 2024',
  'Mapa de nivel de riesgo',
];

// ── Estado del chat ───────────────────────────────────────────────────────────
let chatInitialized = false;
let chatIsLoading   = false;

// ── Inicialización ────────────────────────────────────────────────────────────
function initChatbot() {
  if (chatInitialized) return;
  chatInitialized = true;

  _renderChatShell();
  _checkServerStatus();
  _addWelcomeMessage();
}

function openChatbot() {
  initChatbot();
  document.getElementById('s-chatbot')?.classList.remove('chat-collapsed');
  setTimeout(() => document.getElementById('chat-input')?.focus(), 80);
}

function closeChatbot() {
  document.getElementById('s-chatbot')?.classList.add('chat-collapsed');
}

function toggleChatbot() {
  initChatbot();
  const section = document.getElementById('s-chatbot');
  if (!section) return;
  if (section.classList.contains('chat-collapsed')) openChatbot();
  else closeChatbot();
}

// ── Render del shell HTML ─────────────────────────────────────────────────────
function _renderChatShell() {
  const section = document.getElementById('s-chatbot');
  if (!section || section.dataset.chatReady) return;
  section.dataset.chatReady = '1';
  section.classList.add('chat-collapsed');

  section.innerHTML = `
    <button class="chat-fab" onclick="toggleChatbot()" title="Asistente IA">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
        <path d="M8 10h.01M12 10h.01M16 10h.01M12 14c1.66 0 3-1.34 3-3"/>
      </svg>
    </button>
    <div class="chat-floating-panel">
    <!-- Header del chat -->
    <div class="chat-header-bar">
      <div class="chat-header-left">
        <div class="chat-avatar">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
            <path d="M8 10h.01M12 10h.01M16 10h.01M12 14c1.66 0 3-1.34 3-3"/>
          </svg>
        </div>
        <div>
          <div class="chat-title-text">Asistente GeoSalud</div>
          <div class="chat-subtitle-text">Dengue · Valle del Cauca · 42 municipios · 2019–2026</div>
        </div>
      </div>
      <div class="chat-status-pill" id="chat-status-pill">
        <span class="chat-status-dot" id="chat-status-dot"></span>
        <span id="chat-status-label">Conectando…</span>
      </div>
      <button class="chat-close-btn" onclick="closeChatbot()" title="Cerrar">×</button>
    </div>

    <!-- Chips de sugerencias -->
    <div class="chat-suggestions" id="chat-suggestions">
      ${SUGGESTED_QUESTIONS.map(q => `
        <button class="chat-chip" type="button" data-chat-question="${_escapeAttr(q)}">${q}</button>
      `).join('')}
    </div>

    <!-- Área de mensajes -->
    <div class="chat-messages" id="chat-messages"></div>

    <!-- Input -->
    <div class="chat-input-bar">
      <input
        type="text"
        id="chat-input"
        class="chat-input"
        placeholder="Pregunta sobre casos, municipios, tendencias…"
        autocomplete="off"
        maxlength="400"
      />
      <button id="chat-send-btn" class="chat-send-btn" onclick="sendChatFromInput()" title="Enviar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
    </div>
  `;

  // Enviar con Enter
  document.getElementById('chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatFromInput(); }
  });

  document.querySelectorAll('.chat-chip[data-chat-question]').forEach(btn => {
    btn.addEventListener('click', () => {
      sendChatMessage(btn.dataset.chatQuestion || btn.textContent || '');
    });
  });
}

window.initChatbot = initChatbot;
window.openChatbot = openChatbot;
window.closeChatbot = closeChatbot;
window.toggleChatbot = toggleChatbot;
window.sendChatMessage = sendChatMessage;
window.sendChatFromInput = sendChatFromInput;

document.addEventListener('DOMContentLoaded', () => {
  initChatbot();
});

// ── Verificar servidor ────────────────────────────────────────────────────────
async function _checkServerStatus() {
  const dot   = document.getElementById('chat-status-dot');
  const label = document.getElementById('chat-status-label');
  const pill  = document.getElementById('chat-status-pill');
  try {
    const res = await fetch(`${CHATBOT_API}/health`, { signal: AbortSignal.timeout(4000) });
    if (res.ok) {
      dot.classList.add('online');
      label.textContent = 'Agente conectado';
      pill.classList.add('online');
    } else {
      throw new Error('HTTP ' + res.status);
    }
  } catch {
    dot.classList.add('offline');
    label.textContent = 'Servidor no disponible';
    pill.classList.add('offline');
    _appendMessage('agent', '⚠️ No se pudo conectar con el servidor del agente.\n\nAsegúrate de haberlo iniciado:\n```\ncd chatbot\nuvicorn server:app --port 8080 --reload\n```', []);
  }
}

// ── Mensaje de bienvenida ─────────────────────────────────────────────────────
function _addWelcomeMessage() {
  _appendMessage(
    'agent',
    '¡Hola! Soy el **Asistente del Observatorio GeoSalud**.\n\nPuedo responder preguntas sobre dengue en los 42 municipios del Valle del Cauca (2019–2026): casos confirmados, incidencia, rankings, series históricas y gráficas.\n\nUsa los botones de sugerencias o escríbeme directamente. 👇',
    []
  );
}

// ── Enviar desde input ────────────────────────────────────────────────────────
function sendChatFromInput() {
  const input = document.getElementById('chat-input');
  const text = (input.value || '').trim();
  if (!text) return;
  input.value = '';
  sendChatMessage(text);
}

// ── Enviar mensaje ────────────────────────────────────────────────────────────
async function sendChatMessage(text) {
  if (chatIsLoading || !text.trim()) return;
  chatIsLoading = true;

  // Mostrar mensaje del usuario
  _appendMessage('user', text, []);

  // Deshabilitar input
  const input   = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  input.disabled = sendBtn.disabled = true;

  // Mostrar loader
  const loaderId = _appendLoader();

  try {
    const res = await fetch(`${CHATBOT_API}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: CHAT_SESSION_ID, message: text }),
      signal: AbortSignal.timeout(60000),
    });

    _removeLoader(loaderId);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error desconocido' }));
      _appendMessage('agent', `❌ Error del servidor: ${err.detail || res.status}`, []);
    } else {
      const data = await res.json();
      _appendMessage('agent', data.reply || '(Sin respuesta)', data.artifacts || []);
      _applyChatActions(data.actions || []);
    }
  } catch (err) {
    _removeLoader(loaderId);
    if (err.name === 'TimeoutError') {
      _appendMessage('agent', '⏱️ La consulta tardó demasiado. El agente puede estar procesando una gráfica compleja. Intenta de nuevo.', []);
    } else {
      _appendMessage('agent', `❌ No se pudo contactar el servidor: ${err.message}`, []);
    }
  } finally {
    input.disabled = sendBtn.disabled = false;
    chatIsLoading = false;
    input.focus();
  }
}

function _applyChatActions(actions) {
  if (!Array.isArray(actions) || actions.length === 0) return;
  setTimeout(() => {
    actions.forEach(action => {
      if (window.applyGeoSaludChatAction) window.applyGeoSaludChatAction(action);
    });
  }, 350);
}

// ── Render de un mensaje ──────────────────────────────────────────────────────
function _appendMessage(role, text, artifacts) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const msg = document.createElement('div');
  msg.className = `chat-msg chat-msg-${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.innerHTML = _renderMarkdown(text);

  msg.appendChild(bubble);

  // Imágenes de artifacts
  if (artifacts && artifacts.length > 0) {
    artifacts.forEach(filename => {
      const imgWrap = document.createElement('div');
      imgWrap.className = 'chat-artifact';

      const img = document.createElement('img');
      img.src = `${CHATBOT_API}/artifacts/${encodeURIComponent(filename)}?session_id=${encodeURIComponent(CHAT_SESSION_ID)}`;
      img.alt = filename;
      img.className = 'chat-artifact-img';
      img.loading = 'lazy';

      // Expandir en click
      img.addEventListener('click', () => _openArtifactModal(img.src, filename));

      const caption = document.createElement('div');
      caption.className = 'chat-artifact-caption';
      caption.textContent = filename.replace(/_/g, ' ').replace('.png', '');

      imgWrap.appendChild(img);
      imgWrap.appendChild(caption);
      msg.appendChild(imgWrap);
    });
  }

  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

// ── Loader (puntos animados) ──────────────────────────────────────────────────
function _appendLoader() {
  const id = 'loader_' + Date.now();
  const container = document.getElementById('chat-messages');
  const msg = document.createElement('div');
  msg.className = 'chat-msg chat-msg-agent';
  msg.id = id;
  msg.innerHTML = `
    <div class="chat-bubble chat-bubble-loading">
      <span class="dot-pulse"></span>
      <span class="dot-pulse" style="animation-delay:.15s"></span>
      <span class="dot-pulse" style="animation-delay:.3s"></span>
    </div>`;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
  return id;
}

function _removeLoader(id) {
  document.getElementById(id)?.remove();
}

// ── Markdown mínimo ───────────────────────────────────────────────────────────
function _renderMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/\n/g, '<br>');
}

function _escapeAttr(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ── Modal de imagen ampliada ──────────────────────────────────────────────────
function _openArtifactModal(src, title) {
  const existing = document.getElementById('artifact-modal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'artifact-modal';
  modal.className = 'artifact-modal';
  modal.innerHTML = `
    <div class="artifact-modal-backdrop" onclick="document.getElementById('artifact-modal').remove()"></div>
    <div class="artifact-modal-content">
      <div class="artifact-modal-header">
        <span>${title.replace(/_/g, ' ').replace('.png', '')}</span>
        <button onclick="document.getElementById('artifact-modal').remove()">✕</button>
      </div>
      <img src="${src}" alt="${title}" class="artifact-modal-img"/>
    </div>`;
  document.body.appendChild(modal);
}
