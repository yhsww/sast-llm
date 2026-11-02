# Experimento SAST-LLM — Guia de execução

Este repositório compara três estratégias para gerar casos de teste de segurança a partir de relatórios SAST:

1. **Direct LLM** — envia os achados diretamente ao modelo.
2. **RAG CWE/WSTG** — recupera documentação CWE e OWASP WSTG antes da geração.
3. **RAG + contexto de código** — combina CWE/WSTG com trechos do código-fonte relacionado aos achados.

Os comandos abaixo são para **Windows PowerShell**. Execute-os na raiz do repositório.

## 1. Preparação inicial

### Clonar ou abrir o projeto

Se ainda não tiver o repositório:

```powershell
git clone https://github.com/yhsww/sast-llm.git
cd sast-llm
```

Se já estiver clonado, abra o PowerShell na pasta `sast-llm`.

### Criar o ambiente e instalar dependências

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se a ativação for bloqueada pelo PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Configurar as chaves

Confira se a branch possui `.env.example`. Se possuir, crie o arquivo local:

```powershell
Copy-Item .env.example .env
```
### Atualizar e conferir branches

```powershell
git fetch origin
git branch -a
```

Para trocar de branch, execute um comando por vez:

```powershell
git switch main
git switch branch-1-direct-llm
git switch branch-2-rag-cwe-wstg
git switch branch-3-rag-code-context
```

Se a branch existir apenas no remoto, use, por exemplo, `git switch --track origin/branch-2-rag-cwe-wstg`.

## 2. Branch `main` — Direct LLM com `query.py`

A `main` usa `query.py` como executor principal. Por padrão, utiliza `data/sast_reports/sample.json`.

### Validar sem chamar APIs

```powershell
python query.py --simulate
python query.py --report GT01 --simulate
python query.py --all-reports --simulate
```

A simulação verifica os relatórios de entrada sem gerar análises por LLM.

### Gerar casos de teste

```powershell
python query.py
```

Siga o menu para escolher o provedor. Também é possível escolher diretamente:

```powershell
python query.py --provider openai
python query.py --provider gemini
python query.py --provider kimi
python query.py --provider claude
python query.py --provider all
```

Para selecionar os dados de entrada:

```powershell
python query.py --report GT01
python query.py --report sample.json
python query.py --all-reports
```

A geração real faz chamadas externas e pode consumir cota ou gerar custos. Consulte os arquivos JSON de saída em `results/` e as mensagens do terminal para identificar o resultado de cada execução.

## 3. Branch `branch-1-direct-llm` — Direct LLM

Esta branch envia os achados diretamente à LLM, sem recuperar documentos CWE/WSTG.

```powershell
git switch branch-1-direct-llm
python -m pip install -r requirements.txt
```

Configure o provedor e a chave no `.env`. Para validar em modo de simulação:

```powershell
python query.py --simulate
```

Para gerar com um provedor específico ou todos:

```powershell
python query.py --provider gemini
python query.py --all-providers
```

Troque `gemini` por `openai`, `kimi` ou `claude` para selecionar outro provedor. Para processar somente um relatório, use `--only GT01` ou `--only sample.json`. A execução real exige credenciais válidas e pode consumir cota.

## 4. Branch `branch-2-rag-cwe-wstg` — RAG com CWE e WSTG

Esta branch recupera documentação CWE e OWASP WSTG para acrescentar contexto aos achados.

```powershell
git switch branch-2-rag-cwe-wstg
python -m pip install -r requirements.txt
```

### Preparar a base de conhecimento

Execute os passos na raiz do repositório:

```powershell
python -m scripts.build_cwe_kb
python -m scripts.build_wstg_kb
python -m scripts.ingest --reset
```

O argumento `--reset` recria as coleções indexadas; use-o quando realmente quiser reconstruir a base.

### Simular e executar

Simulação, sem geração real por LLM:

```powershell
python -m scripts.run_gt_experiment
```

Geração real:

```powershell
python -m scripts.run_gt_experiment --execute
```

A execução real depende de credenciais válidas e da cota disponível no provedor. O runner dessa branch processa especificamente `GT01.json` a `GT08.json` (não inclui `sample.json` por padrão) e consulta a base Chroma durante a preparação. O modo sem `--execute` valida leitura e recuperação de contexto, mas **não comprova a geração real pela LLM**. As saídas usam `results/GPT5.5/`, `results/Gemini/`, `results/Kimi/` e `results/Claude/`. Embora o provedor OpenAI apareça no resumo do runner como `GPT`, os arquivos são salvos em `results/GPT5.5/` para manter a convenção de pastas das outras branches.

## 5. Branch `branch-3-rag-code-context` — RAG + contexto de código

Esta branch combina recuperação CWE/WSTG com trechos de código associados aos achados. Ela permite selecionar o relatório e o provedor pela linha de comando.

```powershell
git switch branch-3-rag-code-context
python -m pip install -r requirements.txt
```

Configure as credenciais exigidas pela configuração da branch. Confira os argumentos disponíveis:

```powershell
python query.py --help
```

### Simulação (sem chamadas de geração)

```powershell
python query.py --input-file data/sast_reports/sample.json
```

### Geração real

Exemplo com Gemini:

```powershell
python query.py --input-file data/sast_reports/sample.json --provider Gemini --execute
```

Para outro relatório, substitua o caminho de entrada. Para escolher outro provedor, use o nome aceito pelo `--help`, por exemplo `GPT`, `Kimi` ou `Claude`, e garanta que a credencial correspondente esteja configurada. A geração real pode consumir cota ou gerar custos.

Os trechos de código podem ser lidos de `data/code_snippets/` ou extraídos do código-fonte usando `--source-root <pasta>`, conforme os argumentos apresentados por `python query.py --help`.

## Modelos padrão configurados

As quatro branches usam os seguintes IDs para as APIs dos provedores, em `backend/config.py` e nos arquivos `.env.example`:

| Provedor | Modelo | ID de API |
|---|---|---|
| OpenAI | GPT-6.1 Sol | `gpt-6.1-sol` |
| Google | Gemini 3.8 Flash | `gemini-3.8-flash` |
| Moonshot | Kimi K3.1 Pro | `kimi-k3.1-pro` |
| Anthropic | Claude Sonnet 5 | `claude-sonnet-5` |

O ID da API não é necessariamente igual ao nome de exibição do modelo. O arquivo `.env` local prevalece sobre os valores padrão; atualize-o quando trocar de branch, preservando as chaves fora do Git. Nunca publique chaves reais no repositório.

## 6. Testes e critérios de validação

Na raiz do repositório, em cada branch, execute:

```powershell
python -m pytest -q
```

Se o projeto não tiver testes descobertos, o pytest informará que não encontrou testes; isso não equivale a aprovação. Execute também a simulação indicada para a branch e confira se o número de relatórios válidos corresponde ao esperado. A simulação não chama a API de geração e, portanto, não comprova autenticação, disponibilidade do modelo ou geração real.

Para validar a geração real, configure as credenciais do provedor e execute apenas um relatório primeiro. Confirme no terminal a contagem de achados, o resumo final e o arquivo de saída. Não interprete um arquivo `_ERROR.txt`, um relatório antigo ou uma execução em modo de simulação como resultado novo bem-sucedido.

Antes de comparar resultados entre abordagens, use os mesmos relatórios de entrada e registre:

```powershell
git branch --show-current
git rev-parse HEAD
```

Registre também o provedor/modelo, o relatório usado, o modo (simulação ou geração real) e o resumo final. Não registre chaves de API.

As entradas de referência ficam em `data/sast_reports/`. Os arquivos `GT01.json` a `GT08.json` são processados em lote pelos runners RAG; `sample.json` é a entrada padrão da `main` e pode ser passado explicitamente à `branch-3-rag-code-context`.

| Branch | Entrada padrão | Saídas | Observações |
|---|---|---|---|
| `main` | `sample.json`; `--all-reports` lê todos os JSON da pasta | `results/GPT5.5/`, `results/Gemini/`, `results/Kimi/`, `results/Claude/` | `--simulate` só valida JSON; não escreve resultados. |
| `branch-1-direct-llm` | Todos os JSON em `data/sast_reports/`, incluindo `sample.json` | Mesmas pastas de provedor da `main` | Use `--only GT01` para um relatório ou `--all-providers` para todos os provedores. |
| `branch-2-rag-cwe-wstg` | `GT01.json` a `GT08.json` | `results/GPT5.5/`, `results/Gemini/`, `results/Kimi/`, `results/Claude/` | Não inclui `sample.json` no lote fixo; no modo real preserva resultados já existentes e os pula. |
| `branch-3-rag-code-context` | Todos os `GT*.json`; também aceita `--input-file` | `results/GPT5.5/`, `results/Gemini/`, `results/Kimi/`, `results/Claude/` | O modo real preserva resultados existentes; use `--force` para sobrescrever. |

O nome de saída é `<nome-do-relatório>_LLM.json`; erros de execução real podem ser registrados como `<nome-do-relatório>_ERROR.txt`. Confira sempre a branch ativa e o caminho impresso no terminal. Na `branch-2-rag-cwe-wstg`, o provedor OpenAI pode aparecer como `GPT` no terminal, mas a pasta de saída padronizada é `GPT5.5`. Registre também branch, provedor, modelo e relatório de entrada.
