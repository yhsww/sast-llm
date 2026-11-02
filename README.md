# Experimento SAST-LLM — Guia de execução

Este repositório compara três estratégias para gerar casos de teste de segurança a partir de relatórios SAST do SonarQube:

1. **Direct LLM** — envia os achados diretamente à LLM.
2. **RAG CWE/WSTG** — recupera documentação CWE e OWASP WSTG para enriquecer os achados.
3. **RAG + contexto de código** — combina os achados, documentos recuperados e trechos reais do código-fonte relacionado.
   

## Sobre o projeto

O **SAST-LLM** é um experimento para investigar como modelos de linguagem (LLMs) podem ajudar a transformar achados de ferramentas de análise estática de segurança (SAST) em **casos de teste de segurança estruturados**. O projeto utiliza relatórios no formato do SonarQube e compara diferentes formas de fornecer contexto ao modelo, observando como cada estratégia pode influenciar a especificidade e a utilidade dos casos de teste gerados.

O sistema recebe os findings do relatório — por exemplo, regra, mensagem, severidade, componente, linha e tags — e solicita à LLM que produza casos de teste com campos como identificador, finding relacionado, título, objetivo, pré-condições, passos, resultado esperado e severidade. O resultado é salvo em JSON para inspeção e comparação posterior.

### Objetivo experimental

A questão central do projeto é: **fornecer contexto adicional e mais específico sobre uma vulnerabilidade ajuda a LLM a gerar casos de teste mais úteis e relacionados à implementação analisada?**

Para investigar essa questão, o repositório mantém três estratégias em branches separadas. Elas funcionam como condições experimentais: a estratégia direta é a referência de comparação; as demais acrescentam documentação de segurança recuperada e, na terceira estratégia, contexto de código-fonte.

### Fluxo geral

```text
Relatório SAST (JSON)
        |
        v
Validação e leitura dos findings
        |
        +--> Estratégia direta: findings ------------------+
        |                                                  |
        +--> RAG: findings -> busca em CWE e OWASP WSTG ---+--> LLM
        |                                                  |      |
        +--> RAG + código: findings + RAG + snippet -------+      v
                                                               Casos de teste
                                                                    |
                                                                    v
                                                           Relatório JSON em results/
```

Na estratégia RAG, a busca semântica recupera documentos relevantes da base local de conhecimento. Na estratégia com código, o snippet associado ao finding é acrescentado ao contexto enviado à LLM; ele complementa a documentação recuperada, mas não é, por si só, indexado na base vetorial.

### Estratégias comparadas

| Branch | Estratégia | Contexto enviado à LLM | Papel no experimento |
|---|---|---|---|
| `main` | Direct LLM | Findings do relatório SAST | Runner com opções `--report`/`--all-reports`; seleção de provedor por `--provider` ou menu interativo |
| `branch-1-direct-llm` | Direct LLM | Findings do relatório SAST | Mesma estratégia direta, mas com interface de execução própria: `--only`/`--allreports` e provedor padrão definido por `LLM_PROVIDER` |
| `branch-2-rag-cwe-wstg` | RAG com CWE e OWASP WSTG | Findings + documentos recuperados | Avaliar o efeito da documentação de segurança |
| `branch-3-rag-code-context` | RAG + contexto de código | Findings + documentos recuperados + snippet | Avaliar se o código torna os testes mais específicos à implementação |

As branches `main` e `branch-1-direct-llm` usam a mesma **estratégia experimental** (findings enviados diretamente à LLM, sem RAG e sem snippet adicional), mas **não têm execução idêntica**: os argumentos de linha de comando e a seleção padrão do provedor diferem. Na `main`, use `--report`/`--all-reports`; na `branch-1-direct-llm`, use `--only`/`--allreports`. A branch 1 usa `LLM_PROVIDER` como provedor padrão quando nenhum provedor é informado. Portanto, compare a estratégia mantendo entrada, provedor/modelo e modo de execução equivalentes, e não apenas repetindo o mesmo comando nas duas branches.

As branches 2 e 3 acrescentam, respectivamente, recuperação RAG e recuperação RAG com contexto de código. Consulte os comandos específicos de cada branch antes de executar.

### Dados utilizados

- **Relatórios SAST:** arquivos JSON em `data/sast_reports/`. O `sample.json` contém três exemplos: SQL Injection (`java:S3649`), XSS (`java:S5131`) e senha hardcoded (`java:S2068`).
- **Base CWE:** documentos extraídos do catálogo Common Weakness Enumeration (CWE), mantidos em `data/knowledge_base/cwe/`.
- **Base OWASP WSTG:** documentos derivados do OWASP Web Security Testing Guide, mantidos em `data/knowledge_base/wstg/`.
- **Snippets de código:** arquivos em `data/code_snippets/`, usados na branch 3 para fornecer contexto de implementação aos findings. O carregador da branch 3 procura associar os snippets ao tipo de vulnerabilidade e mantém alternativas de carregamento descritas na seção dessa branch.

### O que o projeto faz

**O projeto gera propostas de casos de teste de segurança; não executa automaticamente esses testes contra a aplicação.** Os resultados devem ser revisados por uma pessoa com conhecimento de segurança e desenvolvimento antes de serem usados em validação real.

O experimento também não demonstra, por si só, que uma estratégia é superior. Para comparar os resultados, execute as estratégias com entradas equivalentes, registre branch/commit, finding, provedor/modelo e modo de execução, e avalie os casos gerados com critérios consistentes. Um dry run confirma a preparação do contexto e do fluxo local, mas não comprova que uma chamada real à API foi concluída nem que os casos gerados são corretos.


## 1. Preparar o ambiente

### Clonar o projeto ou entrar na pasta

```powershell
git clone https://github.com/yhsww/sast-llm.git
cd sast-llm
```

Se o projeto já estiver clonado, abra o PowerShell na pasta que contém `query.py`, `requirements.txt` e a pasta `backend`.

### Criar e ativar o ambiente virtual

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação, execute:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Se trocar de branch e ela tiver dependências diferentes, execute novamente:

```powershell
python -m pip install -r requirements.txt
```

### Atualizar e escolher uma branch

```powershell
git fetch origin
git branch -a
```

Para atualizar a branch em que você está:

```powershell
git pull
```

Troque de branch com um comando por vez:

```powershell
git switch main
git switch branch-1-direct-llm
git switch branch-2-rag-cwe-wstg
git switch branch-3-rag-code-context
```

Se uma branch existir somente no remoto, crie o acompanhamento local, por exemplo:

```powershell
git switch --track origin/branch-3-rag-code-context
```

### Configurar as chaves de API

Na raiz do projeto, veja se existe um arquivo `.env.example`. Se existir, crie o arquivo local:

```powershell
Copy-Item .env.example .env
```

Preencha no `.env` somente as chaves dos provedores que pretende testar. A branches usam essas variáveis:

- `OPENAI_API_KEY` para GPT.
- `GOOGLE_API_KEY` para Gemini.
- `KIMI_API_KEY` para Kimi.
- `ANTHROPIC_API_KEY` para Claude.

Modelos padrão:

| Provedor | ID padrão |
|---|---|
| GPT | `gpt-6.1-sol` |
| Gemini | `gemini-3.8-flash` |
| Kimi | `kimi-k3.1-pro` |
| Claude | `claude-sonnet-5` |

## 2. Branch `main` — Direct LLM

A `main` usa `query.py` para ler relatórios de `data/sast_reports/` e enviar os achados diretamente à LLM, sem recuperação RAG ou trecho adicional de código. O relatório padrão é `sample.json`. Esta branch e `branch-1-direct-llm` implementam a mesma estratégia direta, mas possuem interfaces de execução diferentes: na `main`, a seleção do relatório usa `--report`/`--all-reports` e a seleção do provedor usa `--provider` ou o menu interativo.

Entre na branch e instale as dependências:

```powershell
git switch main
python -m pip install -r requirements.txt
```

### Validar os relatórios sem chamar APIs

```powershell
python query.py --simulate
python query.py --report GT01 --simulate
python query.py --all-reports --simulate
```

### Executar com um provedor

```powershell
python query.py --provider openai
python query.py --provider gemini
python query.py --provider kimi
python query.py --provider claude
python query.py --provider all
```

Para selecionar a entrada na `main`:

```powershell
python query.py --report sample.json
python query.py --report GT01.json
python query.py --all-reports
```

`--simulate` valida os arquivos sem chamar APIs e sem gravar resultados. Sem essa opção, os comandos de geração chamam as APIs dos provedores selecionados.

Esses comandos fazem chamadas reais, exceto quando acompanhados de `--simulate`. Confira os arquivos de saída em `results/` e mensagens `*_ERROR.txt`.

## 3. Branch `branch-1-direct-llm` — Direct LLM

Esta branch compara a mesma estratégia direta da `main` — sem recuperação de documentos e sem contexto adicional de código —, mas sua interface de execução é diferente. Ela usa `--only`/`--allreports` para selecionar relatórios e, se `--provider` não for informado, escolhe o provedor configurado em `LLM_PROVIDER` no `.env` (ou na configuração padrão). Por isso, os comandos da `main` não devem ser copiados para esta branch sem adaptar os argumentos.

```powershell
git switch branch-1-direct-llm
python -m pip install -r requirements.txt
python query.py --help
```

Validação sem chamadas reais:

```powershell
python query.py --simulate
```

Geração real com um provedor ou com todos:

```powershell
python query.py --provider gemini
python query.py --provider all
```

Para limitar a execução a um relatório, use `--only GT01.json` ou `--only sample.json`. Para processar todos os relatórios, use `--allreports`. Consulte `python query.py --help` para ver as opções disponíveis nesta branch. Configure no `.env` as credenciais dos provedores que pretende executar.

## 4. Branch `branch-2-rag-cwe-wstg` — RAG com CWE/WSTG

Esta branch recupera referências da base de conhecimento CWE e OWASP WSTG antes de gerar os casos de teste.

```powershell
git switch branch-2-rag-cwe-wstg
python -m pip install -r requirements.txt
```

Prepare ou reconstrua a base local:

```powershell
python -m scripts.build_cwe_kb
python -m scripts.build_wstg_kb
python -m scripts.ingest --reset
```

Use `--reset` somente quando quiser recriar as coleções do ChromaDB.

Valide a preparação e recuperação:

```powershell
python -m scripts.run_gt_experiment
```

Gere os resultados chamando a LLM:

```powershell
python -m scripts.run_gt_experiment --execute
```

O runner dessa branch processa os relatórios `GT01.json` a `GT08.json`. O modo sem `--execute` não comprova que a geração real pela LLM funciona. Confira o resumo no terminal e os arquivos em `results/`.

## 5. Branch `branch-3-rag-code-context` — RAG + contexto do código-fonte

**Esta é a branch que combina RAG com o trecho de código associado ao finding.** O passo mais importante é conferir que todos os achados receberam o trecho correto antes de chamar uma API.
Para a branch 3, o fluxo recomendado é: **dry run de um relatório → confirmar `snippets=N/N` → executar com `--execute` → conferir o arquivo e o resumo final → só então ampliar para outros relatórios/provedores.**

### 5.1. Entrar na branch e verificar os argumentos

```powershell
git switch branch-3-rag-code-context
python -m pip install -r requirements.txt
python query.py --help
```

Principais argumentos:

- `--provider GPT|Gemini|Kimi|Claude|all`: seleciona o provedor. Se omitido, o padrão é `all`.
- `--only GT01.json`: processa um único relatório.
- `--allreports`: processa os JSONs da pasta de relatórios.
- `--input-file caminho\arquivo.json`: processa um JSON específico, inclusive fora de `data/sast_reports/`.
- `--snippets-dir data/code_snippets`: local dos snippets salvos.
- `--source-root "C:\caminho\para\codigo"`: raiz local do projeto analisado pelo SonarQube.
- `--auto-snippets`: desativa a pergunta interativa e tenta carregar snippets salvos ou extrair do código local.
- `--execute`: chama a API e gera resultados reais.
- `--force`: permite sobrescrever um resultado existente.

### 5.2. Primeiro teste: dry run com snippet colado manualmente

Comece com apenas um relatório e um provedor. Este comando **não chama a API**:

```powershell
python query.py --provider GPT --only GT01.json --snippets-dir data/code_snippets
```

O programa mostrará a regra, mensagem, arquivo e linha do finding. Copie um trecho real do arquivo indicado no relatório e cole no terminal. Ao terminar o trecho, pressione Enter e digite `###` sozinho em uma linha:

```text
### 
```

O terminador encerra a entrada daquele finding. Se o relatório tiver vários findings, repita para cada um. Não digite `###` no meio do código.

Exemplo conhecido de `GT01.json`:

- Componente do finding: `juice-shop:routes/b2bOrder.ts`
- O arquivo de código de referência fica em: [routes/b2bOrder.ts no projeto avaliado](https://github.com/ASTRID-RESEARCH/SAST-COGNITIVE-LOAD-TEST-SECURITY/blob/main/juice-shop/routes/b2bOrder.ts)
- Use o código real da mesma versão/commit que foi analisada pelo SonarQube. Não invente ou reescreva o trecho.

A saída deve conter uma linha semelhante a:

```text
[RAG] GT01.json: findings=1, snippets=1/1, docs=4
```

Os números de `docs` podem variar. O importante é `snippets=N/N): todos os findings do relatório receberam contexto de código. Se aparecer `snippets=0/1` ou `snippets=2/3`, corrija os snippets antes de executar a geração. O dry run prepara o prompt, mas não cria uma resposta nova da LLM.

### 5.3. Executar a geração real

Depois de conferir o dry run, execute novamente adicionando `--execute`:

```powershell
python query.py --provider GPT --only GT01.json --snippets-dir data/code_snippets --execute
```

A captura manual acontece novamente; cole o código e finalize cada finding com `###`. Para Gemini, Kimi ou Claude, altere o valor de `--provider`, por exemplo:

```powershell
python query.py --provider Gemini --only GT01.json --snippets-dir data/code_snippets --execute
```

Se houver saldo/cota insuficiente, erro 401/403 ou modelo não habilitado, a chamada pode falhar mesmo que o dry run tenha funcionado. Isso não significa que o trecho não foi recebido.

### 5.4. Alternativa A — extrair snippets do código local automaticamente

Se o código analisado pelo SonarQube estiver no computador, informe a pasta raiz e use **ambas** as opções `--source-root` e `--auto-snippets`. Sem `--auto-snippets`, o programa continua pedindo os trechos manualmente.

Exemplo para um checkout do projeto de referência:

```powershell
python query.py --provider GPT --only GT01.json --source-root "C:\caminho\SAST-COGNITIVE-LOAD-TEST-SECURITY\juice-shop" --auto-snippets
```

Confira `snippets=N/N`. Se o resultado estiver correto, faça a geração real:

```powershell
python query.py --provider GPT --only GT01.json --source-root "C:\caminho\SAST-COGNITIVE-LOAD-TEST-SECURITY\juice-shop" --auto-snippets --execute
```

Substitua o caminho pelo caminho real da pasta no seu computador. O extrator tenta encontrar o arquivo pelo caminho do componente e, se necessário, pelo nome do arquivo. Se o arquivo ou a versão não corresponder ao relatório, o snippet pode ficar vazio ou o intervalo de linhas pode não representar o código analisado.

### 5.5. Alternativa B — carregar snippets organizados por tipo de finding

A branch 3 procura primeiro os snippets em `data/code_snippets/` e tenta associá-los ao tipo de vulnerabilidade identificado no finding. A associação usa a regra, as tags e a mensagem do relatório. Assim, o `sample.json` não precisa conter os trechos de código dentro de uma propriedade `code_snippets`.

Organize os arquivos por tipo de vulnerabilidade. O tipo pode estar no nome do arquivo ou no nome de uma subpasta. São aceitos arquivos de texto/código (`.txt`, `.md`, `.java`, `.js`, `.ts`, entre outros) e JSON (`.json`).

Exemplo ilustrativo de organização:

```text
data/
  code_snippets/
    sql_injection.txt
    xss.txt
    hardcoded_credentials.txt
```

Os nomes acima são exemplos: use os nomes e arquivos que realmente existem no seu repositório. Para os tipos presentes em `sample.json`, a associação procura rótulos relacionados a:

- SQL Injection: regra `java:S3649`, tags/mensagem de SQL injection.
- XSS: regra `java:S5131`, tags/mensagem de XSS ou cross-site scripting.
- Credenciais/senha hardcoded: regra `java:S2068`, tags/mensagem relacionadas a credenciais ou senha hardcoded.

Também é possível agrupar por subpastas, por exemplo `data/code_snippets/xss/trecho.ts`. Se houver vários arquivos que correspondam ao mesmo tipo, o carregador usa o primeiro em ordem alfabética; prefira manter um snippet de referência claro por tipo ou subpasta.

Para arquivos JSON, o carregador aceita uma string, uma lista de strings ou um objeto com uma propriedade como `code_snippet`, `snippet`, `code`, `source`, `content` ou `code_snippets`. O trecho deve ser código real relacionado ao tipo de vulnerabilidade, não apenas a descrição da regra.

Valide sem chamar uma API:

```powershell
python query.py --input-file data/sast_reports/sample.json --provider GPT --snippets-dir data/code_snippets --auto-snippets
```

Confira a linha `[RAG]` e confirme que `snippets=N/N` corresponde à quantidade de findings do relatório. Se aparecer uma contagem menor, confira se os nomes dos arquivos/subpastas correspondem aos tipos e se os arquivos contêm snippets legíveis.

Depois de confirmar os snippets, faça a chamada real (pode consumir créditos):

```powershell
python query.py --input-file data/sast_reports/sample.json --provider GPT --snippets-dir data/code_snippets --auto-snippets --execute
```

Compatibilidade: o carregador ainda aceita snippets embutidos no relatório e um arquivo com o mesmo nome-base do relatório (por exemplo, `data/code_snippets/sample.json`) como alternativas de fallback quando não encontra snippets por tipo.

### 5.6. Processar vários relatórios

Dry run de todos os relatórios `GT*.json`:

```powershell
python query.py --provider Gemini --allreports
```

Geração real para todos os relatórios com um provedor:

```powershell
python query.py --provider Gemini --allreports --execute
```

Para todos os provedores:

```powershell
python query.py --provider all --allreports --execute
```

Antes de uma execução em lote, é recomendável validar um relatório individual, verificar os snippets e confirmar que a chave e a cota do provedor estão funcionando.

### 5.7. Onde ficam os resultados

Cada branch grava os arquivos por provedor:

| Provedor | Pasta de saída |
|---|---|
| GPT | `results/GPT5.5/` |
| Gemini | `results/Gemini/` |
| Kimi | `results/Kimi/` |
| Claude | `results/Claude/` |

Exemplo: `results/GPT5.5/GT01_LLM.json`. Erros de geração real podem ser registrados em `*_ERROR.txt`. Por padrão, resultados existentes são preservados; use `--force` somente se quiser sobrescrever:

```powershell
python query.py --provider GPT --only GT01.json --snippets-dir data/code_snippets --auto-snippets --execute --force
```

### 5.8. Como interpretar o resumo

- `[RAG]`: informa quantos findings foram lidos, quantos snippets foram carregados e quantos documentos foram recuperados.
- `[DRY RUN]`: o prompt foi preparado; não houve geração real pela API.
- `[OK] Saved ...`: arquivo de resultado novo foi gravado.
- `[SKIP] Preserving existing result ...`: o arquivo já existia e foi preservado.
- `[SKIP] ... API key ... is not configured`: não foi feita chamada porque a variável da chave está ausente.
- `ERROR` com HTTP 429, saldo ou quota: verifique cobrança/limites do provedor antes de repetir.
- `FINAL SUMMARY`: resumo agregado dos provedores e relatórios processados.

O primeiro uso do ChromaDB pode inicializar o modelo local de embeddings e demorar mais. A recuperação RAG usa a regra, mensagem e tags do finding; o trecho de código é adicionado depois ao contexto enviado à LLM.

## 6. Testes e validação do experimento

Na raiz de cada branch, tente executar:

```powershell
python -m pytest -q
```

Se não houver testes descobertos, isso não equivale a aprovação do experimento. Execute também o dry run específico da branch e confira as contagens no terminal. Para validar a geração real, use primeiro um único finding e confirme que o arquivo foi criado nesta execução.

Antes de comparar resultados entre estratégias, registre a branch e o commit:

```powershell
git branch --show-current
git rev-parse HEAD
```

Registre também o relatório, finding, provedor/modelo, modo (dry run ou geração real), versão do código-fonte e resumo final. Não registre chaves de API.

## 7. Resumo das branches

| Branch | Estratégia | Entrada/execução principal |
|---|---|---|
| `main` | Direct LLM | `python query.py --simulate`; geração: `python query.py --provider gemini` ou `--report sample.json` |
| `branch-1-direct-llm` | Direct LLM | `python query.py --simulate`; geração: `python query.py --provider gemini --only sample.json` |

**Importante:** `main` e `branch-1-direct-llm` são equivalentes quanto à estratégia (Direct LLM), mas não quanto à interface/comandos de execução. Para uma comparação justa, use o mesmo relatório, o mesmo provedor/modelo e o mesmo modo (simulação ou chamada real), adaptando os argumentos à branch.
| `branch-2-rag-cwe-wstg` | RAG CWE/WSTG | `python -m scripts.run_gt_experiment` ou adicionar `--execute` |
| `branch-3-rag-code-context` | RAG + trecho de código | `python query.py --provider GPT --only GT01.json --snippets-dir data/code_snippets` |

