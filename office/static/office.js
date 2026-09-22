"use strict";

// ---------------------------------------------------------------------
// Personagens: sprites pixel-art prontos, de pixel-agents-hq/pixel-agents
// (MIT — ver office/static/assets/characters/README.md), não desenhados
// à mão. Layout de cada folha (112x96px, 4 personagens em
// office/static/assets/characters/char_N.png): 3 linhas (baixo/cima/
// direita) x 7 colunas de 16x32px — colunas 0-2 são o ciclo de caminhada,
// 3-4 são "digitando", 5-6 são "lendo". Não existe linha "esquerda": é a
// linha "direita" espelhada (ctx.scale(-1,1)) — mesma técnica que já
// usávamos nos sprites desenhados à mão. Layout confirmado lendo o
// código-fonte deles (webview-ui/src/office/sprites/spriteData.ts e
// engine/characters.ts), não adivinhado.
// ---------------------------------------------------------------------

const FRAME_W = 16;
const FRAME_H = 32;
const SCALE = 3;
const DRAW_W = FRAME_W * SCALE;
const DRAW_H = FRAME_H * SCALE;

const SHEET_ROW = { down: 0, up: 1, right: 2 };

// Colunas por linha: caminhada usa o ciclo [0,1,2,1] (mesmo padrão do
// pixel-agents — ver characters.ts::getCharacterSprite), digitando
// alterna 3<->4, lendo alterna 5<->6 (usado quando a tool ativa é de
// leitura — ver ROLE em office.js::handleMessage/activity).
const WALK_CYCLE = [0, 1, 2, 1];
const TYPE_FRAMES = [3, 4];
const READ_FRAMES = [5, 6];
const WALK_FRAME_DURATION = 150; // ms, igual ao pixel-agents (WALK_FRAME_DURATION_SEC)
const TYPE_FRAME_DURATION = 300; // ms, igual ao pixel-agents (TYPE_FRAME_DURATION_SEC)

const ROLES = {
  supervisor: { label: "Supervisor", color: "#1baf7a", charFile: "char_3.png" },
  arquiteto: { label: "Arquiteto", color: "#6a5ad6", charFile: "char_4.png" },
  dev_backend: { label: "Dev Backend", color: "#eb6834", charFile: "char_2.png" },
  dev_frontend: { label: "Dev Frontend", color: "#e87ba4", charFile: "char_1.png" },
};

const ROLE_ORDER = ["supervisor", "arquiteto", "dev_backend", "dev_frontend"];

const characterImages = {};
for (const role of ROLE_ORDER) {
  const img = new Image();
  img.src = `/static/assets/characters/${ROLES[role].charFile}`;
  characterImages[role] = img;
}

const EXAMPLE_TASKS = [
  "Crie uma feature de login (email + senha) no projeto FastAPI + React.",
  "Crie uma feature de 'lista de favoritos': endpoint no backend para adicionar, listar e remover um item por id (guardado em memória) e uma tela no frontend em React que lista os favoritos e permite adicionar/remover. Não rode comandos de instalação, apenas escreva os arquivos.",
];

// ---------------------------------------------------------------------
// Estado de cada personagem — duas camadas:
// - `status`: vem do servidor ('idle'/'working'/'done') e diz O QUE o
//   papel está fazendo agora (é a vez dele? acabou de terminar?).
// - `phase`/`x`/`facing`: posição e animação, calculadas a cada quadro em
//   `updateCharacter` a PARTIR do status. 'wander' (passeia devagar perto
//   da própria baia) enquanto idle/done; 'walking_to_desk' -> 'at_desk'
//   quando `status` vira 'working' (anda até a mesa, senta, monitor
//   acende, pose de "digitando"); volta a 'wander' quando termina.
// ---------------------------------------------------------------------

const state = {};

function freshCharacterState() {
  return {
    status: "idle",
    tokens: 0,
    doneUntil: 0,
    phase: "wander",
    x: 0,
    facing: 1,
    wanderAnchor: 0,
    wanderStart: 0,
    walkFromX: 0,
    walkStart: 0,
  };
}

for (const role of ROLE_ORDER) state[role] = freshCharacterState();

function resetState() {
  for (const role of ROLE_ORDER) {
    const x = state[role].x; // mantém posição atual, só zera status/tokens
    state[role] = { ...freshCharacterState(), x, wanderAnchor: x };
  }
}

// ---------------------------------------------------------------------
// Canvas: 4 "baias" lado a lado (mesa + monitor ao fundo, chão na frente
// onde o personagem caminha).
// ---------------------------------------------------------------------

const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
ctx.imageSmoothingEnabled = false;

const SLOT_WIDTH = canvas.width / ROLE_ORDER.length;

const DESK_FOOT_Y = 214; // pé do personagem quando está "na mesa" (working)
const WANDER_FOOT_Y = 278; // pé do personagem passeando à frente da mesa
const MONITOR_Y = 118;
const MONITOR_W = 62;
const MONITOR_H = 44;
const DESK_Y = MONITOR_Y + MONITOR_H + 8;
const DESK_H = 24;

ROLE_ORDER.forEach((role, index) => {
  const deskX = index * SLOT_WIDTH + SLOT_WIDTH / 2;
  state[role].x = deskX;
  state[role].wanderAnchor = deskX;
});

function hexWithAlpha(hex, alpha) {
  const value = Math.round(alpha * 255).toString(16).padStart(2, "0");
  return `${hex}${value}`;
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

// ---------------------------------------------------------------------
// Movimento: sem física — cada frame recalcula x a partir do tempo e da
// fase atual, então não precisa de integração de velocidade nem dt.
// ---------------------------------------------------------------------

function updateCharacter(role, index, time) {
  const s = state[role];
  const zoneLeft = index * SLOT_WIDTH + 30;
  const zoneRight = (index + 1) * SLOT_WIDTH - 30;
  const deskX = index * SLOT_WIDTH + SLOT_WIDTH / 2;
  const previousX = s.x;

  if (s.status === "working") {
    if (s.phase !== "walking_to_desk" && s.phase !== "at_desk") {
      s.phase = "walking_to_desk";
      s.walkFromX = s.x;
      s.walkStart = time;
    }
    if (s.phase === "walking_to_desk") {
      const t = Math.min(1, (time - s.walkStart) / 650);
      s.x = s.walkFromX + (deskX - s.walkFromX) * easeOutCubic(t);
      if (t >= 1) s.phase = "at_desk";
    } else {
      s.x = deskX;
    }
  } else {
    if (s.phase !== "wander") {
      s.phase = "wander";
      s.wanderAnchor = s.x;
      s.wanderStart = time;
    }
    const radius = Math.max(10, Math.min(34, (zoneRight - zoneLeft) / 2 - 6));
    const center = Math.max(zoneLeft + radius, Math.min(zoneRight - radius, s.wanderAnchor));
    const t = (time - s.wanderStart) / 1000;
    s.x = center + Math.sin(t * 0.55 + index * 1.7) * radius;
  }

  const dx = s.x - previousX;
  if (Math.abs(dx) > 0.03) s.facing = dx > 0 ? 1 : -1;
  s.walking = s.phase !== "at_desk" && Math.abs(dx) > 0.03;
}

function footY(role) {
  const s = state[role];
  if (s.phase === "at_desk") return DESK_FOOT_Y;
  if (s.phase === "walking_to_desk") {
    const t = Math.min(1, (performance.now() - s.walkStart) / 650);
    return WANDER_FOOT_Y + (DESK_FOOT_Y - WANDER_FOOT_Y) * easeOutCubic(t);
  }
  return WANDER_FOOT_Y;
}

// ---------------------------------------------------------------------
// Desenho.
// ---------------------------------------------------------------------

function drawFloor() {
  ctx.fillStyle = "#181a24";
  ctx.fillRect(0, DESK_Y + DESK_H, canvas.width, canvas.height - (DESK_Y + DESK_H));
  ctx.strokeStyle = "#23263380";
  for (let x = 0; x <= canvas.width; x += 24) {
    ctx.beginPath();
    ctx.moveTo(x, DESK_Y + DESK_H);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
}

/** Escolhe linha/coluna da folha de sprite pro estado atual do personagem —
 * mesma lógica de pixel-agents (engine/characters.ts::getCharacterSprite),
 * adaptada: não temos "lendo" vindo do servidor ainda, então todo tempo
 * "at_desk" usa a pose de digitar. */
function frameFor(role, time) {
  const s = state[role];
  if (s.phase === "at_desk") {
    const col = TYPE_FRAMES[Math.floor(time / TYPE_FRAME_DURATION) % TYPE_FRAMES.length];
    return { row: SHEET_ROW.down, col };
  }
  // Passeando/andando: sempre a linha "direita" da folha — vira "esquerda"
  // por espelhamento (ver `flip` em drawCharacterSprite), não existe uma
  // linha própria pra esquerda na folha original.
  if (s.walking) {
    const col = WALK_CYCLE[Math.floor(time / WALK_FRAME_DURATION) % WALK_CYCLE.length];
    return { row: SHEET_ROW.right, col };
  }
  return { row: SHEET_ROW.right, col: 1 };
}

function drawCharacterSprite(role, time) {
  const img = characterImages[role];
  if (!img.complete || img.naturalWidth === 0) return;

  const s = state[role];
  const feet = footY(role);
  const { row, col } = frameFor(role, time);
  const flip = row === SHEET_ROW.right && s.facing < 0;

  const dx = s.x - DRAW_W / 2;
  const dy = feet - DRAW_H;

  ctx.save();
  if (flip) {
    ctx.translate(s.x, 0);
    ctx.scale(-1, 1);
    ctx.translate(-s.x, 0);
  }
  ctx.drawImage(
    img,
    col * FRAME_W, row * FRAME_H, FRAME_W, FRAME_H,
    dx, dy, DRAW_W, DRAW_H
  );
  ctx.restore();
}

function screenColorFor(role, time) {
  const s = state[role];
  if (s.status === "working") {
    const pulse = (Math.sin(time / 180) + 1) / 2;
    const from = [0x17, 0xa0, 0x6d];
    const to = [0x2b, 0xf0, 0xa8];
    const mix = from.map((v, i) => Math.round(v + (to[i] - v) * pulse));
    return `rgb(${mix.join(",")})`;
  }
  if (performance.now() < s.doneUntil) return "#2a78d6";
  return "#33364a";
}

function drawDeskFurniture(index, role, time) {
  // Só a mobília física (brilho, monitor, mesa) — a ordem em que isto é
  // chamado em relação ao personagem MUDA com o estado (ver `draw`): o
  // rótulo/status ficam sempre por cima em `drawStationLabel`, separados
  // daqui de propósito, pra nunca ficarem escondidos atrás do sprite.
  const config = ROLES[role];
  const s = state[role];
  const centerX = index * SLOT_WIDTH + SLOT_WIDTH / 2;
  const working = s.status === "working";

  if (working) {
    const glowAlpha = 0.14 + 0.07 * ((Math.sin(time / 180) + 1) / 2);
    ctx.fillStyle = hexWithAlpha(config.color, glowAlpha);
    ctx.fillRect(index * SLOT_WIDTH + 6, 18, SLOT_WIDTH - 12, canvas.height - 36);
  }

  const monitorX = centerX - MONITOR_W / 2;
  ctx.fillStyle = "#20222e";
  ctx.fillRect(monitorX, MONITOR_Y, MONITOR_W, MONITOR_H);
  ctx.fillStyle = screenColorFor(role, time);
  ctx.fillRect(monitorX + 5, MONITOR_Y + 5, MONITOR_W - 10, MONITOR_H - 14);
  ctx.fillStyle = "#14151c";
  ctx.fillRect(centerX - 9, MONITOR_Y + MONITOR_H, 18, 7);

  const deskX = centerX - (SLOT_WIDTH - 34) / 2;
  ctx.fillStyle = "#6b4a2f";
  ctx.fillRect(deskX, DESK_Y, SLOT_WIDTH - 34, DESK_H);
  ctx.fillStyle = "#4d341f";
  ctx.fillRect(deskX, DESK_Y + DESK_H - 6, SLOT_WIDTH - 34, 6);
}

function drawStationLabel(index, role) {
  const config = ROLES[role];
  const s = state[role];
  const centerX = index * SLOT_WIDTH + SLOT_WIDTH / 2;
  const working = s.status === "working";

  ctx.textAlign = "center";
  ctx.font = "11px ui-monospace, monospace";
  ctx.fillStyle = working ? config.color : "#9497ab";
  ctx.fillText(config.label, centerX, canvas.height - 22);
  ctx.font = "10px ui-monospace, monospace";
  ctx.fillStyle = "#5c5f73";
  ctx.fillText(`${s.tokens.toLocaleString("pt-BR")} tk`, centerX, canvas.height - 8);

  ctx.beginPath();
  ctx.fillStyle = working ? "#2bf0a8" : performance.now() < s.doneUntil ? "#2a78d6" : "#3a3d52";
  ctx.arc(centerX, 16, 5, 0, Math.PI * 2);
  ctx.fill();
}

function draw(time) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawFloor();

  ROLE_ORDER.forEach((role, index) => {
    updateCharacter(role, index, time);

    // "at_desk": o personagem senta ATRÁS da mesa — mobília desenhada por
    // cima cobre a parte de baixo do corpo (como sentar de verdade atrás
    // de um monitor). Passeando: o personagem está à FRENTE da mesa, no
    // chão aberto — desenhado por cima da mobília.
    if (state[role].phase === "at_desk") {
      drawCharacterSprite(role, time);
      drawDeskFurniture(index, role, time);
    } else {
      drawDeskFurniture(index, role, time);
      drawCharacterSprite(role, time);
    }
    drawStationLabel(index, role);
  });

  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

// ---------------------------------------------------------------------
// Log e painel de tokens (DOM simples).
// ---------------------------------------------------------------------

const logEl = document.getElementById("log");
const usageEl = document.getElementById("usage-bars");
const runTokensEl = document.getElementById("run-tokens");
const statusLineEl = document.getElementById("status-line");
const runBtn = document.getElementById("run-btn");
const taskInput = document.getElementById("task-input");
const configLineEl = document.getElementById("config-line");
const projectSelectEl = document.getElementById("project-select");
const researchPanelEl = document.getElementById("research-panel");
const researchCategorySelectEl = document.getElementById("research-category-select");
const researchTaskInputEl = document.getElementById("research-task-input");
const researchStatusLineEl = document.getElementById("research-status-line");
const researchBtn = document.getElementById("research-btn");

let logHasEntries = false;

function appendLog(roleKey, label, text, { dim = false } = {}) {
  if (!logHasEntries) {
    logEl.innerHTML = "";
    logHasEntries = true;
  }
  const entry = document.createElement("div");
  entry.className = `log-entry role-${roleKey}${dim ? " activity" : ""}`;
  const tag = document.createElement("div");
  tag.className = "role-tag";
  tag.textContent = label;
  const body = document.createElement("div");
  body.textContent = text;
  entry.appendChild(tag);
  entry.appendChild(body);
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
}

function renderUsageBars() {
  const maxTokens = Math.max(1, ...ROLE_ORDER.map((r) => state[r].tokens));
  const anyTokens = ROLE_ORDER.some((r) => state[r].tokens > 0);
  if (!anyTokens) {
    usageEl.innerHTML = '<p class="empty-hint">Sem dados ainda.</p>';
    return;
  }
  usageEl.innerHTML = "";
  for (const role of ROLE_ORDER) {
    const config = ROLES[role];
    const tokens = state[role].tokens;
    const row = document.createElement("div");
    row.className = "usage-row";
    row.innerHTML = `
      <div class="usage-label"><span>${config.label}</span><span>${tokens.toLocaleString("pt-BR")}</span></div>
      <div class="usage-track"><div class="usage-fill" style="width:${(tokens / maxTokens) * 100}%;background:${config.color}"></div></div>
    `;
    usageEl.appendChild(row);
  }
}

// ---------------------------------------------------------------------
// Config ativa (provedor + pasta que dev_backend/dev_frontend podem
// tocar nesta sessão) — buscada uma vez ao carregar, nunca implícita.
// ---------------------------------------------------------------------

fetch("/config")
  .then((r) => r.json())
  .then((cfg) => {
    configLineEl.textContent = `provedor: ${cfg.provider} · pasta autorizada: ${cfg.workspace}`;
  })
  .catch(() => {
    configLineEl.textContent = "não foi possível ler /config";
  });

// Seletor de projeto: escolher um prefixa a tarefa com "trabalhe em
// <projeto>/" antes de mandar pro time (ver
// office/server.py::build_task_with_project_context) — é um hint forte
// no prompt, não uma restrição técnica nova; o sandbox continua sendo o
// workspace inteiro (ver /config acima).
fetch("/projects")
  .then((r) => r.json())
  .then((data) => {
    for (const name of data.projects || []) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      projectSelectEl.appendChild(option);
    }
  })
  .catch(() => {
    /* seletor fica só com "(todos)" — não é crítico pro resto funcionar */
  });

// Painel do pesquisador: só aparece se o backend do acervo estiver no
// workspace ativo (ver office/server.py::research_categories) — sem ele
// não tem categoria/schema real pra validar contra, então não faz sentido
// oferecer o botão.
fetch("/research/categories")
  .then((r) => r.json())
  .then((data) => {
    const categories = data.categories || [];
    if (categories.length === 0) return;
    for (const name of categories) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      researchCategorySelectEl.appendChild(option);
    }
    researchPanelEl.hidden = false;
  })
  .catch(() => {
    /* painel fica escondido — mesmo tratamento de erro do /projects acima */
  });

// ---------------------------------------------------------------------
// WebSocket: manda a tarefa, recebe eventos (decisão/resultado do
// supervisor, tool calls individuais, uso de token) e status de execução.
// ---------------------------------------------------------------------

let ws = null;
let running = false;
// Qual painel disparou a tarefa em curso — "status"/"error"/"usage"/"done"
// são compartilhados entre os dois fluxos (só uma tarefa por vez, trava no
// servidor: ver office/server.py::websocket_endpoint), então precisa saber
// pra qual linha de status e botão devolver o controle quando termina.
let activeMode = "run";

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.addEventListener("message", (event) => {
    handleMessage(JSON.parse(event.data));
  });

  ws.addEventListener("close", () => {
    statusLineEl.textContent = "Conexão perdida — recarregue a página.";
    runBtn.disabled = true;
  });
}

function handleMessage(message) {
  if (message.type === "status") {
    running = message.running;
    runBtn.disabled = running;
    researchBtn.disabled = running;
    runBtn.textContent = running && activeMode === "run" ? "⏳ Rodando…" : "▶ Rodar";
    researchBtn.textContent = running && activeMode === "research" ? "⏳ Pesquisando…" : "🔎 Pesquisar";
    if (!running) {
      statusLineEl.textContent = "Concluído — pronto pra próxima tarefa.";
      researchStatusLineEl.textContent = "Concluído — pronto pra próxima pesquisa.";
    }
    return;
  }

  if (message.type === "error") {
    appendLog("error", "Erro", message.message);
    if (activeMode === "research") {
      researchStatusLineEl.textContent = "Deu erro — veja o log.";
    } else {
      statusLineEl.textContent = "Deu erro — veja o log.";
    }
    return;
  }

  if (message.type === "research_status") {
    appendLog("pesquisador", "Pesquisador", message.text, { dim: true });
    researchStatusLineEl.textContent = message.text;
    return;
  }

  if (message.type === "research_warning") {
    appendLog("pesquisador", "Pesquisador", `⚠ ${message.text}`, { dim: true });
    return;
  }

  if (message.type === "research_result") {
    const text = `${message.valid} de ${message.proposed} item(ns) validado(s) e gravado(s) em "${message.categoria}".`;
    appendLog("pesquisador", "Pesquisador", text);
    researchStatusLineEl.textContent = text;
    return;
  }

  if (message.type === "activity") {
    const config = ROLES[message.role];
    if (config) appendLog(message.role, config.label, message.text, { dim: true });
    return;
  }

  if (message.type === "event") {
    const config = ROLES[message.role] || ROLES.supervisor;
    appendLog(message.role in ROLES ? message.role : "error", config.label, message.text);

    if (message.kind === "decision") {
      const match = message.text.match(/próximo:\s*(\w+)/);
      const nextRole = match ? match[1] : null;
      for (const role of ROLE_ORDER) {
        if (role === nextRole) {
          state[role].status = "working";
        } else if (state[role].status === "working") {
          state[role].status = "idle";
        }
      }
      statusLineEl.textContent = message.text;
    } else if (message.kind === "result") {
      const s = state[message.role];
      if (s) {
        s.status = "idle";
        s.doneUntil = performance.now() + 2500;
      }
    } else {
      statusLineEl.textContent = message.text;
      for (const role of ROLE_ORDER) state[role].status = "idle";
    }
    return;
  }

  if (message.type === "usage") {
    const s = state[message.role];
    if (s) s.tokens += message.total_tokens;
    runTokensEl.innerHTML = `<strong>${message.run_total_tokens.toLocaleString("pt-BR")}</strong> tokens nesta rodada`;
    renderUsageBars();
    return;
  }

  if (message.type === "done") {
    for (const role of ROLE_ORDER) state[role].status = "idle";
    if (message.run_total_tokens) {
      runTokensEl.innerHTML = `<strong>${message.run_total_tokens.toLocaleString("pt-BR")}</strong> tokens nesta rodada`;
    }
  }
}

function runTask() {
  const task = taskInput.value.trim();
  if (!task || running || !ws || ws.readyState !== WebSocket.OPEN) return;
  activeMode = "run";
  resetState();
  renderUsageBars();
  runTokensEl.innerHTML = "0 tokens nesta rodada";
  logHasEntries = false;
  logEl.innerHTML = "";
  const project = projectSelectEl.value || null;
  statusLineEl.textContent = project
    ? `Enviando tarefa pro time — projeto: ${project}…`
    : "Enviando tarefa pro time…";
  ws.send(JSON.stringify({ action: "run", task, project }));
}

function runResearch() {
  const categoria = researchCategorySelectEl.value;
  const task = researchTaskInputEl.value.trim();
  if (!categoria || !task || running || !ws || ws.readyState !== WebSocket.OPEN) return;
  activeMode = "research";
  logHasEntries = false;
  logEl.innerHTML = "";
  researchStatusLineEl.textContent = `Pesquisando para "${categoria}"…`;
  ws.send(JSON.stringify({ action: "research", categoria, task }));
}

runBtn.addEventListener("click", runTask);
taskInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) runTask();
});
researchBtn.addEventListener("click", runResearch);
researchTaskInputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) runResearch();
});

const examplesEl = document.getElementById("examples");
EXAMPLE_TASKS.forEach((task) => {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = task.length > 70 ? `${task.slice(0, 70)}…` : task;
  button.addEventListener("click", () => {
    taskInput.value = task;
  });
  examplesEl.appendChild(button);
});

connect();
