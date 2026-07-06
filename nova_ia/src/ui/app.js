// ═══════════════════════════════════════════════════════════════════════════════
// NOVA — app.js
// ═══════════════════════════════════════════════════════════════════════════════

// ── Estado global ─────────────────────────────────────────────────────────────
let sessaoAtual = null
let focoInterval = null
let focoSegundos = 0
let focoFase = "foco"
let focoPausado = false
let imagemAtual = null

// ── Utilitário: chama função Python via pywebview ─────────────────────────────
async function chamarAPI(fn, ...args) {
  try {
    const raw = await window.pywebview.api[fn](...args)
    return JSON.parse(raw)
  } catch (e) {
    console.error(`Erro ao chamar ${fn}:`, e)
    return { ok: false, erro: String(e) }
  }
}

// ── Inicialização ─────────────────────────────────────────────────────────────
window.addEventListener("pywebviewready", async () => {
  // Anexa TODOS os event listeners primeiro (síncrono). Assim a UI fica
  // clicável imediatamente, mesmo que o carregamento assíncrono falhe.
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => trocarAba(btn.dataset.aba))
  })

  document.getElementById("btn-nova-conversa").addEventListener("click", novaConversa)

  document.getElementById("chat-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      enviarMensagem()
    }
  })

  document.getElementById("chat-send").addEventListener("click", enviarMensagem)

  document.getElementById("cor-fundo").addEventListener("input", e => {
    document.getElementById("cor-fundo-label").textContent = e.target.value
  })

  // Agora sim: carrega os dados (best-effort, não trava a UI se falhar)
  try { await abrirUltimaConversa() } catch (e) { console.error("abrirUltimaConversa:", e) }
  try { await carregarResumoMatinal() } catch (e) { console.error("carregarResumoMatinal:", e) }
  try { await atualizarStatsFoco() } catch (e) { console.error("atualizarStatsFoco:", e) }
})

// ══════════════════════════════════════════════════════════════════════════════
// NAVEGAÇÃO
// ══════════════════════════════════════════════════════════════════════════════

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

// ══════════════════════════════════════════════════════════════════════════════
// CHAT
// ══════════════════════════════════════════════════════════════════════════════

// Ao abrir o app, continua a conversa mais recente em vez de criar uma nova
// em branco. Só cria uma nova se não houver nenhuma ainda.
async function abrirUltimaConversa() {
  const res = await chamarAPI("get_sessoes")
  if (!res.ok || !res.data || res.data.length === 0) {
    await novaConversa()
    return
  }
  const ultima = res.data[0]  // listar_sessoes já vem ordenado por criado_em DESC
  sessaoAtual = ultima.id
  await carregarSessoes()
  marcarSessaoAtiva(sessaoAtual)
  // Carrega o histórico direto — não chama abrirSessao/trocarAba porque a aba
  // chat já é a ativa por padrão no HTML.
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
    f.innerHTML = `
      <span class="sessao-titulo">💬 ${s.titulo}</span>
      <button class="sessao-del" onclick="deletarSessao(${s.id}, event)">✕</button>
    `
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

// Deletar sessão: remove de verdade do banco e troca para outra conversa
// existente em vez de sempre criar uma nova em branco (comportamento de
// "fechar aba", não apenas "limpar tela").
async function deletarSessao(id, e) {
  e.stopPropagation()
  await chamarAPI("deletar_sessao", id)

  if (sessaoAtual === id) {
    const res = await chamarAPI("get_sessoes")
    if (res.ok && res.data.length > 0) {
      await abrirSessao(res.data[0].id)
    } else {
      await novaConversa()
    }
  } else {
    await carregarSessoes()
  }
}

async function carregarResumoMatinal() {
  const res = await chamarAPI("get_resumo_matinal")
  if (!res.ok) return
  adicionarMensagem("nova", res.data.resumo)
}

function adicionarMensagem(tipo, texto) {
  const msgs = document.getElementById("chat-msgs")
  const div = document.createElement("div")
  div.className = `msg ${tipo}`

  if (tipo === "nova") {
    div.innerHTML = `
      <div class="msg-avatar">N</div>
      <div class="bubble">${escapeHTML(texto)}</div>
    `
  } else if (tipo === "user") {
    div.innerHTML = `<div class="bubble">${escapeHTML(texto)}</div>`
  } else {
    div.innerHTML = `<div class="bubble">${escapeHTML(texto)}</div>`
    div.classList.add("muted")
  }

  msgs.appendChild(div)
  msgs.scrollTop = msgs.scrollHeight
  return div
}

// Mensagem da NOVA contendo uma imagem (resultado de edição)
function adicionarMensagemImagem(texto, base64Img) {
  const msgs = document.getElementById("chat-msgs")
  const div = document.createElement("div")
  div.className = "msg nova"
  div.innerHTML = `
    <div class="msg-avatar">N</div>
    <div class="bubble" style="padding:8px">
      <img src="${base64Img}" style="max-width:260px; max-height:260px; border-radius:8px; display:block; margin-bottom:6px"/>
      <span>${escapeHTML(texto)}</span>
    </div>
  `
  msgs.appendChild(div)
  msgs.scrollTop = msgs.scrollHeight
  return div
}

// ── Imagem anexada no chat ──────────────────────────────────────────────────────

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
    div.innerHTML = `
      <div class="bubble" style="padding:6px">
        <img src="${imagemEnviada}" style="max-width:200px; max-height:200px; border-radius:8px; display:block"/>
        ${texto ? `<span style="display:block; margin-top:6px">${escapeHTML(texto)}</span>` : ""}
      </div>
    `
    msgs.appendChild(div)
    msgs.scrollTop = msgs.scrollHeight
  } else {
    adicionarMensagem("user", texto)
  }

  removerImagem()

  const btn = document.getElementById("chat-send")
  btn.disabled = true

  // ── Fluxo com imagem: sem streaming (a resposta é curta/édita imagem) ──
  if (imagemEnviada) {
    const pensando = adicionarMensagem("muted", "NOVA está olhando a imagem...")
    const res = await chamarAPI("chat_imagem", sessaoAtual, texto, imagemEnviada)
    pensando.remove()
    btn.disabled = false

    if (res.ok) {
      if (res.data.tipo === "imagem") {
        adicionarMensagemImagem(res.data.resposta, res.data.imagem_base64)
      } else {
        adicionarMensagem("nova", res.data.resposta)
      }
      await carregarSessoes()
      marcarSessaoAtiva(sessaoAtual)
    } else {
      adicionarMensagem("nova", `❌ ${res.erro}`)
    }
    return
  }

  // ── Fluxo de texto puro: STREAMING ──
  // Cria a bubble da NOVA vazia e marca com id para os handlers encontrarem
  const msgs = document.getElementById("chat-msgs")
  const divNova = document.createElement("div")
  divNova.className = "msg nova"
  divNova.innerHTML = `
    <div class="msg-avatar">N</div>
    <div class="bubble" id="streaming-bubble"><span class="streaming-cursor">▍</span></div>
  `
  msgs.appendChild(divNova)
  msgs.scrollTop = msgs.scrollHeight

  const res = await chamarAPI("enviar_mensagem_stream", sessaoAtual, texto)

  btn.disabled = false
  // Garantia: se o streaming travou e a bubble ainda tem o cursor, remove
  const bubble = document.getElementById("streaming-bubble")
  if (bubble) {
    bubble.removeAttribute("id")
    const cursor = bubble.querySelector(".streaming-cursor")
    if (cursor) cursor.remove()
  }

  if (!res.ok) {
    divNova.querySelector(".bubble").textContent = `❌ ${res.erro}`
  }

  await carregarSessoes()
  marcarSessaoAtiva(sessaoAtual)
}

// ── Handlers de streaming (chamados pelo Python via evaluate_js) ──────────────
// O Python envia chunks da resposta em tempo real. Estes handlers anexam o
// texto na bubble que estiver com id="streaming-bubble".

window.__novaChunk = function(texto) {
  const bubble = document.getElementById("streaming-bubble")
  if (!bubble) return
  // Remove o cursor temporário, anexa o texto, e re-adiciona o cursor no fim
  const cursor = bubble.querySelector(".streaming-cursor")
  if (cursor) cursor.remove()
  bubble.appendChild(document.createTextNode(texto))
  if (cursor) bubble.appendChild(cursor)
  const msgs = document.getElementById("chat-msgs")
  msgs.scrollTop = msgs.scrollHeight
}

window.__novaFim = function() {
  const bubble = document.getElementById("streaming-bubble")
  if (!bubble) return
  bubble.removeAttribute("id")
  const cursor = bubble.querySelector(".streaming-cursor")
  if (cursor) cursor.remove()
}

window.__novaErro = function(msg) {
  const bubble = document.getElementById("streaming-bubble")
  if (!bubble) return
  bubble.removeAttribute("id")
  bubble.textContent = `❌ ${msg}`
}

function escapeHTML(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>")
}

// ══════════════════════════════════════════════════════════════════════════════
// API KEY
// ══════════════════════════════════════════════════════════════════════════════

function abrirModalKey() {
  document.getElementById("modal-key").style.display = "flex"
  document.getElementById("input-key").focus()
}

async function salvarKey() {
  const key = document.getElementById("input-key").value.trim()
  if (!key) return
  await chamarAPI("salvar_api_key", key)
  fecharModal("modal-key")
}

// ══════════════════════════════════════════════════════════════════════════════
// TAREFAS
// ══════════════════════════════════════════════════════════════════════════════

async function carregarTarefas() {
  const res = await chamarAPI("get_tarefas")
  if (!res.ok) return
  const lista = document.getElementById("lista-tarefas")
  lista.innerHTML = ""

  const pendentes  = res.data.filter(t => t.status === "pendente")
  const concluidas = res.data.filter(t => t.status === "concluida")

  if (!res.data.length) {
    lista.innerHTML = `<p class="empty-msg">Nenhuma tarefa ainda. Que tal criar uma?</p>`
    return
  }

  if (pendentes.length) {
    lista.innerHTML += `<div class="secao-label">PENDENTES</div>`
    pendentes.forEach(t => lista.appendChild(cardTarefa(t)))
  }

  if (concluidas.length) {
    lista.innerHTML += `<div class="secao-label">CONCLUÍDAS</div>`
    concluidas.slice(0, 5).forEach(t => lista.appendChild(cardTarefa(t, true)))
  }
}

function cardTarefa(t, concluida = false) {
  const cores = { alta: "#ff5f5f", media: "#ffb347", baixa: "#1de9b6" }
  const cor = cores[t.prioridade] || "#7a7890"
  const div = document.createElement("div")
  div.className = "card"
  div.innerHTML = `
    <div class="prio-bar" style="background:${cor}"></div>
    <div class="card-left">
      <div class="card-titulo ${concluida ? "concluida" : ""}">${escapeHTML(t.titulo)}</div>
      <div class="card-meta">
        ${t.projeto ? `<span style="color:${t.cor_projeto||'#7a7890'}">[${t.projeto}]</span>` : ""}
        ${t.prazo   ? `<span>📅 ${t.prazo.slice(0,10)}</span>` : ""}
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
  const titulo    = document.getElementById("tarefa-titulo").value.trim()
  const desc      = document.getElementById("tarefa-desc").value.trim()
  const prazo     = document.getElementById("tarefa-prazo").value || null
  const prioridade = document.querySelector('input[name="prio"]:checked')?.value || "media"
  if (!titulo) return
  await chamarAPI("criar_tarefa", titulo, desc, null, prioridade, prazo)
  fecharModal("modal-tarefa")
  document.getElementById("tarefa-titulo").value = ""
  document.getElementById("tarefa-desc").value = ""
  document.getElementById("tarefa-prazo").value = ""
  await carregarTarefas()
}

async function concluirTarefa(id) {
  await chamarAPI("concluir_tarefa", id)
  await carregarTarefas()
}

async function deletarTarefa(id) {
  await chamarAPI("deletar_tarefa", id)
  await carregarTarefas()
}

// ══════════════════════════════════════════════════════════════════════════════
// LEMBRETES
// ══════════════════════════════════════════════════════════════════════════════

async function carregarLembretes() {
  const res = await chamarAPI("get_lembretes")
  if (!res.ok) return
  const lista = document.getElementById("lista-lembretes")
  lista.innerHTML = ""

  if (!res.data.length) {
    lista.innerHTML = `<p class="empty-msg">Nenhum lembrete ativo.</p>`
    return
  }

  res.data.forEach(l => {
    const div = document.createElement("div")
    div.className = "card"
    const data = l.data_hora.slice(0,16).replace("T"," ")
    const rep  = l.repetir !== "nunca" ? ` • repete ${l.repetir}` : ""
    div.innerHTML = `
      <div class="card-left">
        <div class="card-titulo">⏰ ${escapeHTML(l.titulo)}</div>
        <div class="card-meta"><span>${data}${rep}</span></div>
      </div>
      <div class="card-btns">
        <button class="btn-icon" onclick="deletarLembrete(${l.id})">✕</button>
      </div>
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
  const titulo   = document.getElementById("lembrete-titulo").value.trim()
  const dataHora = document.getElementById("lembrete-data").value
  const repetir  = document.querySelector('input[name="rep"]:checked')?.value || "nunca"
  if (!titulo || !dataHora) return
  await chamarAPI("criar_lembrete", titulo, dataHora, "", repetir)
  fecharModal("modal-lembrete")
  document.getElementById("lembrete-titulo").value = ""
  await carregarLembretes()
}

async function deletarLembrete(id) {
  await chamarAPI("deletar_lembrete", id)
  await carregarLembretes()
}

// ══════════════════════════════════════════════════════════════════════════════
// HÁBITOS
// ══════════════════════════════════════════════════════════════════════════════

async function carregarHabitos() {
  const res = await chamarAPI("get_habitos")
  if (!res.ok) return
  const lista = document.getElementById("lista-habitos")
  lista.innerHTML = ""

  if (!res.data.length) {
    lista.innerHTML = `<p class="empty-msg">Nenhum hábito ainda. Crie um!</p>`
    return
  }

  const hoje = new Date().toLocaleDateString("pt-BR")
  lista.innerHTML = `<div class="secao-label">HOJE — ${hoje}</div>`

  res.data.forEach(h => {
    const div = document.createElement("div")
    div.className = "card"
    div.innerHTML = `
      <button class="habito-check ${h.feito_hoje ? "feito" : ""}"
              onclick="toggleHabito(${h.id})">${h.feito_hoje ? "✓" : "○"}</button>
      <div class="card-left">
        <div class="card-titulo">${h.icone} ${escapeHTML(h.nome)}</div>
        <div class="card-meta streak">🔥 ${h.streak} dias</div>
      </div>
      <div class="card-btns">
        <button class="btn-icon" onclick="deletarHabito(${h.id})">✕</button>
      </div>
    `
    lista.appendChild(div)
  })
}

function abrirModalHabito() {
  document.getElementById("modal-habito").style.display = "flex"
  document.getElementById("habito-nome").focus()
}

async function criarHabito() {
  const nome  = document.getElementById("habito-nome").value.trim()
  const icone = document.getElementById("habito-icone").value.trim() || "⭐"
  const cor   = document.getElementById("habito-cor").value
  if (!nome) return
  await chamarAPI("criar_habito", nome, icone, cor)
  fecharModal("modal-habito")
  document.getElementById("habito-nome").value = ""
  await carregarHabitos()
}

async function toggleHabito(id) {
  await chamarAPI("registrar_habito", id)
  await carregarHabitos()
}

async function deletarHabito(id) {
  await chamarAPI("deletar_habito", id)
  await carregarHabitos()
}

// ══════════════════════════════════════════════════════════════════════════════
// FOCO
// ══════════════════════════════════════════════════════════════════════════════

async function atualizarStatsFoco() {
  const res = await chamarAPI("get_stats_foco")
  if (!res.ok) return
  document.getElementById("foco-stats").textContent =
    `Hoje: ${res.data.sessoes} sessão(ões) • ${res.data.minutos} minutos`
}

function focoIniciar() {
  const duracaoMin = parseInt(document.getElementById("foco-min").value) || 25
  const pausaMin   = parseInt(document.getElementById("pausa-min").value) || 5

  focoFase    = "foco"
  focoPausado = false
  focoSegundos = duracaoMin * 60

  document.getElementById("btn-foco-iniciar").disabled  = true
  document.getElementById("btn-foco-pausar").disabled   = false
  document.getElementById("btn-foco-cancelar").disabled = false
  document.getElementById("foco-fase").textContent = "🎯 FOCO"
  document.getElementById("foco-fase").style.color = "var(--teal)"

  focoInterval = setInterval(() => {
    if (focoPausado) return
    focoSegundos--
    atualizarTimerDisplay(focoSegundos)

    if (focoSegundos <= 0) {
      clearInterval(focoInterval)
      if (focoFase === "foco") {
        focoFase = "pausa"
        focoSegundos = pausaMin * 60
        document.getElementById("foco-fase").textContent = "☕ PAUSA"
        document.getElementById("foco-fase").style.color = "var(--warning)"
        focoInterval = setInterval(() => {
          if (focoPausado) return
          focoSegundos--
          atualizarTimerDisplay(focoSegundos)
          if (focoSegundos <= 0) {
            clearInterval(focoInterval)
            chamarAPI("salvar_sessao_foco", duracaoMin, pausaMin, true)
            focoReset(duracaoMin)
            atualizarStatsFoco()
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
  const pausaMin   = parseInt(document.getElementById("pausa-min").value) || 5
  chamarAPI("salvar_sessao_foco", duracaoMin, pausaMin, false)
  focoReset(duracaoMin)
}

function focoReset(duracaoMin = 25) {
  clearInterval(focoInterval)
  focoSegundos = 0
  focoPausado  = false
  document.getElementById("btn-foco-iniciar").disabled  = false
  document.getElementById("btn-foco-pausar").disabled   = true
  document.getElementById("btn-foco-cancelar").disabled = true
  document.getElementById("btn-foco-pausar").textContent = "⏸ Pausar"
  document.getElementById("foco-fase").textContent = "FOCO"
  document.getElementById("foco-fase").style.color = "var(--teal)"
  atualizarTimerDisplay(duracaoMin * 60)
}

function atualizarTimerDisplay(seg) {
  const m = String(Math.floor(seg / 60)).padStart(2, "0")
  const s = String(seg % 60).padStart(2, "0")
  document.getElementById("foco-timer").textContent = `${m}:${s}`
}

// ══════════════════════════════════════════════════════════════════════════════
// IMAGENS (aba dedicada)
// ══════════════════════════════════════════════════════════════════════════════

async function selecionarImagem() {
  const res = await chamarAPI("abrir_arquivo_dialogo")
  if (!res.ok || !res.data) return

  imagemAtual = res.data.caminho
  const preview = document.getElementById("imagens-preview")
  const placeholder = document.getElementById("imagens-placeholder")
  preview.src = res.data.base64
  preview.style.display = "block"
  placeholder.style.display = "none"
  document.getElementById("imagens-info").textContent =
    `${res.data.largura}×${res.data.altura}px  •  ${res.data.nome}`
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
      nitidez:   parseFloat(document.getElementById("sl-nitidez").value),
      brilho:    parseFloat(document.getElementById("sl-brilho").value),
      contraste: parseFloat(document.getElementById("sl-contraste").value),
      cor:       parseFloat(document.getElementById("sl-cor").value),
    }
  } else if (operacao === "aumentar") {
    params = { escala: parseInt(document.querySelector('input[name="escala"]:checked').value) }
  } else if (operacao === "instagram") {
    params = { formato: document.getElementById("formato-instagram").value }
  } else if (operacao === "trocar_fundo") {
    const hex = document.getElementById("cor-fundo").value
    params = { cor: hexParaRgb(hex) }
  }

  const res = await chamarAPI("processar_imagem", imagemAtual, operacao, params)

  if (res.ok) {
    const preview = document.getElementById("imagens-preview")
    preview.src = res.data.base64
    preview.style.display = "block"
    document.getElementById("imagens-placeholder").style.display = "none"
    document.getElementById("imagens-status").textContent =
      `✅ Salvo: ${res.data.caminho.split("\\").pop()}`
    document.getElementById("imagens-status").style.color = "var(--success)"
  } else {
    document.getElementById("imagens-status").textContent = `❌ ${res.erro}`
    document.getElementById("imagens-status").style.color = "var(--danger)"
  }
}

function hexParaRgb(hex) {
  const r = parseInt(hex.slice(1,3), 16)
  const g = parseInt(hex.slice(3,5), 16)
  const b = parseInt(hex.slice(5,7), 16)
  return [r, g, b]
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
    document.getElementById("imagens-status").textContent =
      `✅ Aplicado: ${res.data.operacao} • Salvo: ${res.data.caminho.split("\\").pop()}`
    document.getElementById("imagens-status").style.color = "var(--success)"
  } else {
    document.getElementById("imagens-status").textContent = `❌ ${res.erro}`
    document.getElementById("imagens-status").style.color = "var(--danger)"
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// MODAIS
// ══════════════════════════════════════════════════════════════════════════════

function fecharModal(id) {
  document.getElementById(id).style.display = "none"
}

document.addEventListener("click", e => {
  if (e.target.classList.contains("modal")) {
    e.target.style.display = "none"
  }
})

document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal").forEach(m => m.style.display = "none")
  }
})