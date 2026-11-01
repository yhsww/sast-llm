# SAST Security Test Case Generator — Branch Execution Guide

Este guia apresenta a configuração do projeto e o passo a passo para executar cada branch, selecionar a LLM, gerar casos de teste e alternar entre as abordagens do experimento.

## Project overview

O projeto recebe relatórios SAST do SonarQube e gera casos de teste de segurança estruturados usando um modelo de linguagem (LLM). As branches representam três estratégias de geração:

- **Branch 1 — Direct LLM (`main` / `branch-1-direct-llm`):** envia os achados diretamente à LLM, sem recuperação de documentos.
- **Branch 2 — RAG with CWE and WSTG (`branch-2-rag-cwe-wstg`):** recupera informações das bases CWE e WSTG para enriquecer o contexto.
- **Branch 3 — RAG with code context (`branch-3-rag-code-context`):** combina a recuperação CWE/WSTG com trechos do código-fonte associados aos achados.

Os comandos deste documento usam **PowerShell no Windows**.

## Requirements

- Python 3.11 ou superior
- Git
- Chave de API válida para o provedor escolhido
- Dependências listadas em `requirements.txt`

## 1. Initial setup

### 1.1 Clone the repository

Se ainda não clonou o projeto:

```powershell
git clone https://github.com/yhsww/sast-llm.git
cd sast-llm
```

Se o repositório já estiver no computador, abra o PowerShell na pasta do projeto.

### 1.2 Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação, execute na mesma janela:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 1.3 Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Após alternar de branch, execute novamente `python -m pip install -r requirements.txt` caso o arquivo `requirements.txt` tenha mudado.

### 1.4 Configure environment variables

Crie o arquivo `.env` na raiz do projeto a partir do modelo da branch selecionada:

```powershell
Copy-Item .env.example .env
```

Se `.env` já existir, não o sobrescreva sem guardar as configurações atuais. Edite o arquivo e preencha as chaves e os modelos que pretende utilizar. Nunca versione ou compartilhe chaves de API.

## 2. Choosing the LLM

As branches `main`, `branch-1-direct-llm` e `branch-2-rag-cwe-wstg` oferecem configuração de provedor por meio de `LLM_PROVIDER`. A branch 3 usa OpenAI para geração e embeddings.

### 2.1 Providers in `main`, `branch-1-direct-llm` and `branch-2-rag-cwe-wstg`

Configure `LLM_PROVIDER` como `openai`, `gemini`, `kimi` ou `claude` e preencha a chave e o identificador do modelo correspondente no `.env`.

```env
# Escolha um provedor: openai, gemini, kimi ou claude
LLM_PROVIDER=openai

# OpenAI
OPENAI_API_KEY=sua_chave_aqui
OPENAI_CHAT_MODEL=gpt-4.1

# Gemini
GOOGLE_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3.8-flash

# Kimi
KIMI_API_KEY=sua_chave_aqui
KIMI_MODEL=moonshot-v1-8k

# Claude
ANTHROPIC_API_KEY=sua_chave_aqui
CLAUDE_MODEL=claude-sonnet-4-5
```

Os nomes e valores padrão podem variar entre branches. O arquivo `.env.example` e `backend/config.py` da branch selecionada são a referência final. Use modelos disponíveis para sua conta.

Na `main`, também é possível selecionar o provedor pelo argumento `--provider` do `run_experiment.py`. Na branch 1, selecione o provedor alterando `LLM_PROVIDER` no `.env`. Na branch 2, o executor experimental percorre os provedores configurados.

### 2.2 Provider in `branch-3-rag-code-context`

A branch 3 usa OpenAI. Configure as variáveis abaixo no `.env`:

```env
OPENAI_API_KEY=sua_chave_aqui
OPENAI_CHAT_MODEL=gpt-4.1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_PATH=./chroma_data
TOP_K_CWE=2
TOP_K_WSTG=2
```

Essa branch não oferece a seleção de Gemini, Kimi ou Claude no `backend/config.py` recebido.

## 3. Branch `main` — Direct LLM experiment

Na branch `main`, tanto `python query.py` quanto `python run_experiment.py` delegam a execução ao mesmo fluxo:

1. Lê automaticamente `data/sast_reports/sample.json`.
2. Permite selecionar a LLM no terminal: OpenAI, Gemini, Kimi ou Claude.
3. Envia os achados diretamente à LLM, sem RAG e sem solicitar contexto adicional.
4. Gera e salva o relatório JSON na pasta correspondente ao provedor.

### Execução

```powershell
git switch main
python -m pip install -r requirements.txt
python query.py
```

Também é possível iniciar pelo ponto de entrada compatível:

```powershell
python run_experiment.py
```

Os arquivos de saída usam nomes estáveis, como `sample_LLM.json`, em `results/GPT4.1/`, `results/Gemini/`, `results/Kimi/` ou `results/Claude/`. Uma nova execução para o mesmo relatório e provedor substitui o arquivo anterior. O conteúdo JSON não inclui data ou hora de execução. Erros são registrados em um arquivo `*_ERROR.txt separado do relatório de sucesso.

Configure as chaves e os identificadores de modelo no arquivo `.env` antes de executar. A seleção feita no terminal determina o provedor usado naquela execução.

## 4. Branch 1 — Direct LLM

**Branch:** `branch-1-direct-llm`

Esta abordagem envia os achados diretamente à LLM, sem recuperação de documentos CWE/WSTG.

### Steps

1. Selecione a branch:

   ```powershell
   git switch branch-1-direct-llm
   ```

2. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Configure `.env` com `LLM_PROVIDER`, a chave de API e o modelo desejado, conforme a seção 2.

4. Para validar o relatório sem chamar a API, execute:

   ```powershell
   python run_experiment.py --only GT01 --simulate
   ```

5. Para gerar casos de teste para um relatório:

   ```powershell
   python run_experiment.py --only GT01
   ```

6. Para processar todos os relatórios `GT*.json`:

   ```powershell
   python run_experiment.py
   ```

O argumento `--only` seleciona um relatório específico. Nesta branch, a seleção da LLM é feita pelo `LLM_PROVIDER` do `.env`, e não por um argumento `--provider`.

Os resultados são gravados em `results/<nome-do-modelo>/`. Arquivos existentes podem ser ignorados; preserve ou mova os resultados anteriores antes de repetir uma execução.

## 5. Branch 2 — RAG with CWE and WSTG

**Branch:** `branch-2-rag-cwe-wstg`

Esta abordagem recupera documentos das coleções CWE e WSTG no ChromaDB e usa o contexto recuperado para fundamentar a geração dos casos de teste.

### Steps

1. Selecione a branch:

   ```powershell
   git switch branch-2-rag-cwe-wstg
   ```

2. Instale as dependências e configure `.env` conforme as seções 1 e 2.

3. Construa a base CWE:

   ```powershell
   python -m scripts.build_cwe_kb
   ```

   O script pode usar o catálogo XML local ou tentar obter a fonte necessária, conforme as opções disponíveis nessa branch.

4. Construa a base WSTG:

   ```powershell
   python -m scripts.build_wstg_kb
   ```

5. Indexe os documentos no ChromaDB:

   ```powershell
   python -m scripts.ingest --reset
   ```

   `--reset` recria as coleções e remove a indexação anterior. Use-o quando quiser reconstruir a base, não em uma execução normal se deseja preservar a indexação existente.

6. Execute primeiro em modo de simulação, sem chamadas de geração:

   ```powershell
   python -m scripts.run_gt_experiment
   ```

7. Execute a geração real dos casos para os relatórios GT01–GT08:

   ```powershell
   python -m scripts.run_gt_experiment --execute
   ```

O executor percorre os provedores configurados e grava os resultados nas pastas de `results/` por provedor. Arquivos existentes podem ser ignorados. Verifique os arquivos JSON, os arquivos de erro e o resumo exibido no terminal.

## 6. Branch 3 — RAG with code context

**Branch:** `branch-3-rag-code-context`

Esta abordagem combina o contexto CWE/WSTG recuperado com trechos de código-fonte fornecidos pelo usuário para cada achado.

### Steps

1. Selecione a branch:

   ```powershell
   git switch branch-3-rag-code-context
   ```

2. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Configure a chave OpenAI e os parâmetros de embeddings/RAG no `.env`, conforme a seção 2.2.

4. Construa a base CWE:

   ```powershell
   python -m scripts.build_cwe_kb
   ```

5. Construa a base WSTG:

   ```powershell
   python -m scripts.build_wstg_kb
   ```

6. Indexe os documentos:

   ```powershell
   python -m scripts.ingest --reset
   ```

7. Inicie a consulta interativa:

   ```powershell
   python query.py
   ```

8. Quando solicitado, informe o caminho do relatório SonarQube. Pressione Enter para usar o relatório padrão `data/sast_reports/sample.json`.

9. Informe um foco/contexto adicional ou pressione Enter para pular essa etapa.

10. Para cada achado, cole o trecho de código correspondente. Termine cada entrada com `###` em uma linha isolada. Para pular um trecho, pressione Enter e depois digite `###`.

**Snippet order for `sample.json`:**

| Finding | Rule | File |
|---------|------|------|
| 1 | `java:S3649` — SQL Injection | `data/code_snippets/UserRepository.java` |
| 2 | `java:S5131` — XSS | `data/code_snippets/CommentController.java` |
| 3 | `java:S2068` — Hard-coded password | `data/code_snippets/DatabaseConfig.java` |

A resposta JSON é impressa no terminal. Salve a saída manualmente para preservar o resultado; o `query.py` desta branch não grava automaticamente o JSON em `results/`.

## 7. Switching between branches

Antes de trocar de branch, salve ou faça commit das alterações locais que deseja manter.

```powershell
git status
git fetch origin
git branch -a
```

Para alternar, execute **um comando por vez**:

```powershell
git switch main
git switch branch-1-direct-llm
git switch branch-2-rag-cwe-wstg
git switch branch-3-rag-code-context
```

Se uma branch existir apenas no remoto, crie uma branch local de acompanhamento. Exemplo:

```powershell
git switch --track origin/branch-2-rag-cwe-wstg
```

Substitua pelo nome da branch desejada. Depois da troca, confira a branch ativa e reinstale as dependências caso necessário:

```powershell
git branch --show-current
python -m pip install -r requirements.txt
```

Não presuma que todas as branches possuem os mesmos scripts ou argumentos. Use a seção correspondente à branch selecionada.

## 8. Expected output and reports

Os relatórios de entrada `GT01.json` a `GT08.json` ficam em `data/sast_reports/`. Para comparar as abordagens, use os mesmos relatórios em todas as branches.

As saídas são estruturadas em JSON com `test_cases`. Nas branches RAG, o resultado também pode conter `retrieved_context`, indicando documentos recuperados das bases CWE/WSTG.

- **`main`:** resultados em subpastas de `results/`, organizadas por provedor.
- **`branch-1-direct-llm`:** resultados em `results/<nome-do-modelo>/`.
- **`branch-2-rag-cwe-wstg`:** resultados do executor em lote nas pastas de `results/` por provedor.
- **`branch-3-rag-code-context`:** JSON impresso no terminal; salve manualmente a saída.

Antes de cada execução, registre a branch e o commit:

```powershell
git branch --show-current
git rev-parse HEAD
```

Registre também o provedor, o identificador exato do modelo, o relatório de entrada e eventuais erros. Não inclua chaves de API no registro.

## 9. Troubleshooting

- **`ModuleNotFoundError`:** ative `.venv` e execute `python -m pip install -r requirements.txt`.
- **Erro de autenticação:** confira a chave, o provedor e o identificador do modelo no `.env`.
- **Relatório não encontrado:** confira se o arquivo existe em `data/sast_reports/` e se o nome segue o padrão esperado.
- **Nenhum contexto recuperado nas branches RAG:** reconstrua as bases e execute `python -m scripts.ingest --reset`.
- **Resultado anterior ignorado:** confira o comportamento do executor da branch; arquive o resultado antigo antes de repetir a execução.
- **Branch não encontrada:** execute `git fetch origin` e `git branch -a` para verificar os nomes disponíveis.
- **PowerShell bloqueia a ativação do ambiente:** use o comando temporário da seção 1.2.
