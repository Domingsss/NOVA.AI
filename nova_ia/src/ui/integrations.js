// Cadastro de APIs. As chaves existentes nunca são devolvidas à interface.
let integrations = [];

async function loadLocalChat() {
  try {
    const response = await chamarAPI("get_chat_local");
    if (!response.ok) throw new Error(response.erro);
    document.getElementById("local-chat-enabled").checked =
      response.data.enabled;
    document.getElementById("local-chat-model").value = response.data.model;
  } catch (error) {
    showToast("Erro nas configurações locais", error.message, "error");
  }
}

async function refreshLocalModels() {
  const status = document.getElementById("local-chat-status");
  status.textContent = "Consultando Ollama...";
  try {
    const response = await chamarAPI("listar_modelos_locais");
    if (!response.ok) throw new Error(response.erro);
    const list = document.getElementById("local-chat-models");
    list.replaceChildren();
    for (const model of response.data) {
      const option = document.createElement("option");
      option.value = model;
      list.append(option);
    }
    status.textContent = response.data.length
      ? "Modelos encontrados. Escolha um e salve as configurações."
      : "Nenhum modelo instalado no Ollama.";
    if (
      !document.getElementById("local-chat-model").value &&
      response.data.length
    )
      document.getElementById("local-chat-model").value = response.data[0];
  } catch (error) {
    status.textContent = error.message;
  }
}

async function loadIntegrations() {
  const list = document.getElementById("integration-list");
  list.textContent = "Carregando...";
  try {
    const response = await chamarAPI("listar_integracoes");
    if (!response.ok) throw new Error(response.erro);
    integrations = response.data;
    list.replaceChildren();
    if (!integrations.length)
      list.textContent = "Nenhuma API adicional cadastrada.";
    for (const item of integrations) {
      const row = document.createElement("div");
      row.className = "integration-row";
      const label = document.createElement("span");
      label.textContent = `${item.name} · ${item.category === "videos" ? "vídeos" : item.category} · ${item.has_key ? "chave salva" : "sem chave"}`;
      const edit = document.createElement("button");
      edit.className = "btn-secondary";
      edit.textContent = "Editar";
      edit.onclick = () => editIntegration(item);
      const remove = document.createElement("button");
      remove.className = "btn-secondary";
      remove.textContent = "Excluir";
      remove.onclick = async () => {
        if (!confirm(`Excluir o cadastro de ${item.name}?`)) return;
        try {
          const result = await chamarAPI("excluir_integracao", item.id);
          if (!result.ok) throw new Error(result.erro);
          resetIntegration();
          await loadIntegrations();
        } catch (error) {
          showToast("Erro", error.message, "error");
        }
      };
      row.append(label, edit, remove);
      list.append(row);
    }
  } catch (error) {
    list.textContent = error.message || "Não foi possível carregar as APIs.";
  }
}

function editIntegration(item) {
  for (const field of ["id", "name", "category", "url", "model"]) {
    document.getElementById(`integration-${field}`).value = item[field] || "";
  }
  document.getElementById("integration-key").value = "";
  document.getElementById("integration-clear-key").checked = false;
  document.getElementById("integration-name").focus();
}

function resetIntegration() {
  editIntegration({ category: "respostas" });
}

async function saveIntegration() {
  const button = document.getElementById("integration-save");
  button.disabled = true;
  try {
    const data = {};
    for (const field of ["id", "name", "category", "url", "model", "key"]) {
      data[field] = document
        .getElementById(`integration-${field}`)
        .value.trim();
    }
    data.clear_key = document.getElementById("integration-clear-key").checked;
    const response = await chamarAPI("salvar_integracao", data);
    if (!response.ok) throw new Error(response.erro);
    resetIntegration();
    await loadIntegrations();
    showToast(
      "API cadastrada",
      "Dados salvos para integração futura.",
      "success",
    );
  } catch (error) {
    showToast("Erro ao salvar API", error.message, "error");
  } finally {
    button.disabled = false;
  }
}
