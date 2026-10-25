// usa os dados do painel pra preencher os planetas.
(() => {
  const agents = [
    {
      id: "terra",
      name: "Terra",
      area: "Clima",
      note: "Seu céu, agora",
      color: "#69d6c7",
      card: ".dash-weather",
      source: "dash-clima",
    },
    {
      id: "tita",
      name: "Titã",
      area: "Sistema",
      note: "O pulso da máquina",
      color: "#dcb77e",
      card: ".dash-system",
      source: "dash-sistema",
    },
    {
      id: "marte",
      name: "Marte",
      area: "Tarefas",
      note: "Um passo de cada vez",
      color: "#ed947c",
      card: ".dash-tasks",
      source: "dash-tarefas",
    },
    {
      id: "lua",
      name: "Lua",
      area: "Hábitos",
      note: "Pequenos ciclos, evolução",
      color: "#ccd2ed",
      card: ".dash-habits",
      source: "dash-habitos",
    },
    {
      id: "mercurio",
      name: "Mercúrio",
      area: "Mercado",
      note: "Movimentos e cotações",
      color: "#b7a1eb",
      card: ".dash-finance",
      source: "dash-financas",
    },
    {
      id: "europa",
      name: "Europa",
      area: "Atalhos e foco",
      note: "Espaço para se concentrar",
      color: "#8dbfe9",
      card: ".dash-shortcuts",
    },
  ];
  const chat = document.getElementById("aba-chat");
  const presence = document.getElementById("nova-presence");
  const toggle = document.getElementById("nova-universe-toggle");
  const solar = document.createElement("section");
  solar.id = "aba-solar";
  solar.className = "aba";
  solar.setAttribute("aria-label", "Sistema NOVA");
  solar.innerHTML = `<header class="solar-header"><div><h1>Sistema NOVA</h1><p>Seis mundos. Tudo conectado a você.</p></div><button type="button" id="solar-back">← Conversar com a NOVA</button></header>
    <div class="solar-map"><svg class="solar-orbits" viewBox="0 0 1000 620" preserveAspectRatio="none" aria-hidden="true"><ellipse cx="500" cy="310" rx="340" ry="235"/><ellipse cx="500" cy="310" rx="200" ry="150"/><path d="M500 310L170 105M500 310L830 105M500 310L170 310M500 310L830 310M500 310L170 515M500 310L830 515"/></svg><div id="solar-core"><span class="solar-core-label">NOVA · NÚCLEO</span></div>
    ${agents.map((a, i) => `<button type="button" class="planet-node planet-${a.id}" data-agent="${a.id}" style="--planet:${a.color};--delay:${i * 65}ms" aria-haspopup="dialog"><span class="planet-sphere" aria-hidden="true"></span><span class="planet-text"><strong>${a.name}</strong><span class="planet-summary">${a.note}</span><span class="planet-open">Explorar </span></span></button>`).join("")}</div><p class="solar-footer">Selecione um mundo para ver seus dados e conversar com seu agente.</p>
    <dialog id="planet-dialog" aria-labelledby="planet-title" aria-describedby="planet-description"><header><div class="planet-identity"><span class="planet-avatar planet-sphere" aria-hidden="true"></span><div><span id="planet-area" class="planet-eyebrow"></span><h2 id="planet-title"></h2></div></div><button type="button" id="planet-close" aria-label="Fechar detalhes">✕</button></header><p id="planet-description"></p><div id="planet-data"></div><div id="planet-suggestions" aria-label="Sugestões de perguntas"></div><form id="planet-form"><label for="planet-question">Converse com <span id="planet-chat-name">este agente</span></label><div><input id="planet-question" maxlength="2000" required placeholder="O que você quer saber?" autocomplete="off"/><button type="submit">Enviar ↗</button></div></form><div id="planet-answer" role="status" aria-live="polite"></div></dialog>`;
  chat.before(solar);
  const core = document.getElementById("solar-core");
  const dialog = document.getElementById("planet-dialog");
  const data = document.getElementById("planet-data");
  let selected = null,
    movedCard = null,
    marker = null,
    request = 0;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  function animateMove(before) {
    if (reduced.matches) return;
    const after = toggle.getBoundingClientRect();
    if (!after.width || !before.width) return;
    toggle.animate(
      [
        {
          transform: `translate(${before.x - after.x}px,${before.y - after.y}px) scale(${before.width / after.width})`,
        },
        { transform: "translate(0,0) scale(1)" },
      ],
      { duration: 720, easing: "cubic-bezier(.22,1,.36,1)" },
    );
  }
  function returnPresence() {
    if (presence.parentNode !== chat)
      chat.insertBefore(presence, document.getElementById("chat-msgs"));
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Explorar o sistema NOVA");
  }
  function back() {
    const before = toggle.getBoundingClientRect();
    returnPresence();
    trocarAba("chat");
    animateMove(before);
    toggle.focus({ preventScroll: true });
  }
  function open() {
    if (solar.classList.contains("active")) {
      back();
      return;
    }
    const before = toggle.getBoundingClientRect();
    core.prepend(presence);
    trocarAba("solar");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Voltar à conversa com a NOVA");
    animateMove(before);
    carregarDashboard();
  }
  toggle.addEventListener("click", open);
  document.getElementById("solar-back").addEventListener("click", back);
  function closeDetails() {
    request++;
    if (movedCard && marker) {
      marker.replaceWith(movedCard);
      movedCard = marker = null;
    }
    dialog.close();
    selected = null;
    document.querySelector("#planet-form button").disabled = false;
  }
  document
    .getElementById("planet-close")
    .addEventListener("click", closeDetails);
  dialog.addEventListener("cancel", (e) => {
    e.preventDefault();
    closeDetails();
  });
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) {
      const r = dialog.getBoundingClientRect();
      if (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      )
        closeDetails();
    }
  });
  solar.querySelectorAll("[data-agent]").forEach((button) =>
    button.addEventListener("click", () => {
      selected = agents.find((a) => a.id === button.dataset.agent);
      document.getElementById("planet-title").textContent = selected.name;

      document.getElementById("planet-description").textContent =
        selected.note + ". Explore seus dados com a ajuda da NOVA.";
      document.getElementById("planet-area").textContent = "AGENTE NOVA / " + selected.area;
      document.getElementById("planet-chat-name").textContent = selected.name;
      dialog.dataset.agent = selected.id;
      const suggestions = document.getElementById("planet-suggestions");
      suggestions.replaceChildren();
      if (selected.id === "terra") {
        ["Vou precisar de guarda-chuva?", "Como está a sensação térmica?", "O que vestir hoje?"].forEach((question) => {
          const suggestion = document.createElement("button");
          suggestion.type = "button";
          suggestion.textContent = question;
          suggestion.addEventListener("click", () => {
            const input = document.getElementById("planet-question");
            input.value = question;
            input.focus();
          });
          suggestions.append(suggestion);
        });
      }
      dialog.style.setProperty("--planet", selected.color);
      document.getElementById("planet-answer").textContent = "";
      document.getElementById("planet-question").value = "";
      movedCard = document.querySelector(selected.card);
      marker = document.createComment("dashboard-card");
      movedCard.before(marker);
      data.append(movedCard);
      dialog.showModal();
      document.getElementById("planet-close").focus();
    }),
  );
  document
    .getElementById("planet-form")
    .addEventListener("submit", async (e) => {
      e.preventDefault();
      const question = document.getElementById("planet-question").value.trim();
      const button = e.currentTarget.querySelector("button");
      if (!selected || !question || button.disabled) return;
      const ticket = ++request,
        agent = selected;
      button.disabled = true;
      const answer = document.getElementById("planet-answer");
      answer.textContent = `${agent.name} está consultando seus dados…`;
      try {
        const result = await chamarAPI(
          "consultar_agente",
          agent.id,
          question,
          cidadeDashboard,
        );
        if (ticket !== request) return;
        answer.textContent = result.ok
          ? result.data.resposta
          : `Não foi possível consultar ${agent.name}: ${result.erro || "Tente novamente."}`;
      } catch (error) {
        if (ticket === request)
          answer.textContent =
            "Não foi possível concluir a consulta. Tente novamente.";
      } finally {
        if (ticket === request) button.disabled = false;
      }
    });
  // Existing controls inside a planet still navigate to the original functional screens.
  new MutationObserver(() => {
    if (!solar.classList.contains("active")) {
      if (dialog.open) closeDetails();
      returnPresence();
    }
    document.body.classList.toggle(
      "nova-immersive",
      chat.classList.contains("active") || solar.classList.contains("active"),
    );
  }).observe(document.getElementById("conteudo"), {
    subtree: true,
    attributes: true,
    attributeFilter: ["class"],
  });
  const summarize = () =>
    agents.forEach((a) => {
      if (!a.source) return;
      const source = document.getElementById(a.source);
      const parts = [];
      if (source) {
        const walker = document.createTreeWalker(source, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const text = walker.currentNode.textContent.trim();
          if (text) parts.push(text);
        }
      }
      const value = parts.join(" · ");
      const label = solar.querySelector(
        `[data-agent="${a.id}"] .planet-summary`,
      );
      const summary = value ? value.slice(0, 95) : a.note;
      if (label.textContent !== summary) label.textContent = summary;
    });
  agents.forEach((a) => {
    if (a.source)
      new MutationObserver(summarize).observe(
        document.getElementById(a.source),
        { childList: true, subtree: true, characterData: true },
      );
  });
  document.addEventListener("keydown", (e) => {
    if (
      e.key === "Escape" &&
      solar.classList.contains("active") &&
      !dialog.open &&
      !e.defaultPrevented
    )
      back();
  });
  document.body.classList.add("nova-immersive");
})();
