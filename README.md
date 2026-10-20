# NOVA

Assistente pessoal desktop em Python, com interface HTML, CSS e JavaScript via pywebview.

## Organização

- `nova_ia/src/`: código Python em uso.
- `nova_ia/src/ui/`: interface atual, incluindo o sistema solar e as configurações.
- `nova_ia/data/`: dados locais do navegador e cadastro de APIs. Não compartilhar.
- `nova_ia/assets/`: recursos e imagens do aplicativo.
- `scripts/`: ferramentas de manutenção do projeto.
- `tests/`: verificações automatizadas.
- `docs/previews/`: capturas de referência da interface.
- `legacy/`: interfaces anteriores, experimentos e cópias preservadas; não fazem parte da inicialização atual.

O banco `nova_ia/src/nova.db` e a chave Gemini permanecem no local original por compatibilidade. Não os apague: contêm dados pessoais. Os executáveis existentes em `nova_ia/dist/` também foram preservados; precisam ser recompilados para receber alterações no código.

## Executar

Na pasta deste README, com Python instalado:

```powershell
py -m venv nova_ia/.venv
nova_ia/.venv/Scripts/python.exe -m pip install -r nova_ia/requirements.txt
nova_ia/.venv/Scripts/python.exe nova_ia/src/main.py
```

As dependências opcionais para processamento avançado de imagens são `rembg` e `onnxruntime`. O experimento de geração local em `legacy/experiments/` não faz parte do fluxo atual.

## Configurar APIs

### Ollama local

O chat agora pode usar o Ollama instalado no computador, sem chave de API. Em **Configurações → Chat no computador**, ative o Ollama, clique em **Buscar modelos no computador**, escolha um modelo instalado e clique em **Salvar** no rodapé. Em branco, o modelo é selecionado pela primeira entrada retornada pelo Ollama.

O servidor deve estar aberto em `http://127.0.0.1:11434`. O chat envia histórico e recebe respostas em streaming pela API nativa do Ollama. Imagens exigem um modelo com visão; a transcrição de áudio existente continua dependendo do Gemini. Desligar a opção local volta a usar a chave Gemini. O cadastro genérico de APIs adicionais não altera essa seleção.

Referência: https://docs.ollama.com/api/chat

### Outros serviços

Abra **Configurações** no aplicativo:

1. A seção **Respostas · Gemini em uso** altera a chave usada pelo chat atual. Clique em **Salvar** no rodapé.
2. Em **APIs adicionais**, escolha respostas, imagens ou vídeos e preencha nome, endereço, modelo e chave. Clique em **Salvar API** para cada cadastro.
3. Use **Editar** para alterar um cadastro. Deixar a chave vazia mantém a anterior; a opção **Remover a chave salva** a apaga. **Excluir** remove o cadastro inteiro.

É possível cadastrar vários serviços por finalidade. Esses cadastros ficam preparados para integrações futuras: salvar uma URL ou chave não conecta automaticamente um provedor nem ativa geração de vídeo. A implementação depende do formato de requisição e resposta de cada serviço escolhido.

As chaves adicionais ficam em `nova_ia/data/integrations.json`, em texto local, e não são retornadas à interface. Esse arquivo está no `.gitignore`. Arquivos pessoais que já eram rastreados pelo Git não deixam de ser rastreados apenas por essa regra; revise-os antes de publicar o repositório.

## Verificar

```powershell
py -m unittest discover -s tests
node --check nova_ia/src/ui/integrations.js
```
