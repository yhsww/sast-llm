# Experimento SAST-LLM — Guia de execução

Este repositório compara três estratégias para gerar casos de teste de segurança a partir de relatórios SAST do SonarQube:

1. **Direct LLM/main** — envia os achados diretamente à LLM.
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

Preencha no `.env` somente as chaves dos provedores que pretende testar. As branches usam estas variáveis:

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

## 5. Branch `branch-3-rag-code-context` — RAG + código-fonte

Esta branch precisa do código-fonte do projeto analisado para adicionar trechos reais ao contexto do finding. Os trechos podem ser obtidos de duas formas:

1. **Baixar o projeto:** [SAST-COGNITIVE-LOAD-TEST-SECURITY](https://github.com/ASTRID-RESEARCH/SAST-COGNITIVE-LOAD-TEST-SECURITY) e informe a pasta do código com `--source-root` e `--auto-snippets`.
2. **Consultar pelo GitHub:** abra o repositório, localize o arquivo e copie o trecho correspondente ao finding. Cole-o no terminal quando o programa solicitar e finalize a entrada digitando `###` sozinho em uma linha.

Repositório com os códigos-fonte:  
https://github.com/ASTRID-RESEARCH/SAST-COGNITIVE-LOAD-TEST-SECURITY

### Executar

Entre na branch e instale as dependências:

```powershell
git switch branch-3-rag-code-context
python -m pip install -r requirements.txt
python query.py --help
```

**Opção A — usar o código local automaticamente**

```powershell
python query.py --provider GPT --only GT01.json --source-root "C:\caminho\SAST-COGNITIVE-LOAD-TEST-SECURITY\juice-shop" --auto-snippets
```

Confira no terminal se aparece `snippets=N/N`. Se todos os findings tiverem snippet, execute a geração real:

```powershell
python query.py --provider GPT --only GT01.json --source-root "C:\caminho\SAST-COGNITIVE-LOAD-TEST-SECURITY\juice-shop" --auto-snippets --execute
```

Troque o caminho pelo local em que você salvou o projeto.

**Opção B — copiar do GitHub e colar no terminal**

Execute o dry run:

```powershell
python query.py --provider GPT --only GT01.json --snippets-dir data/code_snippets
```

Quando solicitado, abra no GitHub o arquivo indicado pelo finding, copie o código correspondente e cole no terminal. Para encerrar cada trecho, digite `###` sozinho em uma nova linha. Repita para cada finding. Depois, execute novamente com `--execute` para chamar a LLM:

```powershell
python query.py --provider GPT --only GT01.json --snippets-dir data/code_snippets --execute
```

Substitua `GPT` por `Gemini`, `Kimi` ou `Claude` para usar outro provedor.

**Antes de executar todos os relatórios:** teste um relatório, confirme que a contagem mostra `snippets=N/N` e só então use:

```powershell
python query.py --provider Gemini --allreports --execute
```

Os resultados ficam em `results/`. Essa branch gera casos de teste; não executa os testes na aplicação.

## 6. Solução de problemas de API

### Kimi: erro de temperatura (HTTP 400)

O modelo configurado como `kimi-k3.1-pro` pode rejeitar temperaturas diferentes de `1`. Na função `_generate_kimi`, em `backend/openai_service.py`, a chamada deve usar:

```python
temperature=1,
```

Se aparecer `invalid temperature: only 1 is allowed for this model`, confira a chamada real no arquivo local e confirme que não existe outra configuração de temperatura sendo aplicada ao Kimi. Depois de atualizar o código, rode novamente um relatório individual antes de processar o lote.

### Kimi: limite de requisições (HTTP 429)

A API pode limitar a quantidade de requisições por minuto por organização. Um erro como `organization max RPM: 3` indica que o limite foi atingido; não é um erro de leitura do relatório SAST. Aguarde o intervalo indicado pela API antes de repetir a chamada. Em lotes, execute poucos relatórios por vez e evite reiniciar repetidamente o processo, pois isso pode gerar novas chamadas e atingir o limite novamente.

### Como interpretar erros

- `*_ERROR.txt`: contém o provedor, o modelo e a mensagem da falha para aquele relatório.
- `KeyboardInterrupt`: indica que a execução foi interrompida pelo usuário (por exemplo, com Ctrl+C); não identifica, por si só, a causa inicial.
- `--simulate`: valida os JSONs localmente, mas não testa credenciais, disponibilidade do modelo, limites de uso ou geração real.

## 7. Testes e validação do experimento

Há três tipos de execução que têm objetivos diferentes: **pytest**, **dry run** e **execução real**.

### Pytest — testes automatizados do código

O `pytest` é uma ferramenta de testes para Python. Ele executa os testes automatizados existentes no repositório para verificar comportamentos específicos do código, como funções de leitura ou validação, quando esses comportamentos têm testes implementados.

Na raiz do projeto, com o ambiente virtual ativado, execute:

```powershell
python -m pytest -q
```

Para ver o nome e o resultado de cada teste:

```powershell
python -m pytest -v
```

Se o Python informar que `pytest` não está instalado, instale-o com:

```powershell
python -m pip install pytest
```

**Importante:** o pytest só executa os testes que existem no projeto; ele não cria automaticamente testes para todo o código. Se aparecer uma mensagem como “no tests ran”, isso significa que nenhum teste foi descoberto nessa execução — não significa que o projeto passou nos testes. Se houver falhas, analise a mensagem para identificar qual teste falhou.

### Dry run — validar o fluxo sem chamar a LLM

O dry run verifica etapas locais da preparação, conforme os recursos de cada branch: por exemplo, a leitura dos relatórios, a validação do JSON e, nas branches com RAG/código, a preparação ou recuperação de contexto e snippets.

Use o comando de validação documentado na seção da branch em que estiver trabalhando. Na `main` e na `branch-1-direct-llm`, por exemplo:

```powershell
python query.py --simulate
```

Na branch 3, confira também a contagem de snippets apresentada no terminal. O dry run **não comprova** que a chave de API está correta, que o modelo está disponível ou que a chamada real será bem-sucedida.

### Execução real — chamar a LLM

A execução real envia os dados à API do provedor selecionado e pode consumir créditos ou cota de API. Use o comando específico da branch e comece com um relatório pequeno antes de executar um lote. Depois, confirme no terminal e em `results/` se os resultados foram gerados; verifique também os arquivos `*_ERROR.txt`, se existirem.

Em resumo:

| Método | O que verifica | Chama a API da LLM? |
|---|---|---|
| `pytest` | Os testes automatizados implementados no repositório | Em geral, não; confira o que os testes fazem |
| Dry run | Etapas locais de validação e preparação previstas pela branch | Não, nos modos de dry run descritos neste README |
| Execução real | A geração dos casos de teste pelo provedor escolhido | Sim; pode consumir créditos/cota |

Nenhum desses métodos, isoladamente, garante que os casos de teste gerados sejam corretos ou seguros. Revise os resultados antes de utilizá-los.

Antes de comparar resultados entre estratégias, registre a branch e o commit:

```powershell
git branch --show-current
git rev-parse HEAD
```

Registre também o relatório, finding, provedor/modelo, modo (dry run ou geração real), versão do código-fonte e resumo final. Não registre chaves de API.

