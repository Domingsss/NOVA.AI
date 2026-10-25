let sessaoAtual = null;
let focoInterval = null;
let focoSegundos = 0;
let focoTotalSegundos = 0;
let focoFase = "foco";
let focoPausado = false;
let settings = { particles: true, animations: true, theme: "light" };
let ultimaMsgNova = null;
let contextMsgEl = null;
let cidadeDashboard = "Rio de Janeiro";
let gravadorVoz = null;
let gravandoVoz = false;
let vozNovaAtiva = true;
let modoGravacaoVoz = "native";
let timerGravacaoVoz = null;

function storageGet(chave, fallback = null) {
  try {
    return window.localStorage.getItem(chave) || fallback;
  } catch (e) {
    return fallback;
  }
}
function storageSet(chave, valor) {
  try {
    window.localStorage.setItem(chave, valor);
  } catch (e) {
    console.warn("Armazenamento local indisponível:", e);
  }
}

function atualizarControlesVoz() {
  document
    .querySelectorAll("#chat-mic,#topbar-mic")
    .forEach((el) => el?.classList.toggle("recording", gravandoVoz));
  const voz = document.getElementById("topbar-voice");
  if (voz) {
    voz.classList.toggle("muted", !vozNovaAtiva);
    voz.title = vozNovaAtiva ? "Silenciar voz da NOVA" : "Ativar voz da NOVA";
  }
}
function toggleVozNova() {
  vozNovaAtiva = !vozNovaAtiva;
  if (!vozNovaAtiva) pararVozLocal();
  storageSet("novaVozAtiva", vozNovaAtiva ? "1" : "0");
  atualizarControlesVoz();
  showToast(
    vozNovaAtiva ? "Voz da NOVA ativada" : "Voz da NOVA silenciada",
    "",
    "info",
    1800,
  );
}
let audioLocal = null;
let falaTicket = 0;
function pararVozLocal() {
  falaTicket++;
  if (audioLocal) { audioLocal.pause(); audioLocal = null; }
}
async function falarResposta(texto) {
  pararVozLocal();
  if (!vozNovaAtiva || !texto) return;
  const ticket = falaTicket;
  const tmp = document.createElement("div");
  tmp.innerHTML = renderMarkdown(texto);
  const plain = tmp.textContent.replace(/\s+/g, " ").trim().slice(0, 6000);
  if (!plain) return;
  try {
    const result = await chamarAPI("sintetizar_voz", plain);
    if (ticket !== falaTicket || !vozNovaAtiva) return;
    if (!result.ok) throw new Error(result.erro);
    audioLocal = new Audio(result.data.audio);
    await audioLocal.play();
  } catch (error) {
    if (ticket === falaTicket) showToast("Voz local indisponível", error.message, "error");
  }
}
function criarWav(amostras, sampleRate) {
  const total = amostras.reduce((n, a) => n + a.length, 0),
    buffer = new ArrayBuffer(44 + total * 2),
    view = new DataView(buffer);
  const texto = (offset, valor) => {
    for (let i = 0; i < valor.length; i++)
      view.setUint8(offset + i, valor.charCodeAt(i));
  };
  texto(0, "RIFF");
  view.setUint32(4, 36 + total * 2, true);
  texto(8, "WAVE");
  texto(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  texto(36, "data");
  view.setUint32(40, total * 2, true);
  let pos = 44;
  amostras.forEach((bloco) =>
    bloco.forEach((valor) => {
      const v = Math.max(-1, Math.min(1, valor));
      view.setInt16(pos, v < 0 ? v * 0x8000 : v * 0x7fff, true);
      pos += 2;
    }),
  );
  return new Blob([view], { type: "audio/wav" });
}
async function toggleGravacao() {
  if (gravandoVoz)
    return modoGravacaoVoz === "browser"
      ? pararGravacao()
      : pararGravacaoNativa();
  return iniciarGravacaoComFallback();
}
async function iniciarGravacaoComFallback() {
  pararVozLocal();
  if (!sessaoAtual) await novaConversa();
  const r = await chamarAPI("iniciar_gravacao_nativa");
  if (r.ok) return iniciarGravacaoNativaPos(r.data?.backend || "native");
  if (window.isSecureContext && navigator.mediaDevices?.getUserMedia) {
    showToast("Usando microfone do navegador", r.erro, "info", 4500);
    return iniciarGravacao();
  }
  showToast("Microfone indisponível", r.erro, "error", 7000);
}
function iniciarGravacaoNativaPos(backend) {
  modoGravacaoVoz = "native";
  gravandoVoz = true;
  atualizarControlesVoz();
  trocarAba("chat");
  timerGravacaoVoz = setTimeout(() => {
    if (gravandoVoz) pararGravacaoNativa();
  }, 60000);
  const label = backend === "arecord" ? "sistema (ALSA)" : "sistema";
  document.getElementById("voice-status").textContent =
    `● Ouvindo pelo microfone do ${label}... clique novamente para enviar`;
}
async function iniciarGravacaoNativa() {
  const r = await chamarAPI("iniciar_gravacao_nativa");
  if (!r.ok) {
    showToast("Microfone indisponível", r.erro, "error", 7000);
    return;
  }
  iniciarGravacaoNativaPos(r.data?.backend || "native");
}
async function pararGravacaoNativa() {
  if (!gravandoVoz) return;
  gravandoVoz = false;
  atualizarControlesVoz();
  if (timerGravacaoVoz) clearTimeout(timerGravacaoVoz);
  timerGravacaoVoz = null;
  document.getElementById("voice-status").textContent =
    "Processando mensagem de voz...";
  adicionarTyping();
  const r = await chamarAPI("parar_gravacao_nativa", sessaoAtual);
  removerTyping();
  document.getElementById("voice-status").textContent = "";
  if (r.ok) {
    const textoUser = r.data.transcricao
      ? ` ${r.data.transcricao}`
      : " Mensagem de voz";
    adicionarMensagem("user", textoUser);
    adicionarMensagem("nova", r.data.resposta);
    falarResposta(r.data.resposta);
    await carregarSessoes();
    marcarSessaoAtiva(sessaoAtual);
  } else {
    showToast("Erro na conversa por voz", r.erro, "error", 7000);
    adicionarMensagem("nova", ` ${r.erro}`);
  }
}
async function iniciarGravacao() {
  if (!window.isSecureContext) {
    showToast(
      "Microfone bloqueado",
      "A interface não foi aberta em um contexto seguro. Reinicie a NOVA pelo main.py.",
      "error",
      6000,
    );
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    showToast(
      "Microfone indisponível",
      "É necessário um navegador moderno com suporte a microfone.",
      "error",
      6000,
    );
    return;
  }
  if (!sessaoAtual) await novaConversa();
  try {
    pararVozLocal();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    const AudioCtx = window.AudioContext || window.webkitAudioContext,
      contexto = new AudioCtx(),
      fonte = contexto.createMediaStreamSource(stream),
      processador = contexto.createScriptProcessor(4096, 1, 1),
      amostras = [];
    processador.onaudioprocess = (e) => {
      if (gravandoVoz)
        amostras.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };
    fonte.connect(processador);
    processador.connect(contexto.destination);
    gravadorVoz = {
      stream,
      contexto,
      fonte,
      processador,
      amostras,
      inicio: Date.now(),
      limite: setTimeout(() => {
        if (gravandoVoz) pararGravacao();
      }, 60000),
    };
    modoGravacaoVoz = "browser";
    gravandoVoz = true;
    atualizarControlesVoz();
    document.getElementById("voice-status").textContent =
      "● Ouvindo... clique novamente para enviar";
    trocarAba("chat");
  } catch (e) {
    showToast(
      "Não consegui usar o microfone",
      e.message || String(e),
      "error",
      5000,
    );
  }
}
async function pararGravacao() {
  if (!gravadorVoz) return;
  gravandoVoz = false;
  atualizarControlesVoz();
  clearTimeout(gravadorVoz.limite);
  gravadorVoz.processador.disconnect();
  gravadorVoz.fonte.disconnect();
  gravadorVoz.stream.getTracks().forEach((t) => t.stop());
  await gravadorVoz.contexto.close();
  const duracao = (Date.now() - gravadorVoz.inicio) / 1000,
    status = document.getElementById("voice-status");
  if (duracao < 0.5 || !gravadorVoz.amostras.length) {
    status.textContent = "Gravação muito curta";
    gravadorVoz = null;
    return;
  }
  const blob = criarWav(gravadorVoz.amostras, gravadorVoz.contexto.sampleRate);
  gravadorVoz = null;
  status.textContent = "Enviando mensagem de voz...";
  const leitor = new FileReader();
  leitor.onload = async () => enviarMensagemVoz(leitor.result, duracao);
  leitor.readAsDataURL(blob);
}
async function enviarMensagemVoz(audioData, duracao) {
  if (!sessaoAtual) await novaConversa();
  const msgs = document.getElementById("chat-msgs"),
    div = document.createElement("div");
  div.className = "msg user voice-message";
  div.innerHTML = `<div class="msg-content"><div class="bubble"><span class="voice-wave">▂▄▆█▆▄▂</span><span>Mensagem de voz · ${Math.round(duracao)}s</span></div><div class="msg-meta">${agoraHora()}</div></div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  adicionarTyping();
  const r = await chamarAPI(
    "enviar_audio",
    sessaoAtual,
    audioData,
    "audio/wav",
  );
  removerTyping();
  document.getElementById("voice-status").textContent = "";
  if (r.ok) {
    const textoUser = r.data.transcricao
      ? ` ${r.data.transcricao}`
      : `Mensagem de voz · ${Math.round(duracao)}s`;
    adicionarMensagem("nova", r.data.resposta);
    falarResposta(r.data.resposta);
    await carregarSessoes();
    marcarSessaoAtiva(sessaoAtual);
  } else {
    adicionarMensagem("nova", ` ${r.erro}`);
    showToast("Erro na conversa por voz", r.erro, "error", 5000);
  }
}

async function chamarAPI(fn, ...args) {
  try {
    const raw = await window.pywebview.api[fn](...args);
    return JSON.parse(raw);
  } catch (e) {
    console.error(`Erro ao chamar ${fn}:`, e);
    return { ok: false, erro: String(e) };
  }
}
function agoraHora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function escapeHTML(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function sanitizarHTML(html) {
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content
    .querySelectorAll("script,iframe,object,embed,style,link,meta")
    .forEach((el) => el.remove());
  template.content.querySelectorAll("*").forEach((el) =>
    [...el.attributes].forEach((attr) => {
      const nome = attr.name.toLowerCase(),
        valor = attr.value.trim().toLowerCase();
      if (
        nome.startsWith("on") ||
        ((nome === "href" || nome === "src") && valor.startsWith("javascript:"))
      )
        el.removeAttribute(attr.name);
    }),
  );
  return template.innerHTML;
}
function renderMarkdown(texto) {
  const seguro = escapeHTML(texto);
  if (typeof marked !== "undefined") {
    try {
      return sanitizarHTML(marked.parse(texto, { breaks: true, gfm: true }));
    } catch (e) {}
  }
  // Fallback offline: ao menos preserva blocos de código cercados por ```.
  return seguro
    .split(/(```[\s\S]*?```)/g)
    .map((parte) => {
      const bloco = parte.match(/^```([\w.+#-]*)\n?([\s\S]*?)```$/);
      if (bloco)
        return `<pre><code class="language-${bloco[1] || "text"}">${bloco[2].replace(/\n$/, "")}</code></pre>`;
      return parte.replace(/\n/g, "<br>");
    })
    .join("");
}
function decorarBlocosCodigo(raiz) {
  if (!raiz) return;
  raiz.querySelectorAll("pre").forEach((pre) => {
    if (pre.parentElement?.classList.contains("code-block")) return;
    const code = pre.querySelector("code");
    if (!code) return;
    const linguagem = (
      [...code.classList].find((c) => c.startsWith("language-")) ||
      "language-code"
    ).replace("language-", "");
    const wrap = document.createElement("div");
    wrap.className = "code-block";
    const header = document.createElement("div");
    header.className = "code-header";
    const nome = document.createElement("span");
    nome.textContent = linguagem || "code";
    const copiar = document.createElement("button");
    copiar.type = "button";
    copiar.textContent = "Copiar código";
    copiar.addEventListener("click", () =>
      navigator.clipboard.writeText(code.textContent).then(() => {
        copiar.textContent = "Copiado ✓";
        setTimeout(() => (copiar.textContent = "Copiar código"), 1600);
      }),
    );
    header.append(nome, copiar);
    pre.parentNode.insertBefore(wrap, pre);
    wrap.append(header, pre);
  });
}
function esconderSplash() {
  const s = document.getElementById("splash");
  if (s) setTimeout(() => s.classList.add("hidden"), 1200);
}
function showToast(titulo, msg = "", tipo = "info", duracao = 3500) {
  const c = document.getElementById("toast-container");
  const t = document.createElement("div");
  t.className = `toast ${tipo}`;
  const ic = { success: "✓", error: "✕", warning: "", info: "" };
  t.innerHTML = `<div class="toast-icon">${ic[tipo] || ""}</div><div class="toast-content"><div class="toast-title">${escapeHTML(titulo)}</div>${msg ? `<div class="toast-msg">${escapeHTML(msg)}</div>` : ""}</div>`;
  c.appendChild(t);
  setTimeout(() => {
    t.classList.add("fade-out");
    setTimeout(() => t.remove(), 300);
  }, duracao);
}
function criarParticulas() {
  const c = document.getElementById("chat-particles");
  if (!c) return;
  c.innerHTML = "";
  if (!settings.particles) return;
  const cores = ["", "magenta", "amber", "cyan"];
  for (let i = 0; i < 32; i++) {
    const p = document.createElement("div");
    p.className = "particle " + cores[Math.floor(Math.random() * cores.length)];
    if (Math.random() > 0.72) p.classList.add("big");
    p.style.left = Math.random() * 100 + "%";
    p.style.animationDuration = 14 + Math.random() * 12 + "s";
    p.style.animationDelay = -Math.random() * 24 + "s";
    c.appendChild(p);
  }
}
function aplicarTema(tema) {
  document.body.setAttribute("data-theme", tema);
  settings.theme = tema;
  const ht = document.getElementById("header-theme-toggle");
  if (ht) ht.classList.toggle("on", tema === "dark");
  document
    .querySelectorAll(".theme-option")
    .forEach((o) => o.classList.toggle("active", o.dataset.theme === tema));
}
async function toggleTheme() {
  const n = settings.theme === "light" ? "dark" : "light";
  aplicarTema(n);
  await chamarAPI("salvar_tema", n);
}
function setTheme(tema) {
  aplicarTema(tema);
  chamarAPI("salvar_tema", tema);
}
function toggleSidebar() {
  document.body.classList.toggle("sidebar-collapsed");
}
function atualizarLayoutResponsivo() {
  const largura = window.innerWidth,
    altura = window.innerHeight;
  document.body.classList.toggle("layout-wide", largura >= 1450);
  document.body.classList.toggle(
    "layout-compact",
    largura < 900 || altura < 650,
  );
  document.documentElement.style.setProperty(
    "--viewport-height",
    `${altura}px`,
  );
}
window.addEventListener("resize", atualizarLayoutResponsivo);

window.addEventListener("pywebviewready", async () => {
  esconderSplash();
  atualizarLayoutResponsivo();
  try {
    const r = await chamarAPI("carregar_tema");
    if (r.ok) aplicarTema(r.data.tema || "light");
    else aplicarTema("light");
  } catch (e) {
    aplicarTema("light");
  }
  criarParticulas();
  document
    .querySelectorAll(".nav-btn")
    .forEach((b) =>
      b.addEventListener("click", () => trocarAba(b.dataset.aba)),
    );
  document
    .getElementById("btn-nova-conversa")
    .addEventListener("click", async () => {
      await novaConversa();
      trocarAba("chat");
    });
  document.getElementById("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviarMensagem();
    }
  });
  document
    .getElementById("chat-send")
    .addEventListener("click", enviarMensagem);
  document
    .getElementById("cor-fundo")
    .addEventListener(
      "input",
      (e) =>
        (document.getElementById("cor-fundo-label").textContent =
          e.target.value),
    );
  const cm = document.getElementById("chat-msgs");
  cm.addEventListener("scroll", () => {
    const b = document.getElementById("scroll-bottom-btn");
    b.classList.toggle(
      "visible",
      cm.scrollHeight - cm.scrollTop - cm.clientHeight > 80,
    );
  });
  document.addEventListener("click", () =>
    document.getElementById("context-menu").classList.remove("visible"),
  );
  setupSidebarDrag();
  document.addEventListener("keydown", handleAtalhos);
  cidadeDashboard = storageGet("novaCidade", "Rio de Janeiro");
  if (cidadeDashboard === "São Paulo") {
    cidadeDashboard = "Rio de Janeiro";
    storageSet("novaCidade", cidadeDashboard);
  }
  vozNovaAtiva = storageGet("novaVozAtiva", "1") !== "0";
  atualizarControlesVoz();
  document.getElementById("input-cidade").value = cidadeDashboard;
  try {
    await carregarDashboard();
  } catch (e) {
    console.error(e);
    mostrarErroDashboard(String(e));
  }
  iniciarMonitorSistema();
  try {
    await carregarSessoes();
  } catch (e) {
    console.error(e);
  }
  // A tela inicial fica livre; os resumos estão disponíveis no sistema orbital.
  try {
    await atualizarStatsFoco();
  } catch (e) {
    console.error(e);
  }
  try {
    await atualizarBadges();
  } catch (e) {
    console.error(e);
  }
  try {
    await atualizarKeyDot();
  } catch (e) {
    console.error(e);
  }
});

function handleAtalhos(e) {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === "k" || e.key === "K") {
      e.preventDefault();
      novaConversa();
      trocarAba("chat");
      showToast("Nova conversa", "", "info", 1500);
    } else if (e.key === "/") {
      e.preventDefault();
      const h = document.getElementById("shortcut-hint");
      h.classList.add("visible");
      setTimeout(() => h.classList.remove("visible"), 2500);
    } else if (e.key === "b" || e.key === "B") {
      e.preventDefault();
      toggleSidebar();
    }
  }
  if (e.key === "Escape") {
    document
      .querySelectorAll(".modal")
      .forEach((m) => (m.style.display = "none"));
    document.getElementById("context-menu").classList.remove("visible");
  }
}
function setupSidebarDrag() {
  const r = document.getElementById("sidebar-resizer");
  if (!r) return;
  let d = false;
  r.addEventListener("mousedown", (e) => {
    d = true;
    r.classList.add("dragging");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (!d) return;
    document.documentElement.style.setProperty(
      "--sidebar-width",
      Math.max(180, Math.min(400, e.clientX)) + "px",
    );
  });
  document.addEventListener("mouseup", () => {
    if (d) {
      d = false;
      r.classList.remove("dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
  });
}
async function atualizarBadges() {
  try {
    const r = await chamarAPI("get_tarefas");
    if (r.ok) {
      const p = r.data.filter((t) => t.status === "pendente").length;
      const b = document.getElementById("badge-tarefas");
      if (p > 0) {
        b.textContent = p > 9 ? "9+" : p;
        b.style.display = "inline-block";
      } else b.style.display = "none";
      const s = document.getElementById("subtitle-tarefas");
      if (s)
        s.textContent = `${p} pendente(s) · ${r.data.length - p} concluída(s)`;
    }
  } catch (e) {}
  try {
    const r = await chamarAPI("get_lembretes");
    if (r.ok) {
      const t = r.data.length;
      const b = document.getElementById("badge-lembretes");
      if (t > 0) {
        b.textContent = t > 9 ? "9+" : t;
        b.style.display = "inline-block";
      } else b.style.display = "none";
      const s = document.getElementById("subtitle-lembretes");
      if (s) s.textContent = `${t} lembrete(s) ativo(s)`;
    }
  } catch (e) {}
  try {
    const r = await chamarAPI("get_habitos");
    if (r.ok) {
      const f = r.data.filter((h) => h.feito_hoje).length;
      const s = document.getElementById("subtitle-habitos");
      if (s) s.textContent = `${f}/${r.data.length} feitos hoje`;
    }
  } catch (e) {}
}
async function atualizarKeyDot() {
  try {
    const r = await chamarAPI("get_api_key");
    const ok = r.ok && r.data.tem_key;
    const d1 = document.getElementById("key-dot");
    const d2 = document.getElementById("key-dot-modal");
    const st = document.getElementById("key-status");
    if (d1) d1.classList.toggle("configured", ok);
    if (d2) d2.classList.toggle("configured", ok);
    if (st) st.textContent = ok ? "✓ Configurada" : " Não configurada";
  } catch (e) {}
}
function trocarAba(aba) {
  document
    .querySelectorAll(".aba")
    .forEach((a) => a.classList.remove("active"));
  document
    .querySelectorAll(".nav-btn")
    .forEach((b) => b.classList.remove("active"));
  document.getElementById(`aba-${aba}`).classList.add("active");
  const nav = document.querySelector(`[data-aba="${aba}"]`);
  if (nav) nav.classList.add("active");
  if (aba === "dashboard") carregarDashboard();
  if (aba === "tarefas") carregarTarefas();
  if (aba === "lembretes") carregarLembretes();
  if (aba === "habitos") carregarHabitos();
  if (aba === "foco") atualizarStatsFoco();
}

function formatarUptime(segundos) {
  if (segundos == null) return "indisponível";
  const d = Math.floor(segundos / 86400),
    h = Math.floor((segundos % 86400) / 3600),
    m = Math.floor((segundos % 3600) / 60);
  return `${d ? d + "d " : ""}${h}h ${m}m`;
}
function iconeClima(codigo) {
  const cloud = '<path d="M7 17a4 4 0 1 1 .6-7.95A6 6 0 0 1 19 11a3 3 0 0 1 0 6Z"/>';
  let drawing = cloud;
  if (codigo === 0) drawing = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>';
  else if (codigo >= 95) drawing += '<path d="m13 16-3 4h4l-2 3"/>';
  else if ((codigo >= 71 && codigo <= 77) || codigo === 85 || codigo === 86) drawing += '<path d="M8 20v2m-1-1h2m7-1v2m-1-1h2"/>';
  else if (codigo === 45 || codigo === 48) drawing += '<path d="M4 20h16M7 23h10"/>';
  else if (codigo > 3) drawing += '<path d="m8 20-1 2m6-2-1 2m6-2-1 2"/>';
  return `<svg viewBox="0 0 24 26" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${drawing}</svg>`;
}
function moeda(valor) {
  return valor == null
    ? "Não informado"
    : Number(valor).toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
      });
}
function mostrarErroDashboard(erro) {
  const mensagem = escapeHTML(erro || "Falha desconhecida");
  const clima = document.getElementById("dash-clima"),
    financas = document.getElementById("dash-financas");
  if (clima)
    clima.innerHTML = `<div class="dash-error">Não foi possível carregar os dados.<br><small>${mensagem}</small></div>`;
  if (financas)
    financas.innerHTML = `<div class="dash-error">Não foi possível carregar os dados.<br><small>${mensagem}</small></div>`;
}
async function carregarDashboard(forcar = false) {
  if (!forcar && carregarDashboard.carregando) return;
  carregarDashboard.carregando = true;
  carregarColecoesDashboard();
  const agora = new Date();
  const hora = agora.getHours();
  const saudacao =
    hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
  document.getElementById("dashboard-saudacao").textContent =
    `${saudacao}, chefe.`;
  document.getElementById("dashboard-data").textContent =
    agora.toLocaleDateString("pt-BR", {
      weekday: "long",
      day: "2-digit",
      month: "long",
    });
  if (forcar) {
    document.getElementById("dash-clima").textContent = "Atualizando...";
    document.getElementById("dash-financas").textContent = "Atualizando...";
  }
  const cidade = cidadeDashboard || "Rio de Janeiro";
  const r = await chamarAPI("get_dashboard", cidade);
  carregarDashboard.carregando = false;
  if (!r.ok) {
    mostrarErroDashboard(r.erro);
    showToast("Dashboard indisponível", r.erro, "error");
    return;
  }
  const d = r.data,
    c = d.clima,
    f = d.financas,
    s = d.computador;
  document.getElementById("dash-clima").innerHTML = c
    ? `<div class="weather-main"><span class="weather-icon">${iconeClima(c.codigo)}</span><strong>${c.temperatura}°</strong><div><b>${escapeHTML(c.cidade)}</b><small>${escapeHTML(c.descricao)}</small></div></div><div class="weather-stats"><span>Sensação <b>${c.sensacao}°</b></span><span>Máx / mín <b>${c.maxima}° / ${c.minima}°</b></span><span>Umidade <b>${c.umidade}%</b></span><span>Chuva <b>${c.chuva}%</b></span></div>`
    : `<div class="dash-error">Clima indisponível<br><small>${escapeHTML(d.erros.clima || "Tente atualizar")}</small></div>`;
  const variacao = f?.bitcoin_variacao;
  const classe = variacao == null ? "" : variacao >= 0 ? "up" : "down";
  document.getElementById("dash-financas").innerHTML = f
    ? `<div class="quote-row"><span><i>US</i> Dólar</span><b>${moeda(f.dolar)}</b></div><div class="quote-row"><span><i>EU</i> Euro</span><b>${moeda(f.euro)}</b></div><div class="quote-row"><span><i>₿</i> Bitcoin</span><div><b>${moeda(f.bitcoin)}</b>${variacao != null ? `<small class="${classe}">${variacao >= 0 ? "+" : ""}${variacao.toFixed(2)}%</small>` : ""}</div></div>`
    : `<div class="dash-error">Cotações indisponíveis</div>`;
  renderizarSystemFetch(s);
  document.getElementById("dashboard-atualizado").textContent =
    `Atualizado às ${new Date(d.atualizado_em).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
  const tarefas = carregarColecoesDashboard.totalPendentes || 0;
  document.querySelector("#dashboard-insight p").innerHTML =
    `Você tem <b>${tarefas} tarefa${tarefas === 1 ? "" : "s"} pendente${tarefas === 1 ? "" : "s"}</b> hoje.${c ? ` Clima ${escapeHTML(c.descricao.toLowerCase())} em ${escapeHTML(c.cidade)}, ${c.temperatura}°C.` : ""} Boa sessão!`;
}
function renderizarSystemFetch(s) {
  if (!s) return;
  const painel = document.getElementById("dash-sistema");
  if (!painel) return;
  const cpuPct = Math.max(0, Math.min(100, Number(s.cpu_percentual) || 0));
  const ramPct = Math.max(0, Math.min(100, Number(s.ram_percentual) || 0));
  const discoPct = Math.max(0, Math.min(100, Number(s.disco_percentual) || 0));
  const horario = new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  painel.innerHTML = `<div class="system-identity"><div class="system-logo">N</div><div><b>${escapeHTML(s.usuario)}<em>@${escapeHTML(s.hostname)}</em></b><span>${escapeHTML(s.sistema)} · ${escapeHTML(s.arquitetura || "")}</span></div><i class="system-online" title="Última leitura: ${horario}">● AO VIVO · ${horario}</i></div><div class="system-meters"><div class="system-meter"><div><span>CPU</span><b>${cpuPct}%</b></div><i style="--usage:${cpuPct}%"></i><small>${s.nucleos} núcleos · ${escapeHTML(s.processador)}</small></div><div class="system-meter"><div><span>MEMÓRIA</span><b>${ramPct}%</b></div><i style="--usage:${ramPct}%"></i><small>${s.ram_usada ? `${escapeHTML(s.ram_usada)} de ${escapeHTML(s.ram_total)}` : "Monitoramento indisponível"}</small></div><div class="system-meter"><div><span>ARMAZENAMENTO</span><b>${discoPct}%</b></div><i style="--usage:${discoPct}%"></i><small>${escapeHTML(s.disco_usado)} de ${escapeHTML(s.disco_total)}</small></div></div><div class="system-meta"><span><small>UPTIME</small><b>${formatarUptime(s.uptime_segundos)}</b></span><span><small>ARQUITETURA</small><b>${escapeHTML(s.arquitetura || "Não informado")}</b></span><span><small>PYTHON</small><b>${escapeHTML(s.python || "Não informado")}</b></span></div>`;
}
async function atualizarSystemFetch() {
  if (atualizarSystemFetch.executando) return;
  atualizarSystemFetch.executando = true;
  try {
    const resposta = await chamarAPI("get_info_computador");
    if (resposta.ok) renderizarSystemFetch(resposta.data);
  } catch (erro) {
    console.warn("System Fetch:", erro);
  } finally {
    atualizarSystemFetch.executando = false;
  }
}
function iniciarMonitorSistema() {
  if (iniciarMonitorSistema.timer) clearInterval(iniciarMonitorSistema.timer);
  iniciarMonitorSistema.timer = setInterval(atualizarSystemFetch, 5000);
}
async function carregarColecoesDashboard() {
  const [tarefasResp, habitosResp] = await Promise.all([
    chamarAPI("get_tarefas"),
    chamarAPI("get_habitos"),
  ]);
  if (tarefasResp.ok) {
    const tarefas = tarefasResp.data || [],
      pendentes = tarefas.filter((t) => t.status === "pendente"),
      concluidas = tarefas.filter((t) => t.status === "concluida");
    carregarColecoesDashboard.totalPendentes = pendentes.length;
    const total = tarefas.length,
      feitos = concluidas.length,
      progresso = total ? Math.round((feitos / total) * 100) : 0;
    const barra = document.getElementById("dash-task-progress");
    barra.querySelector("i").style.setProperty("--progress", `${progresso}%`);
    barra.querySelector("span").textContent = `${feitos}/${total}`;
    const lista = document.getElementById("dash-tarefas");
    const itens = [...pendentes, ...concluidas].slice(0, 4);
    lista.innerHTML = itens.length
      ? itens
          .map((t) => {
            const done = t.status === "concluida",
              cor =
                { alta: "#ff5263", media: "#ffad1f", baixa: "#778096" }[
                  t.prioridade
                ] || "#778096";
            return `<div class="dashboard-row ${done ? "done" : ""}" onclick="trocarAba('tarefas')"><span class="dashboard-check">✓</span><span class="dashboard-row-name">${escapeHTML(t.titulo)}</span><i class="priority-dot" style="background:${cor}"></i></div>`;
          })
          .join("")
      : `<div class="dash-error">Nenhuma tarefa. Estranhamente organizado, chefe.</div>`;
  } else
    document.getElementById("dash-tarefas").innerHTML =
      `<div class="dash-error">Tarefas indisponíveis</div>`;
  if (habitosResp.ok) {
    const habitos = (habitosResp.data || []).slice(0, 4),
      lista = document.getElementById("dash-habitos");
    lista.innerHTML = habitos.length
      ? habitos
          .map(
            (h) =>
              `<div class="dashboard-row" onclick="trocarAba('habitos')"><span class="dashboard-habit-icon"></span><div class="habit-data"><div>${escapeHTML(h.nome)} <small>↻ ${h.streak}d</small></div><span class="habit-dots">${Array.from({ length: 7 }, (_, i) => `<i class="${i < Math.min(h.streak, 7) ? "on" : ""}"></i>`).join("")}</span></div><span class="dashboard-check ${h.feito_hoje ? "done" : ""}">${h.feito_hoje ? "✓" : ""}</span></div>`,
          )
          .join("")
      : `<div class="dash-error">Nenhum hábito cadastrado.</div>`;
  } else
    document.getElementById("dash-habitos").innerHTML =
      `<div class="dash-error">Hábitos indisponíveis</div>`;
}
async function abrirUltimaConversa() {
  const r = await chamarAPI("get_sessoes");
  if (!r.ok || !r.data || !r.data.length) {
    await novaConversa();
    return;
  }
  const u = r.data[0];
  sessaoAtual = u.id;
  await carregarSessoes();
  marcarSessaoAtiva(sessaoAtual);
  const h = await chamarAPI("get_historico", u.id);
  if (h.ok) {
    const m = document.getElementById("chat-msgs");
    m.innerHTML = "";
    h.data.forEach((d) =>
      adicionarMensagem(d.role === "user" ? "user" : "nova", d.content),
    );
  }
}
async function novaConversa() {
  const r = await chamarAPI("nova_sessao");
  if (!r.ok) return;
  sessaoAtual = r.data.sessao_id;
  document.getElementById("chat-msgs").innerHTML = "";
  await carregarSessoes();
  marcarSessaoAtiva(sessaoAtual);
}
async function carregarSessoes() {
  const r = await chamarAPI("get_sessoes");
  if (!r.ok) return;
  const l = document.getElementById("lista-sessoes");
  l.innerHTML = "";
  r.data.forEach((s) => {
    const f = document.createElement("div");
    f.className = "sessao-item" + (s.id === sessaoAtual ? " ativa" : "");
    f.dataset.id = s.id;
    f.innerHTML = `<span class="sessao-titulo">${escapeHTML(s.titulo)}</span><button class="sessao-del" onclick="deletarSessao(${s.id}, event)">✕</button>`;
    f.addEventListener("click", () => abrirSessao(s.id));
    l.appendChild(f);
  });
}
function marcarSessaoAtiva(id) {
  document
    .querySelectorAll(".sessao-item")
    .forEach((e) => e.classList.toggle("ativa", parseInt(e.dataset.id) === id));
}
async function abrirSessao(id) {
  sessaoAtual = id;
  marcarSessaoAtiva(id);
  trocarAba("chat");
  const r = await chamarAPI("get_historico", id);
  if (!r.ok) return;
  const m = document.getElementById("chat-msgs");
  m.innerHTML = "";
  r.data.forEach((d) =>
    adicionarMensagem(d.role === "user" ? "user" : "nova", d.content),
  );
}
async function deletarSessao(id, e) {
  e.stopPropagation();
  await chamarAPI("deletar_sessao", id);
  if (sessaoAtual === id) {
    const r = await chamarAPI("get_sessoes");
    if (r.ok && r.data.length > 0) await abrirSessao(r.data[0].id);
    else await novaConversa();
  } else await carregarSessoes();
}
async function carregarResumoMatinal() {
  const r = await chamarAPI("get_resumo_matinal");
  if (!r.ok) return;
  adicionarMensagem("nova", r.data.resumo, "resumo");
}
function adicionarMensagem(tipo, texto, extraClass = "") {
  const msgs = document.getElementById("chat-msgs");
  const div = document.createElement("div");
  div.className = `msg ${tipo}${extraClass ? " " + extraClass : ""}`;
  const hora = agoraHora();
  if (tipo === "nova") {
    const isResumo = extraClass === "resumo";
    div.innerHTML = `<div class="msg-avatar">N</div><div class="msg-content"><div class="bubble ${isResumo ? "" : "markdown"}">${isResumo ? escapeHTML(texto).replace(/\n/g, "<br>") : renderMarkdown(texto)}</div><div class="msg-meta">${hora}</div>${!isResumo ? `<div class="msg-actions"><button class="msg-action-btn" onclick="copiarMensagem(this)" title="Copiar"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copiar</button><button class="msg-action-btn" onclick="regenerarMensagem(this)" title="Regenerar"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Regenerar</button></div>` : ""}</div>`;
    if (!extraClass) {
      div.classList.add("nova-flash");
      ultimaMsgNova = div;
    }
    decorarBlocosCodigo(div.querySelector(".bubble"));
    div.querySelector(".bubble").addEventListener("contextmenu", (e) => {
      e.preventDefault();
      contextMsgEl = div;
      mostrarContextMenu(e.clientX, e.clientY);
    });
  } else if (tipo === "user") {
    div.innerHTML = `<div class="msg-content"><div class="bubble">${escapeHTML(texto).replace(/\n/g, "<br>")}</div><div class="msg-meta">${hora}</div></div>`;
  } else {
    div.innerHTML = `<div class="bubble">${escapeHTML(texto).replace(/\n/g, "<br>")}</div>`;
    div.classList.add("muted");
  }
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}
function adicionarMensagemImagem(texto, base64Img) {
  const m = document.getElementById("chat-msgs");
  const d = document.createElement("div");
  d.className = "msg nova nova-flash";
  d.innerHTML = `<div class="msg-avatar">N</div><div class="msg-content"><div class="bubble" style="padding:8px"><img src="${base64Img}" style="max-width:260px;max-height:260px;border-radius:8px;display:block;margin-bottom:6px"/><span>${escapeHTML(texto)}</span></div><div class="msg-meta">${agoraHora()}</div></div>`;
  m.appendChild(d);
  m.scrollTop = m.scrollHeight;
}
function copiarMensagem(btn) {
  const b = btn.closest(".msg-content").querySelector(".bubble");
  navigator.clipboard
    .writeText(b.innerText)
    .then(() => showToast("Copiado!", "", "success", 1800))
    .catch(() => showToast("Erro", "", "error", 2000));
}
function regenerarMensagem(btn) {
  const m = btn.closest(".msg");
  let p = m.previousElementSibling;
  while (p && !p.classList.contains("user")) p = p.previousElementSibling;
  if (!p) return;
  const t = p.querySelector(".bubble").innerText;
  m.remove();
  reenviarSemMostrar(t);
}
async function reenviarSemMostrar(texto) {
  const btn = document.getElementById("chat-send");
  btn.disabled = true;
  adicionarTyping();
  let sd = null;
  window.__novaPrimeiroChunk = function () {
    removerTyping();
    if (sd) return;
    const m = document.getElementById("chat-msgs");
    sd = document.createElement("div");
    sd.className = "msg nova nova-flash";
    sd.innerHTML = `<div class="msg-avatar">N</div><div class="msg-content"><div class="bubble markdown" id="streaming-bubble"><span class="streaming-cursor">▍</span></div><div class="msg-meta">${agoraHora()}</div><div class="msg-actions"><button class="msg-action-btn" onclick="copiarMensagem(this)"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copiar</button><button class="msg-action-btn" onclick="regenerarMensagem(this)"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Regenerar</button></div></div>`;
    m.appendChild(sd);
    m.scrollTop = m.scrollHeight;
  };
  await chamarAPI("enviar_mensagem_stream", sessaoAtual, texto);
  btn.disabled = false;
  removerTyping();
  const b = document.getElementById("streaming-bubble");
  if (b) {
    b.removeAttribute("id");
    const c = b.querySelector(".streaming-cursor");
    if (c) c.remove();
  }
  await carregarSessoes();
  marcarSessaoAtiva(sessaoAtual);
}
function mostrarContextMenu(x, y) {
  const m = document.getElementById("context-menu");
  m.style.left = x + "px";
  m.style.top = y + "px";
  m.classList.add("visible");
}
function ctxCopy() {
  if (!contextMsgEl) return;
  const b = contextMsgEl.querySelector(".bubble");
  if (b) {
    navigator.clipboard.writeText(b.innerText);
    showToast("Copiado!", "", "success", 1500);
  }
  document.getElementById("context-menu").classList.remove("visible");
}
function ctxRegenerate() {
  if (!contextMsgEl) return;
  const b = contextMsgEl.querySelector(".msg-action-btn[title='Regenerar']");
  if (b) regenerarMensagem(b);
  document.getElementById("context-menu").classList.remove("visible");
}
function ctxDelete() {
  if (!contextMsgEl) return;
  contextMsgEl.remove();
  showToast("Removida", "", "info", 1500);
  document.getElementById("context-menu").classList.remove("visible");
}
let imagemChatB64 = null;
function previewImagem(e) {
  const f = e.target.files[0];
  if (!f) return;
  const r = new FileReader();
  r.onload = (ev) => {
    imagemChatB64 = ev.target.result;
    document.getElementById("chat-preview-img").src = imagemChatB64;
    document.getElementById("chat-preview-wrap").style.display = "flex";
  };
  r.readAsDataURL(f);
}
function removerImagem() {
  imagemChatB64 = null;
  document.getElementById("chat-preview-wrap").style.display = "none";
  document.getElementById("chat-preview-img").src = "";
  document.getElementById("chat-imagem").value = "";
}
function scrollChatBottom() {
  const m = document.getElementById("chat-msgs");
  m.scrollTop = m.scrollHeight;
  document.getElementById("scroll-bottom-btn").classList.remove("visible");
}
function adicionarTyping() {
  const m = document.getElementById("chat-msgs");
  const d = document.createElement("div");
  d.className = "msg nova";
  d.id = "typing-msg";
  d.innerHTML = `<div class="msg-avatar">N</div><div class="bubble" style="padding:0"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
  m.appendChild(d);
  m.scrollTop = m.scrollHeight;
}
function removerTyping() {
  const t = document.getElementById("typing-msg");
  if (t) t.remove();
}
function showProgressBar() {
  document.getElementById("chat-progress-bar").classList.add("active");
}
function hideProgressBar() {
  document.getElementById("chat-progress-bar").classList.remove("active");
}
async function enviarMensagem() {
  if (document.getElementById("chat-send").disabled) return;
  const input = document.getElementById("chat-input");
  const texto = input.value.trim();
  const img = imagemChatB64;
  if (!texto && !img) return;
  if (!sessaoAtual) await novaConversa();
  if (!sessaoAtual) return;
  input.value = "";
  input.style.height = "auto";
  if (img) {
    const m = document.getElementById("chat-msgs");
    const d = document.createElement("div");
    d.className = "msg user";
    d.innerHTML = `<div class="msg-content"><div class="bubble" style="padding:6px"><img src="${img}" style="max-width:200px;max-height:200px;border-radius:8px;display:block"/>${texto ? `<span style="display:block;margin-top:6px">${escapeHTML(texto)}</span>` : ""}</div><div class="msg-meta">${agoraHora()}</div></div>`;
    m.appendChild(d);
    m.scrollTop = m.scrollHeight;
  } else adicionarMensagem("user", texto);
  removerImagem();
  const btn = document.getElementById("chat-send");
  btn.disabled = true;
  showProgressBar();
  if (img) {
    adicionarTyping();
    const r = await chamarAPI("enviar_mensagem", sessaoAtual, texto, img);
    removerTyping();
    btn.disabled = false;
    hideProgressBar();
    if (r.ok) {
      adicionarMensagem("nova", r.data.resposta);
      await carregarSessoes();
      marcarSessaoAtiva(sessaoAtual);
    } else {
      adicionarMensagem("nova", ` ${r.erro}`);
      showToast("Erro", r.erro, "error");
    }
    return;
  }
  adicionarTyping();
  let sd = null;
  window.__novaPrimeiroChunk = function () {
    removerTyping();
    hideProgressBar();
    if (sd) return;
    const m = document.getElementById("chat-msgs");
    sd = document.createElement("div");
    sd.className = "msg nova nova-flash";
    sd.innerHTML = `<div class="msg-avatar">N</div><div class="msg-content"><div class="bubble markdown" id="streaming-bubble"><span class="streaming-cursor">▍</span></div><div class="msg-meta">${agoraHora()}</div><div class="msg-actions"><button class="msg-action-btn" onclick="copiarMensagem(this)" title="Copiar"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copiar</button><button class="msg-action-btn" onclick="regenerarMensagem(this)" title="Regenerar"><svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg> Regenerar</button></div></div>`;
    m.appendChild(sd);
    m.scrollTop = m.scrollHeight;
    ultimaMsgNova = sd;
  };
  const res = await chamarAPI("enviar_mensagem_stream", sessaoAtual, texto);
  btn.disabled = false;
  removerTyping();
  hideProgressBar();
  const b = document.getElementById("streaming-bubble");
  if (b) {
    b.removeAttribute("id");
    const c = b.querySelector(".streaming-cursor");
    if (c) c.remove();
  } else if (!res.ok) {
    adicionarMensagem("nova", ` ${res.erro}`);
    showToast("Erro", res.erro, "error");
  }
  await carregarSessoes();
  marcarSessaoAtiva(sessaoAtual);
}
window.__novaChunk = function (texto) {
  if (!document.getElementById("streaming-bubble"))
    window.__novaPrimeiroChunk();
  const b = document.getElementById("streaming-bubble");
  if (!b) return;
  const c = b.querySelector(".streaming-cursor");
  if (c) c.remove();
  b.appendChild(document.createTextNode(texto));
  if (c) b.appendChild(c);
  const m = document.getElementById("chat-msgs");
  if (m.scrollHeight - m.scrollTop - m.clientHeight < 100)
    m.scrollTop = m.scrollHeight;
};
window.__novaFim = function () {
  const b = document.getElementById("streaming-bubble");
  if (!b) return;
  const c = b.querySelector(".streaming-cursor");
  if (c) c.remove();
  const texto = b.textContent;
  b.innerHTML = renderMarkdown(texto);
  decorarBlocosCodigo(b);
  b.removeAttribute("id");
};
window.__novaErro = function (msg) {
  if (!document.getElementById("streaming-bubble"))
    window.__novaPrimeiroChunk();
  const b = document.getElementById("streaming-bubble");
  if (!b) return;
  // O retorno da API finaliza esta bolha; manter o ID evita duplicar o erro.
  b.textContent = ` ${msg}`;
  showToast("Erro", msg, "error");
};
window.__novaAgenteAcao = function (tipo, desc) {
  const ic = { tarefa: "", lembrete: "", listar: "" };
  showToast(`${ic[tipo] || ""} Ação executada`, desc, "success", 3000);
  atualizarBadges();
};
function abrirModalConfig() {
  document.getElementById("modal-config").style.display = "flex";
  document.getElementById("input-key").value = "";
  resetIntegration();
  loadIntegrations();
  loadLocalChat();
  atualizarKeyDot();
}
function toggleSetting(key, el) {
  el.classList.toggle("on");
  settings[key] = el.classList.contains("on");
  if (key === "particles") criarParticulas();
}
async function salvarConfig() {
  try {
    const localResult = await chamarAPI(
      "configurar_chat_local",
      document.getElementById("local-chat-enabled").checked,
      document.getElementById("local-chat-model").value.trim(),
    );
    if (!localResult.ok) throw new Error(localResult.erro);
    const key = document.getElementById("input-key").value.trim();
    if (key) {
      const response = await chamarAPI("salvar_api_key", key);
      if (!response.ok) throw new Error(response.erro);
      document.getElementById("input-key").value = "";
    }
    cidadeDashboard =
      document.getElementById("input-cidade").value.trim() || "Rio de Janeiro";
    storageSet("novaCidade", cidadeDashboard);
    fecharModal("modal-config");
    await atualizarKeyDot();
    carregarDashboard(true);
    showToast("Configurações salvas", "", "success", 2000);
  } catch (error) {
    showToast("Erro ao salvar", error.message, "error");
  }
}
function mostrarSkeleton(lista, n = 3) {
  lista.innerHTML = "";
  for (let i = 0; i < n; i++) {
    const s = document.createElement("div");
    s.className = "skeleton-card";
    s.innerHTML = `<div style="flex:1"><div class="skeleton-line medium"></div><div class="skeleton-line short"></div></div>`;
    lista.appendChild(s);
  }
}
async function carregarTarefas() {
  const l = document.getElementById("lista-tarefas");
  mostrarSkeleton(l);
  const r = await chamarAPI("get_tarefas");
  if (!r.ok) {
    l.innerHTML = "";
    return;
  }
  l.innerHTML = "";
  const p = r.data.filter((t) => t.status === "pendente");
  const c = r.data.filter((t) => t.status === "concluida");
  if (!r.data.length) {
    l.innerHTML = `<div class="empty-msg"><div class="empty-icon"></div><div class="empty-title">Sem tarefas</div><div class="empty-desc">Nenhuma tarefa ainda.</div></div>`;
    return;
  }
  if (p.length) {
    l.innerHTML += `<div class="secao-label">PENDENTES</div>`;
    p.forEach((t, i) => {
      const cd = cardTarefa(t);
      if (i === 0) cd.classList.add("slide-in");
      l.appendChild(cd);
    });
  }
  if (c.length) {
    l.innerHTML += `<div class="secao-label">CONCLUÍDAS</div>`;
    c.slice(0, 5).forEach((t) => l.appendChild(cardTarefa(t, true)));
  }
}
function cardTarefa(t, c = false) {
  const co = { alta: "#dc2626", media: "#d97706", baixa: "#059669" };
  const cor = co[t.prioridade] || "#a1a29e";
  const d = document.createElement("div");
  d.className = "card";
  d.innerHTML = `<div class="prio-bar" style="background:${cor}"></div><div class="card-left"><div class="card-titulo ${c ? "concluida" : ""}">${escapeHTML(t.titulo)}</div><div class="card-meta">${t.projeto ? `<span>[${t.projeto}]</span>` : ""}${t.prazo ? `<span> ${t.prazo.slice(0, 10)}</span>` : ""}<span>${t.prioridade}</span></div></div><div class="card-btns">${!c ? `<button class="btn-icon" onclick="concluirTarefa(${t.id})">✓</button>` : ""}<button class="btn-icon" onclick="deletarTarefa(${t.id})">✕</button></div>`;
  return d;
}
function abrirModalTarefa() {
  document.getElementById("modal-tarefa").style.display = "flex";
  document.getElementById("tarefa-titulo").focus();
}
async function criarTarefa() {
  const t = document.getElementById("tarefa-titulo").value.trim();
  const d = document.getElementById("tarefa-desc").value.trim();
  const p = document.getElementById("tarefa-prazo").value || null;
  const pr =
    document.querySelector('input[name="prio"]:checked')?.value || "media";
  if (!t) return;
  await chamarAPI("criar_tarefa", t, d, null, pr, p);
  fecharModal("modal-tarefa");
  document.getElementById("tarefa-titulo").value = "";
  document.getElementById("tarefa-desc").value = "";
  document.getElementById("tarefa-prazo").value = "";
  await carregarTarefas();
  await atualizarBadges();
  showToast("Tarefa criada!", t, "success", 2500);
}
async function concluirTarefa(id) {
  await chamarAPI("concluir_tarefa", id);
  await carregarTarefas();
  await atualizarBadges();
  showToast("Concluída!", "", "success", 2200);
}
async function deletarTarefa(id) {
  await chamarAPI("deletar_tarefa", id);
  await carregarTarefas();
  await atualizarBadges();
}
async function carregarLembretes() {
  const l = document.getElementById("lista-lembretes");
  mostrarSkeleton(l);
  const r = await chamarAPI("get_lembretes");
  if (!r.ok) {
    l.innerHTML = "";
    return;
  }
  l.innerHTML = "";
  if (!r.data.length) {
    l.innerHTML = `<div class="empty-msg"><div class="empty-icon"></div><div class="empty-title">Sem lembretes</div><div class="empty-desc">Nenhum ativo.</div></div>`;
    return;
  }
  r.data.forEach((lb) => {
    const d = document.createElement("div");
    d.className = "card";
    const dt = lb.data_hora.slice(0, 16).replace("T", " ");
    const rp = lb.repetir !== "nunca" ? ` • repete ${lb.repetir}` : "";
    d.innerHTML = `<div class="card-left"><div class="card-titulo"> ${escapeHTML(lb.titulo)}</div><div class="card-meta"><span>${dt}${rp}</span></div></div><div class="card-btns"><button class="btn-icon" onclick="deletarLembrete(${lb.id})">✕</button></div>`;
    l.appendChild(d);
  });
}
function abrirModalLembrete() {
  const a = new Date();
  a.setMinutes(a.getMinutes() - a.getTimezoneOffset());
  document.getElementById("lembrete-data").value = a.toISOString().slice(0, 16);
  document.getElementById("modal-lembrete").style.display = "flex";
  document.getElementById("lembrete-titulo").focus();
}
async function criarLembrete() {
  const t = document.getElementById("lembrete-titulo").value.trim();
  const d = document.getElementById("lembrete-data").value;
  const r =
    document.querySelector('input[name="rep"]:checked')?.value || "nunca";
  if (!t || !d) return;
  await chamarAPI("criar_lembrete", t, d, "", r);
  fecharModal("modal-lembrete");
  document.getElementById("lembrete-titulo").value = "";
  await carregarLembretes();
  await atualizarBadges();
  showToast("Lembrete criado!", t, "success", 2500);
}
async function deletarLembrete(id) {
  await chamarAPI("deletar_lembrete", id);
  await carregarLembretes();
  await atualizarBadges();
}
async function carregarHabitos() {
  const l = document.getElementById("lista-habitos");
  mostrarSkeleton(l);
  const r = await chamarAPI("get_habitos");
  if (!r.ok) {
    l.innerHTML = "";
    return;
  }
  l.innerHTML = "";
  if (!r.data.length) {
    l.innerHTML = `<div class="empty-msg"><div class="empty-icon"></div><div class="empty-title">Sem hábitos</div><div class="empty-desc">Crie um!</div></div>`;
    return;
  }
  const h = new Date().toLocaleDateString("pt-BR");
  l.innerHTML = `<div class="secao-label">HOJE , ${h}</div>`;
  r.data.forEach((hb) => {
    const d = document.createElement("div");
    d.className = "card";
    d.style.flexDirection = "column";
    d.style.alignItems = "stretch";
    d.innerHTML = `<div style="display:flex;align-items:center;gap:12px;width:100%"><button class="habito-check ${hb.feito_hoje ? "feito" : ""}" onclick="toggleHabito(${hb.id})">${hb.feito_hoje ? "✓" : "○"}</button><div class="card-left"><div class="card-titulo"> ${escapeHTML(hb.nome)}</div><div class="card-meta streak"> ${hb.streak} dias</div></div><div class="card-btns"><button class="btn-icon" onclick="deletarHabito(${hb.id})">✕</button></div></div><div class="habito-heatmap" id="heatmap-${hb.id}"></div>`;
    l.appendChild(d);
    renderHeatmap(hb.id, hb.streak);
  });
}
function renderHeatmap(id, st) {
  const e = document.getElementById(`heatmap-${id}`);
  if (!e) return;
  e.innerHTML = "";
  const h = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = new Date(h);
    d.setDate(d.getDate() - i);
    const c = document.createElement("div");
    c.className = "heat-cell";
    if (i < st) c.classList.add("filled");
    e.appendChild(c);
  }
}
function abrirModalHabito() {
  document.getElementById("modal-habito").style.display = "flex";
  document.getElementById("habito-nome").focus();
}
async function criarHabito() {
  const n = document.getElementById("habito-nome").value.trim();
  const ic = document.getElementById("habito-icone").value.trim() || "H";
  const co = document.getElementById("habito-cor").value;
  if (!n) return;
  await chamarAPI("criar_habito", n, ic, co);
  fecharModal("modal-habito");
  document.getElementById("habito-nome").value = "";
  await carregarHabitos();
  await atualizarBadges();
  showToast("Hábito criado!", n, "success", 2200);
}
async function toggleHabito(id) {
  await chamarAPI("registrar_habito", id);
  await carregarHabitos();
  await atualizarBadges();
}
async function deletarHabito(id) {
  await chamarAPI("deletar_habito", id);
  await carregarHabitos();
  await atualizarBadges();
}
async function atualizarStatsFoco() {
  const r = await chamarAPI("get_stats_foco");
  if (!r.ok) return;
  document.getElementById("foco-stats").textContent =
    `Hoje: ${r.data.sessoes} sessão(ões) • ${r.data.minutos} min`;
}
const RING_CIRC = 2 * Math.PI * 110;
function atualizarAnelFoco() {
  const r = document.querySelector("#foco-ring .ring-fg");
  if (!r) return;
  r.style.strokeDashoffset =
    RING_CIRC * (1 - focoSegundos / (focoTotalSegundos || 1));
}
function focoIniciar() {
  const dm = parseInt(document.getElementById("foco-min").value) || 25;
  const pm = parseInt(document.getElementById("pausa-min").value) || 5;
  focoFase = "foco";
  focoPausado = false;
  focoSegundos = dm * 60;
  focoTotalSegundos = focoSegundos;
  document.getElementById("btn-foco-iniciar").disabled = true;
  document.getElementById("btn-foco-pausar").disabled = false;
  document.getElementById("btn-foco-cancelar").disabled = false;
  document.getElementById("foco-fase").textContent = " FOCO";
  document.getElementById("foco-fase").style.color = "var(--violeta)";
  atualizarTimerDisplay(focoSegundos);
  atualizarAnelFoco();
  focoInterval = setInterval(() => {
    if (focoPausado) return;
    focoSegundos--;
    atualizarTimerDisplay(focoSegundos);
    atualizarAnelFoco();
    if (focoSegundos <= 0) {
      clearInterval(focoInterval);
      if (focoFase === "foco") {
        focoFase = "pausa";
        focoSegundos = pm * 60;
        focoTotalSegundos = focoSegundos;
        document.getElementById("foco-fase").textContent = " PAUSA";
        document.getElementById("foco-fase").style.color = "var(--warning)";
        atualizarAnelFoco();
        showToast("Foco concluído!", "Pausa", "success", 3000);
        focoInterval = setInterval(() => {
          if (focoPausado) return;
          focoSegundos--;
          atualizarTimerDisplay(focoSegundos);
          atualizarAnelFoco();
          if (focoSegundos <= 0) {
            clearInterval(focoInterval);
            chamarAPI("salvar_sessao_foco", dm, pm, true);
            focoReset(dm);
            atualizarStatsFoco();
            showToast("Completo!", "", "success", 3500);
          }
        }, 1000);
      }
    }
  }, 1000);
}
function focoPausar() {
  focoPausado = !focoPausado;
  document.getElementById("btn-foco-pausar").textContent = focoPausado
    ? " Retomar"
    : " Pausar";
}
function focoCancelar() {
  clearInterval(focoInterval);
  const dm = parseInt(document.getElementById("foco-min").value) || 25;
  chamarAPI(
    "salvar_sessao_foco",
    dm,
    parseInt(document.getElementById("pausa-min").value) || 5,
    false,
  );
  focoReset(dm);
}
function focoReset(dm = 25) {
  clearInterval(focoInterval);
  focoSegundos = 0;
  focoTotalSegundos = dm * 60;
  focoPausado = false;
  document.getElementById("btn-foco-iniciar").disabled = false;
  document.getElementById("btn-foco-pausar").disabled = true;
  document.getElementById("btn-foco-cancelar").disabled = true;
  document.getElementById("btn-foco-pausar").textContent = " Pausar";
  document.getElementById("foco-fase").textContent = "FOCO";
  document.getElementById("foco-fase").style.color = "var(--violeta)";
  atualizarTimerDisplay(dm * 60);
  const r = document.querySelector("#foco-ring .ring-fg");
  if (r) r.style.strokeDashoffset = 0;
}
function atualizarTimerDisplay(s) {
  document.getElementById("foco-timer").textContent =
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}
function fecharModal(id) {
  document.getElementById(id).style.display = "none";
}
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal")) e.target.style.display = "none";
});
async function verificarModelosLocais() {
  const status = document.getElementById("local-media-status");
  status.textContent = "Verificando…";
  try {
    const result = await chamarAPI("status_modelos_locais");
    if (!result.ok) throw new Error(result.erro);
    status.textContent = Object.entries({transcricao: "Transcrição", voz: "Voz"})
      .map(([key, label]) => label + ": " + (result.data[key] ? "arquivos encontrados" : "instalação pendente")).join(" · ");
  } catch (error) { status.textContent = error.message; }
}
