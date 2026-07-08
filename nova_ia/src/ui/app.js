// ═══════════════════════════════════════════════════════════════════════════════
// NOVA — app.js
// ═══════════════════════════════════════════════════════════════════════════════

let sessaoAtual = null
let focoInterval = null
let focoSegundos = 0
let focoTotalSegundos = 0
let focoFase = "foco"
let focoPausado = false
let imagemAtual = null
let settings = { particles: true, animations: true, theme: "light" }
let ultimaMsgNova = null
let contextMsgEl = null

async function chamarAPI(fn, ...args) {
  try {
    const raw = await window.pywebview.api[fn](...args)
    return JSON.parse(raw)
  } catch (e) {
    console.error(`Erro ao chamar ${fn}:`, e)
    return { ok: false, erro: String(e) }
  }
}

function agoraHora() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`
}

function escapeHTML(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

function renderMarkdown(texto) {
  if (typeof marked !== "undefined") {
    try { return marked.parse(texto) } catch (e) {}
  }
  return escapeHTML(texto).replace(/\n/g, "<br>")
}

function esconderSplash() {
  const splash = document.getElementById("splash")
  if (splash) setTimeout(() => splash.classList.add("hidden"), 1200)
}

function showToast(titulo, msg = "", tipo = "info", duracao = 3500) {
  const container = document.getElementById("toast-container")
  const toast = document.createElement("div")
  toast.className = `toast ${tipo}`
  const icones = { success: "✓", error: "✕", warning: "⚠", info: "ℹ" }
  toast.innerHTML = `
    <div class="toast-icon">${icones[tipo] || "ℹ"}</div>
    <div class="toast-content">
      <div class="toast-title">${escapeHTML(titulo)}</div>
      ${msg ? `<div class="toast-msg">${escapeHTML(msg)}</div>` : ""}
    </div>
  `
  container.appendChild(toast)
  setTimeout(() => {
    toast.classList.add("fade-out")
    setTimeout(() => toast.remove(), 300)
  }, duracao)
}

function criarParticulas() {
  const container = document.getElementById("chat-particles")
  if (!container) return
  container.innerHTML = ""
  if (!settings.particles) return
  const cores = ["", "magenta", "amber", "cyan"]
  for (let i = 0; i < 20; i++) {
    const p = document.createElement("div")
    p.className = "particle " + cores[Math.floor(Math.random() * cores.length)]
    if (Math.random() > 0.7) p.classList.add("big")
    p.style.left = Math.random() * 100 + "%"
    p.style.animationDuration = (12 + Math.random() * 10) + "s"
    p.style.animationDelay = (Math.random() * 15) + "s"
    container.appendChild(p)
  }
}

function aplicarTema(tema) {
  document.body.setAttribute("data-theme", tema)
  settings.theme = tema
  document.querySelectorAll(".theme-option").forEach(opt => {
    opt.classList.toggle("active", opt.dataset.theme === tema)
  })
  const icon = document.getElementById("theme-icon")
  if (icon) {
    if (tema === "dark") {
      icon.innerHTML = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
    } else {
      icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
    }
  }
}

function toggleTheme() {
  const novo = settings.theme === "light" ? "dark" : "light"
  aplicarTema(novo)
  showToast(`Tema ${novo === "dark" ? "escuro" : "claro"}`, "", "info", 1500)
}

function setTheme(tema) { aplicarTema(tema) }

window.addEventListener("pywebviewready", async () => {
  esconderSplash()
  aplicarTema("light")
  criarParticulas()

  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => trocarAba(btn.dataset.aba))
  })
  document.getElementById("btn-nova-conversa").addEventListener("click", novaConversa)
  document.getElementById("chat-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviarMensagem() }
  })
  document.getElementById("chat-send").addEventListener("click", enviarMensagem)
  document.getElementById("cor-fundo").addEventListener("input", e => {
    document.getElementById("cor-fundo-label").textContent = e.target.value
  })

  const chatMsgs = document.getElementById("chat-msgs")
  chatMsgs.addEventListener("scroll", () => {
    const btn = document.getElementById("scroll-bottom-btn")
    const perto = chatMsgs.scrollHeight - chatMsgs.scrollTop - chatMsgs.clientHeight < 80
    btn.classList.toggle("visible", !perto)
  })

  document.addEventListener("click", () => {
    document.getElementById("context-menu").classList.remove("visible")
  })

  setupSidebarDrag()
  document.addEventListener("keydown", handleAtalhos)

  try { await abrirUltimaConversa() } catch (e) { console.error(e) }
  try { await carregarResumoMatinal() } catch (e) { console.error(e) }
  try { await atualizarStatsFoco() } catch (e) { console.error(e) }
  try { await atualizarBadges() } catch (e) { console.error(e) }
  try { await atualizarKeyDot() } catch (e) { console.error(e) }
})

function handleAtalhos(e) {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === "k" || e.key === "K") {
      e.preventDefault(); novaConversa()
      showToast("Nova conversa", "", "info", 1500)
    } else if (e.key === "/") {
      e.preventDefault()
      const hint = document.getElementById("shortcut-hint")
      hint.classList.add("visible")
      setTimeout(() => hint.classList.remove("visible"), 2500)
    }
  }
  if (e.key === "Escape") {
    document.querySelectorAll(".modal").forEach(m => m.style.display = "none")
    document.getElementById("context-menu").classList.remove("visible")
  }
}

function setupSidebarDrag() {
  const resizer = document.getElementById("sidebar-resizer")
  if (!resizer) return
  let isDragging = false
  resizer.addEventListener("mousedown", (e) => {
    isDragging = true
    resizer.classList.add("dragging")
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    e.preventDefault()
  })
  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return
    const novaLargura = Math.max(180, Math.min(400, e.clientX))
    document.documentElement.style.setProperty("--sidebar-width", novaLargura + "px")
  })
  document.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false
      resizer.classList.remove("dragging")
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
  })
}

async function atualizarBadges() {
  try {
    const res = await chamarAPI("get_tarefas")
    if (res.ok) {
      const pendentes = res.data.filter(t => t.status === "pendente").length
      const badge = document.getElementById("badge-tarefas")
      if (pendentes > 0) { badge.textContent = pendentes > 9 ? "9+" : pendentes; badge.style.display = "inline-block" }
      else badge.style.display = "none"
      const sub = document.getElementById("subtitle-tarefas")
      if (sub) sub.textContent = `${pendentes} pendente(s) · ${res.data.length - pendentes} concluída(s)`
    }
  } catch (e) {}
  try {
    const res = await chamarAPI("get_lembretes")
    if (res.ok) {
      const total = res.data.length
      const badge = document.getElementById("badge-lembretes")
      if (total > 0) { badge.textContent = total > 9 ? "9+" : total; badge.style.display = "inline-block" }
      else badge.style.display = "none"
      const sub = document.getElementById("subtitle-lembretes")
      if (sub) sub.textContent = `${total} lembrete(s) ativo(s)`
    }
  } catch (e) {}
  try {
    const res = await chamarAPI("get_habitos")
    if (res.ok) {
      const feitos = res.data.filter(h => h.feito_hoje).length
      const sub = document.getElementById("subtitle-habitos")
      if (sub) sub.textContent = `${feitos}/${res.data.length} feitos hoje`
    }
  } catch (e) {}
}

async function atualizarKeyDot() {
  try {
    const res = await chamarAPI("get_api_key")
    const dot1 = document.getElementById("key-dot")
    const dot2 = document.getElementById("key-dot-modal")
    const status = document.getElementById("key-status")
    const ok = res.ok && res.data.tem_key
    if (dot1) dot1.classList.toggle("configured", ok)
    if (dot2) dot2.classList.toggle("configured", ok)
    if (status) status.textContent = ok ? "✓ Configurada e pronta" : "⚠ Não configurada"
  } catch (e) {}
}

function trocarAba(aba) {
  document.querySelectorAll(".aba").forEach(a => a.classList.remove("active"))
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"))
  document.getElementById(`aba-${aba}`).classList.add("active")
  document.querySelector(`[data-aba="${aba}"]`).classList.add("active")
  if (aba === "tarefas")   carregarTarefas()
  if (aba === "lembretes") carregarLembretes()
  if (aba === "habitos")   carregarHabitos()
  if (aba === "foco")      atualizarStatsFoco()
}

async function abrirUltimaConversa() {
  const res = await chamarAPI("get_sessoes")
  if (!res.ok || !res.data || res.data.length === 0) { await novaConversa(); return }
  const ultima = res.data[0]
  sessaoAtual = ultima.id
  await carregarSessoes()
  marcarSessaoAtiva(sessaoAtual)
  const hist = await chamarAPI("get_historico", ultima.id)
  if (hist.ok) {
    const msgs = document.getElementById("chat-msgs")
    msgs.innerHTML = ""
    hist.data.forEach(m => adicionarMensagem(m.role === "user" ? "user" : "nova", m.content))
  }
}

async function novaConversa() {
  const res = await chamarAPI("nova_sessao")
  if (!res.ok) return
  sessaoAtual = res.data.sessao_id
  document.getElementById("chat-msgs").innerHTML = ""
  await carregarSessoes()
  marcarSessaoAtiva(sessaoAtual)
}

async function carregarSessoes() {
  const res = await chamarAPI("get_sessoes")
  if (!res.ok) return
  const lista = document.getElementById("lista-sessoes")
  lista.innerHTML = ""
  res.data.forEach(s => {
    const f = document.createElement("div")
    f.className = "sessao-item" + (s.id === sessaoAtual ? " ativa" : "")
    f.dataset.id = s.id
    f.innerHTML = `<span class="sessao-titulo">💬 ${escapeHTML(s.titulo)}</span><button class="sessao-del" onclick="deletarSessao(${s.id}, event)">✕</button>`
    f.addEventListener("click", () => abrirSessao(s.id))
    lista.appendChild(f)
  })
}

function marcarSessaoAtiva(id) {
  document.querySelectorAll(".sessao-item").forEach(el => {
    el.classList.toggle("ativa", parseInt(el.dataset.id) === id)
  })
}

async function abrirSessao(id) {
  sessaoAtual = id
  marcarSessaoAtiva(id)
  trocarAba("chat")
  const res = await chamarAPI("get_historico", id)
  if (!res.ok) return
  const msgs = document.getElementById("chat-msgs")
  msgs.innerHTML = ""
  res.data.forEach(m => adicionarMensagem(m.role === "user" ? "user" : "nova", m.content))
}

async function deletarSessao(id, e) {
  e.stopPropagation()
  await chamarAPI("deletar_sessao", id)
  if (sessaoAtual === id) {
    const res = await chamarAPI("get_sessoes")
    if (res.ok && res.data.length > 0) await abrirSessao(res.data[0].id)
    else await novaConversa()
  } else await carregarSessoes()
}

async function carregarResumoMatinal() {
  const res = await chamarAPI("get_resumo_matinal")
  if (!res.ok) return
  adicionarMensagem("nova", res.data.resumo, "resumo")
}

function adicionarMensagem(tipo, texto, extraClass = "") {
  const msgs = document.getElementById("chat-msgs")
  const div = document.createElement("div")
  div.className = `msg ${tipo}${extraClass ? " " + extraClass : ""}`
  const hora = agoraHora()

  if (tipo === "nova") {
    const isResumo = extraClass === "resumo"
    div.innerHTML = `
      <div class="msg-avatar">N</div>
      <div class="msg-content">
        <div class="bubble ${isResumo ? "" : "markdown"}">${isResumo ? escapeHTML(texto).replace(/\n/g, "<br>") : renderMarkdown(texto)}</div>
        <div class="msg-meta">${hora}</div>
        ${!isResumo ? `
          <div class="msg-actions">
            <button class="msg-action-btn" onclick="copiarMensagem(this)" title="Copiar">
              <svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              Copiar
            </button>
            <button class="msg-action-btn" onclick="regenerarMensagem(this)" title="Regenerar">
              <svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
              Regenerar
            </button>
          </div>
        ` : ""}
      </div>
    `
    if (!extraClass) { div.classList.add("nova-flash"); ultimaMsgNova = div }
    div.querySelector(".bubble").addEventListener("contextmenu", (e) => {
      e.preventDefault()
      contextMsgEl = div
      mostrarContextMenu(e.clientX, e.clientY)
    })
  } else if (tipo === "user") {
    div.innerHTML = `
      <div class="msg-content">
        <div class="bubble">${escapeHTML(texto).replace(/\n/g, "<br>")}</div>
        <div class="msg-meta">${hora}</div>
      </div>
    `
  } else {
    div.innerHTML = `<div class="bubble">${escapeHTML(texto).replace(/\n/g, "<br>")}</div>`
    div.classList.add("muted")
  }

  msgs.appendChild(div)
  msgs.scrollTop = msgs.scrollHeight
  return div
}

function adicionarMensagemImagem(texto, base64Img) {
  const msgs = document.getElementById("chat-msgs")
  const div = document.createElement("div")
  div.className = "msg nova nova-flash"
  const hora = agoraHora()
  div.innerHTML = `
    <div class="msg-avatar">N</div>
    <div class="msg-content">
      <div class="bubble" style="padding:8px">
        <img src="${base64Img}" style="max-width:260px; max-height:260px; border-radius:8px; display:block; margin-bottom:6px"/>
        <span>${escapeHTML(texto)}</span>
      </div>
      <div class="msg-meta">${hora}</div>
    </div>
  `
  msgs.appendChild(div)
  msgs.scrollTop = msgs.scrollHeight
  return div
}

function copiarMensagem(btn) {
  const bubble = btn.closest(".msg-content").querySelector(".bubble")
  const texto = bubble.innerText
  navigator.clipboard.writeText(texto).then(() => {
    showToast("Copiado!", "Mensagem copiada pra área de transferência", "success", 1800)
  }).catch(() => showToast("Erro ao copiar", "", "error", 2000))
}

function regenerarMensagem(btn) {
  const msgNova = btn.closest(".msg")
  let prev = msgNova.previousElementSibling
  while (prev && !prev.classList.contains("user")) prev = prev.previousElementSibling
  if (!prev) return
  const texto = prev.querySelector(".bubble").innerText
  msgNova.remove()
  reenviarSemMostrar(texto)
}

async function reenviarSemMostrar(texto) {
  const btn = document.getElementById("chat-send")
  btn.disabled = true
  adicionarTyping()
  let streamingDiv = null

  window.__novaPrimeiroChunk = function() {
    removerTyping()
    if (streamingDiv) return
    const msgs = document.getElementById("chat-msgs")
    streamingDiv = document.createElement("div")
    streamingDiv.className = "msg nova nova-flash"
    const hora = agoraHora()
    streamingDiv.innerHTML = `
      <div class="msg-avatar">N</div>
      <div class="msg-content">
        <div class="bubble markdown" id="streaming-bubble"><span class="streaming-cursor">▍</span></div>
        <div class="msg-meta">${hora}</div>
        <div class="msg-actions">
          <button class="msg-action-btn" onclick="copiarMensagem(this)"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copiar</button>
          <button class="msg-action-btn" onclick="regenerarMensagem(this)"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Regenerar</button>
        </div>
      </div>
    `
    msgs.appendChild(streamingDiv)
    msgs.scrollTop = msgs.scrollHeight
  }

  await chamarAPI("enviar_mensagem_stream", sessaoAtual, texto)
  btn.disabled = false
  removerTyping()
  const bubble = document.getElementById("streaming-bubble")
  if (bubble) {
    bubble.removeAttribute("id")
    const cursor = bubble.querySelector(".streaming-cursor")
    if (cursor) cursor.remove()
  }
  await carregarSessoes()
  marcarSessaoAtiva(sessaoAtual)
}

function mostrarContextMenu(x, y) {
  const menu = document.getElementById("context-menu")
  menu.style.left = x + "px"
  menu.style.top = y + "px"
  menu.classList.add("visible")
}

function ctxCopy() {
  if (!contextMsgEl) return
  const bubble = contextMsgEl.querySelector(".bubble")
  if (bubble) { navigator.clipboard.writeText(bubble.innerText); showToast("Copiado!", "", "success", 1500) }
  document.getElementById("context-menu").classList.remove("visible")
}

function ctxRegenerate() {
  if (!contextMsgEl) return
  const btn = contextMsgEl.querySelector(".msg-action-btn[title='Regenerar']")
  if (btn) regenerarMensagem(btn)
  document.getElementById("context-menu").classList.remove("visible")
}

function ctxDelete() {
  if (!contextMsgEl) return
  contextMsgEl.remove()
  showToast("Mensagem removida", "", "info", 1500)
  document.getElementById("context-menu").classList.remove("visible")
}

let imagemChatB64 = null

function previewImagem(event) {
  const file = event.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = e => {
    imagemChatB64 = e.target.result
    document.getElementById("chat-preview-img").src = imagemChatB64
    document.getElementById("chat-preview-wrap").style.display = "flex"
  }
  reader.readAsDataURL(file)
}

function removerImagem() {
  imagemChatB64 = null
  document.getElementById("chat-preview-wrap").style.display = "none"
  document.getElementById("chat-preview-img").src = ""
  document.getElementById("chat-imagem").value = ""
}

function scrollChatBottom() {
  const msgs = document.getElementById("chat-msgs")
  msgs.scrollTop = msgs.scrollHeight
  document.getElementById("scroll-bottom-btn").classList.remove("visible")
}

function adicionarTyping() {
  const msgs = document.getElementById("chat-msgs")
  const div = document.createElement("div")
  div.className = "msg nova"
  div.id = "typing-msg"
  div.innerHTML = `<div class="msg-avatar">N</div><div class="bubble" style="padding:0"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`
  msgs.appendChild(div)
  msgs.scrollTop = msgs.scrollHeight
}

function removerTyping() {
  const t = document.getElementById("typing-msg")
  if (t) t.remove()
}

function showProgressBar() { document.getElementById("chat-progress-bar").classList.add("active") }
function hideProgressBar() { document.getElementById("chat-progress-bar").classList.remove("active") }

async function enviarMensagem() {
  const input = document.getElementById("chat-input")
  const texto = input.value.trim()
  const imagemEnviada = imagemChatB64
  if (!texto && !imagemEnviada) return
  if (!sessaoAtual) return

  input.value = ""
  input.style.height = "auto"

  if (imagemEnviada) {
    const msgs = document.getElementById("chat-msgs")
    const div = document.createElement("div")
    div.className = "msg user"
    const hora = agoraHora()
    div.innerHTML = `
      <div class="msg-content">
        <div class="bubble" style="padding:6px">
          <img src="${imagemEnviada}" style="max-width:200px; max-height:200px; border-radius:8px; display:block"/>
          ${texto ? `<span style="display:block; margin-top:6px">${escapeHTML(texto)}</span>` : ""}
        </div>
        <div class="msg-meta">${hora}</div>
      </div>
    `
    msgs.appendChild(div)
    msgs.scrollTop = msgs.scrollHeight
  } else adicionarMensagem("user", texto)

  removerImagem()
  const btn = document.getElementById("chat-send")
  btn.disabled = true
  showProgressBar()

  if (imagemEnviada) {
    adicionarTyping()
    const res = await chamarAPI("chat_imagem", sessaoAtual, texto, imagemEnviada)
    removerTyping(); btn.disabled = false; hideProgressBar()
    if (res.ok) {
      if (res.data.tipo === "imagem") adicionarMensagemImagem(res.data.resposta, res.data.imagem_base64)
      else adicionarMensagem("nova", res.data.resposta)
      await carregarSessoes(); marcarSessaoAtiva(sessaoAtual)
    } else { adicionarMensagem("nova", `❌ ${res.erro}`); showToast("Erro", res.erro, "error") }
    return
  }

  adicionarTyping()
  let streamingDiv = null

  window.__novaPrimeiroChunk = function() {
    removerTyping(); hideProgressBar()
    if (streamingDiv) return
    const msgs = document.getElementById("chat-msgs")
    streamingDiv = document.createElement("div")
    streamingDiv.className = "msg nova nova-flash"
    const hora = agoraHora()
    streamingDiv.innerHTML = `
      <div class="msg-avatar">N</div>
      <div class="msg-content">
        <div class="bubble markdown" id="streaming-bubble"><span class="streaming-cursor">▍</span></div>
        <div class="msg-meta">${hora}</div>
        <div class="msg-actions">
          <button class="msg-action-btn" onclick="copiarMensagem(this)" title="Copiar"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copiar</button>
          <button class="msg-action-btn" onclick="regenerarMensagem(this)" title="Regenerar"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Regenerar</button>
        </div>
      </div>
    `
    msgs.appendChild(streamingDiv)
    msgs.scrollTop = msgs.scrollHeight
    ultimaMsgNova = streamingDiv
  }

  const res = await chamarAPI("enviar_mensagem_stream", sessaoAtual, texto)
  btn.disabled = false; removerTyping(); hideProgressBar()

  const bubble = document.getElementById("streaming-bubble")
  if (bubble) {
    bubble.removeAttribute("id")
    const cursor = bubble.querySelector(".streaming-cursor")
    if (cursor) cursor.remove()
  } else if (!res.ok) {
    adicionarMensagem("nova", `❌ ${res.erro}`)
    showToast("Erro", res.erro, "error")
  }

  await carregarSessoes()
  marcarSessaoAtiva(sessaoAtual)
}

window.__novaChunk = function(texto) {
  if (!document.getElementById("streaming-bubble")) window.__novaPrimeiroChunk()
  const bubble = document.getElementById("streaming-bubble")
  if (!bubble) return
  const cursor = bubble.querySelector(".streaming-cursor")
  if (cursor) cursor.remove()
  bubble.appendChild(document.createTextNode(texto))
  if (cursor) bubble.appendChild(cursor)
  const msgs = document.getElementById("chat-msgs")
  const perto = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 100
  if (perto) msgs.scrollTop = msgs.scrollHeight
}

window.__novaFim = function() {
  const bubble = document.getElementById("streaming-bubble")
  if (!bubble) return
  bubble.removeAttribute("id")
  const cursor = bubble.querySelector(".streaming-cursor")
  if (cursor) cursor.remove()
}

window.__novaErro = function(msg) {
  if (!document.getElementById("streaming-bubble")) window.__novaPrimeiroChunk()
  const bubble = document.getElementById("streaming-bubble")
  if (!bubble) return
  bubble.removeAttribute("id")
  bubble.textContent = `❌ ${msg}`
  showToast("Erro", msg, "error")
}

window.__novaAgenteAcao = function(tipo, descricao) {
  const icones = { tarefa: "✅", lembrete: "⏰", listar: "📋" }
  showToast(`${icones[tipo] || "✨"} Ação executada`, descricao, "success", 3000)
  atualizarBadges()
}

function abrirModalConfig() {
  document.getElementById("modal-config").style.display = "flex"
  atualizarKeyDot()
}

function toggleSetting(key, el) {
  el.classList.toggle("on")
  settings[key] = el.classList.contains("on")
  if (key === "particles") criarParticulas()
}

async function salvarConfig() {
  const key = document.getElementById("input-key").value.trim()
  if (key) {
    await chamarAPI("salvar_api_key", key)
    showToast("API Key salva!", "", "success", 2000)
  }
  fecharModal("modal-config")
  await atualizarKeyDot()
}

function mostrarSkeleton(lista, n = 3) {
  lista.innerHTML = ""
  for (let i = 0; i < n; i++) {
    const sk = document.createElement("div")
    sk.className = "skeleton-card"
    sk.innerHTML = `<div style="flex:1"><div class="skeleton-line medium"></div><div class="skeleton-line short"></div></div>`
    lista.appendChild(sk)
  }
}

async function carregarTarefas() {
  const lista = document.getElementById("lista-tarefas")
  mostrarSkeleton(lista)
  const res = await chamarAPI("get_tarefas")
  if (!res.ok) { lista.innerHTML = ""; return }
  lista.innerHTML = ""
  const pendentes = res.data.filter(t => t.status === "pendente")
  const concluidas = res.data.filter(t => t.status === "concluida")
  if (!res.data.length) {
    lista.innerHTML = `<div class="empty-msg"><div class="empty-icon">✅</div><div class="empty-title">Sem tarefas</div><div class="empty-desc">Nenhuma tarefa ainda. Que tal criar uma?</div></div>`
    return
  }
  if (pendentes.length) {
    lista.innerHTML += `<div class="secao-label">PENDENTES</div>`
    pendentes.forEach((t, i) => {
      const card = cardTarefa(t)
      if (i === 0) card.classList.add("slide-in")
      lista.appendChild(card)
    })
  }
  if (concluidas.length) {
    lista.innerHTML += `<div class="secao-label">CONCLUÍDAS</div>`
    concluidas.slice(0, 5).forEach(t => lista.appendChild(cardTarefa(t, true)))
  }
}

function cardTarefa(t, concluida = false) {
  const cores = { alta: "#dc2626", media: "#d97706", baixa: "#059669" }
  const cor = cores[t.prioridade] || "#a1a29e"
  const div = document.createElement("div")
  div.className = "card"
  div.innerHTML = `
    <div class="prio-bar" style="background:${cor}"></div>
    <div class="card-left">
      <div class="card-titulo ${concluida ? "concluida" : ""}">${escapeHTML(t.titulo)}</div>
      <div class="card-meta">
        ${t.projeto ? `<span style="color:${t.cor_projeto||'#7a7890'}">[${t.projeto}]</span>` : ""}
        ${t.prazo ? `<span>📅 ${t.prazo.slice(0,10)}</span>` : ""}
        <span>${t.prioridade}</span>
      </div>
    </div>
    <div class="card-btns">
      ${!concluida ? `<button class="btn-icon" onclick="concluirTarefa(${t.id})">✓</button>` : ""}
      <button class="btn-icon" onclick="deletarTarefa(${t.id})">✕</button>
    </div>
  `
  return div
}

function abrirModalTarefa() {
  document.getElementById("modal-tarefa").style.display = "flex"
  document.getElementById("tarefa-titulo").focus()
}

async function criarTarefa() {
  const titulo = document.getElementById("tarefa-titulo").value.trim()
  const desc = document.getElementById("tarefa-desc").value.trim()
  const prazo = document.getElementById("tarefa-prazo").value || null
  const prioridade = document.querySelector('input[name="prio"]:checked')?.value || "media"
  if (!titulo) return
  await chamarAPI("criar_tarefa", titulo, desc, null, prioridade, prazo)
  fecharModal("modal-tarefa")
  document.getElementById("tarefa-titulo").value = ""
  document.getElementById("tarefa-desc").value = ""
  document.getElementById("tarefa-prazo").value = ""
  await carregarTarefas()
  await atualizarBadges()
  showToast("Tarefa criada!", titulo, "success", 2500)
}

async function concluirTarefa(id) {
  await chamarAPI("concluir_tarefa", id)
  await carregarTarefas()
  await atualizarBadges()
  showToast("Tarefa concluída!", "Boa, chefe! 👏", "success", 2200)
}

async function deletarTarefa(id) {
  await chamarAPI("deletar_tarefa", id)
  await carregarTarefas()
  await atualizarBadges()
}

async function carregarLembretes() {
  const lista = document.getElementById("lista-lembretes")
  mostrarSkeleton(lista)
  const res = await chamarAPI("get_lembretes")
  if (!res.ok) { lista.innerHTML = ""; return }
  lista.innerHTML = ""
  if (!res.data.length) {
    lista.innerHTML = `<div class="empty-msg"><div class="empty-icon">⏰</div><div class="empty-title">Sem lembretes</div><div class="empty-desc">Nenhum lembrete ativo no momento.</div></div>`
    return
  }
  res.data.forEach(l => {
    const div = document.createElement("div")
    div.className = "card"
    const data = l.data_hora.slice(0,16).replace("T"," ")
    const rep = l.repetir !== "nunca" ? ` • repete ${l.repetir}` : ""
    div.innerHTML = `
      <div class="card-left">
        <div class="card-titulo">⏰ ${escapeHTML(l.titulo)}</div>
        <div class="card-meta"><span>${data}${rep}</span></div>
      </div>
      <div class="card-btns"><button class="btn-icon" onclick="deletarLembrete(${l.id})">✕</button></div>
    `
    lista.appendChild(div)
  })
}

function abrirModalLembrete() {
  const agora = new Date()
  agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset())
  document.getElementById("lembrete-data").value = agora.toISOString().slice(0,16)
  document.getElementById("modal-lembrete").style.display = "flex"
  document.getElementById("lembrete-titulo").focus()
}

async function criarLembrete() {
  const titulo = document.getElementById("lembrete-titulo").value.trim()
  const dataHora = document.getElementById("lembrete-data").value
  const repetir = document.querySelector('input[name="rep"]:checked')?.value || "nunca"
  if (!titulo || !dataHora) return
  await chamarAPI("criar_lembrete", titulo, dataHora, "", repetir)
  fecharModal("modal-lembrete")
  document.getElementById("lembrete-titulo").value = ""
  await carregarLembretes()
  await atualizarBadges()
  showToast("Lembrete criado!", titulo, "success", 2500)
}

async function deletarLembrete(id) {
  await chamarAPI("deletar_lembrete", id)
  await carregarLembretes()
  await atualizarBadges()
}

async function carregarHabitos() {
  const lista = document.getElementById("lista-habitos")
  mostrarSkeleton(lista)
  const res = await chamarAPI("get_habitos")
  if (!res.ok) { lista.innerHTML = ""; return }
  lista.innerHTML = ""
  if (!res.data.length) {
    lista.innerHTML = `<div class="empty-msg"><div class="empty-icon">📊</div><div class="empty-title">Sem hábitos</div><div class="empty-desc">Nenhum hábito ainda. Crie um pra começar!</div></div>`
    return
  }
  const hoje = new Date().toLocaleDateString("pt-BR")
  lista.innerHTML = `<div class="secao-label">HOJE — ${hoje}</div>`
  res.data.forEach(h => {
    const div = document.createElement("div")
    div.className = "card"
    div.style.flexDirection = "column"
    div.style.alignItems = "stretch"
    div.innerHTML = `
      <div style="display:flex; align-items:center; gap:12px; width:100%;">
        <button class="habito-check ${h.feito_hoje ? "feito" : ""}" onclick="toggleHabito(${h.id})">${h.feito_hoje ? "✓" : "○"}</button>
        <div class="card-left">
          <div class="card-titulo">${h.icone} ${escapeHTML(h.nome)}</div>
          <div class="card-meta streak">🔥 ${h.streak} dias</div>
        </div>
        <div class="card-btns"><button class="btn-icon" onclick="deletarHabito(${h.id})">✕</button></div>
      </div>
      <div class="habito-heatmap" id="heatmap-${h.id}"></div>
    `
    lista.appendChild(div)
    renderHeatmap(h.id, h.streak)
  })
}

function renderHeatmap(habitoId, streak) {
  const el = document.getElementById(`heatmap-${habitoId}`)
  if (!el) return
  el.innerHTML = ""
  const hoje = new Date()
  for (let i = 29; i >= 0; i--) {
    const d = new Date(hoje)
    d.setDate(d.getDate() - i)
    const cell = document.createElement("div")
    cell.className = "heat-cell"
    if (i < streak) cell.classList.add("filled")
    const dd = String(d.getDate()).padStart(2, "0")
    const mm = String(d.getMonth() + 1).padStart(2, "0")
    cell.title = `${dd}/${mm}`
    el.appendChild(cell)
  }
}

function abrirModalHabito() {
  document.getElementById("modal-habito").style.display = "flex"
  document.getElementById("habito-nome").focus()
}

async function criarHabito() {
  const nome = document.getElementById("habito-nome").value.trim()
  const icone = document.getElementById("habito-icone").value.trim() || "⭐"
  const cor = document.getElementById("habito-cor").value
  if (!nome) return
  await chamarAPI("criar_habito", nome, icone, cor)
  fecharModal("modal-habito")
  document.getElementById("habito-nome").value = ""
  await carregarHabitos()
  await atualizarBadges()
  showToast("Hábito criado!", nome, "success", 2200)
}

async function toggleHabito(id) {
  await chamarAPI("registrar_habito", id)
  await carregarHabitos()
  await atualizarBadges()
}

async function deletarHabito(id) {
  await chamarAPI("deletar_habito", id)
  await carregarHabitos()
  await atualizarBadges()
}

async function atualizarStatsFoco() {
  const res = await chamarAPI("get_stats_foco")
  if (!res.ok) return
  document.getElementById("foco-stats").textContent = `Hoje: ${res.data.sessoes} sessão(ões) • ${res.data.minutos} minutos`
}

const RING_CIRC = 2 * Math.PI * 110

function atualizarAnelFoco() {
  const ring = document.querySelector("#foco-ring .ring-fg")
  if (!ring) return
  const total = focoTotalSegundos || 1
  const pct = focoSegundos / total
  ring.style.strokeDashoffset = RING_CIRC * (1 - pct)
}

function focoIniciar() {
  const duracaoMin = parseInt(document.getElementById("foco-min").value) || 25
  const pausaMin = parseInt(document.getElementById("pausa-min").value) || 5
  focoFase = "foco"
  focoPausado = false
  focoSegundos = duracaoMin * 60
  focoTotalSegundos = focoSegundos
  document.getElementById("btn-foco-iniciar").disabled = true
  document.getElementById("btn-foco-pausar").disabled = false
  document.getElementById("btn-foco-cancelar").disabled = false
  document.getElementById("foco-fase").textContent = "🎯 FOCO"
  document.getElementById("foco-fase").style.color = "var(--violeta)"
  atualizarTimerDisplay(focoSegundos)
  atualizarAnelFoco()
  focoInterval = setInterval(() => {
    if (focoPausado) return
    focoSegundos--
    atualizarTimerDisplay(focoSegundos)
    atualizarAnelFoco()
    if (focoSegundos <= 0) {
      clearInterval(focoInterval)
      if (focoFase === "foco") {
        focoFase = "pausa"
        focoSegundos = pausaMin * 60
        focoTotalSegundos = focoSegundos
        document.getElementById("foco-fase").textContent = "☕ PAUSA"
        document.getElementById("foco-fase").style.color = "var(--warning)"
        atualizarAnelFoco()
        showToast("Foco concluído!", "Pausa começando", "success", 3000)
        focoInterval = setInterval(() => {
          if (focoPausado) return
          focoSegundos--
          atualizarTimerDisplay(focoSegundos)
          atualizarAnelFoco()
          if (focoSegundos <= 0) {
            clearInterval(focoInterval)
            chamarAPI("salvar_sessao_foco", duracaoMin, pausaMin, true)
            focoReset(duracaoMin)
            atualizarStatsFoco()
            showToast("Sessão completa!", "Bom trabalho! 🔥", "success", 3500)
          }
        }, 1000)
      }
    }
  }, 1000)
}

function focoPausar() {
  focoPausado = !focoPausado
  document.getElementById("btn-foco-pausar").textContent = focoPausado ? "▶ Retomar" : "⏸ Pausar"
}

function focoCancelar() {
  clearInterval(focoInterval)
  const duracaoMin = parseInt(document.getElementById("foco-min").value) || 25
  const pausaMin = parseInt(document.getElementById("pausa-min").value) || 5
  chamarAPI("salvar_sessao_foco", duracaoMin, pausaMin, false)
  focoReset(duracaoMin)
}

function focoReset(duracaoMin = 25) {
  clearInterval(focoInterval)
  focoSegundos = 0
  focoTotalSegundos = duracaoMin * 60
  focoPausado = false
  document.getElementById("btn-foco-iniciar").disabled = false
  document.getElementById("btn-foco-pausar").disabled = true
  document.getElementById("btn-foco-cancelar").disabled = true
  document.getElementById("btn-foco-pausar").textContent = "⏸ Pausar"
  document.getElementById("foco-fase").textContent = "FOCO"
  document.getElementById("foco-fase").style.color = "var(--violeta)"
  atualizarTimerDisplay(duracaoMin * 60)
  const ring = document.querySelector("#foco-ring .ring-fg")
  if (ring) ring.style.strokeDashoffset = 0
}

function atualizarTimerDisplay(seg) {
  const m = String(Math.floor(seg / 60)).padStart(2, "0")
  const s = String(seg % 60).padStart(2, "0")
  document.getElementById("foco-timer").textContent = `${m}:${s}`
}

async function selecionarImagem() {
  const res = await chamarAPI("abrir_arquivo_dialogo")
  if (!res.ok || !res.data) return
  imagemAtual = res.data.caminho
  const preview = document.getElementById("imagens-preview")
  const placeholder = document.getElementById("imagens-placeholder")
  preview.src = res.data.base64
  preview.style.display = "block"
  placeholder.style.display = "none"
  document.getElementById("imagens-info").textContent = `${res.data.largura}×${res.data.altura}px  •  ${res.data.nome}`
  document.getElementById("imagens-status").textContent = ""
}

async function processarImagem(operacao) {
  if (!imagemAtual) {
    document.getElementById("imagens-status").textContent = "⚠ Selecione uma imagem primeiro."
    document.getElementById("imagens-status").style.color = "var(--warning)"
    return
  }
  document.getElementById("imagens-status").textContent = "⏳ Processando..."
  document.getElementById("imagens-status").style.color = "var(--muted)"
  let params = {}
  if (operacao === "melhorar") {
    params = {
      nitidez: parseFloat(document.getElementById("sl-nitidez").value),
      brilho: parseFloat(document.getElementById("sl-brilho").value),
      contraste: parseFloat(document.getElementById("sl-contraste").value),
      cor: parseFloat(document.getElementById("sl-cor").value),
    }
  } else if (operacao === "aumentar") {
    params = { escala: parseInt(document.querySelector('input[name="escala"]:checked').value) }
  } else if (operacao === "instagram") {
    params = { formato: document.getElementById("formato-instagram").value }
  } else if (operacao === "trocar_fundo") {
    params = { cor: hexParaRgb(document.getElementById("cor-fundo").value) }
  }
  const res = await chamarAPI("processar_imagem", imagemAtual, operacao, params)
  if (res.ok) {
    const preview = document.getElementById("imagens-preview")
    preview.src = res.data.base64
    preview.style.display = "block"
    document.getElementById("imagens-placeholder").style.display = "none"
    document.getElementById("imagens-status").textContent = `✅ Salvo: ${res.data.caminho.split("\\").pop()}`
    document.getElementById("imagens-status").style.color = "var(--success)"
    showToast("Imagem processada!", res.data.operacao, "success", 2200)
  } else {
    document.getElementById("imagens-status").textContent = `❌ ${res.erro}`
    document.getElementById("imagens-status").style.color = "var(--danger)"
    showToast("Erro", res.erro, "error")
  }
}

function hexParaRgb(hex) {
  return [parseInt(hex.slice(1,3),16), parseInt(hex.slice(3,5),16), parseInt(hex.slice(5,7),16)]
}

async function aplicarEdicaoTexto() {
  if (!imagemAtual) {
    document.getElementById("imagens-status").textContent = "⚠ Selecione uma imagem primeiro."
    document.getElementById("imagens-status").style.color = "var(--warning)"
    return
  }
  const instrucao = document.getElementById("imagens-instrucao").value.trim()
  if (!instrucao) return
  document.getElementById("imagens-status").textContent = "🤔 Entendendo seu pedido..."
  document.getElementById("imagens-status").style.color = "var(--muted)"
  const res = await chamarAPI("interpretar_e_processar_imagem", imagemAtual, instrucao)
  if (res.ok) {
    const preview = document.getElementById("imagens-preview")
    preview.src = res.data.base64
    preview.style.display = "block"
    document.getElementById("imagens-placeholder").style.display = "none"
    document.getElementById("imagens-status").textContent = `✅ Aplicado: ${res.data.operacao} • Salvo: ${res.data.caminho.split("\\").pop()}`
    document.getElementById("imagens-status").style.color = "var(--success)"
  } else {
    document.getElementById("imagens-status").textContent = `❌ ${res.erro}`
    document.getElementById("imagens-status").style.color = "var(--danger)"
  }
}

function fecharModal(id) { document.getElementById(id).style.display = "none" }

document.addEventListener("click", e => {
  if (e.target.classList.contains("modal")) e.target.style.display = "none"
})