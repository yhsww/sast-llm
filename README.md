# SAST-LLM — Experimentos com LLMs

Este repositório contém três experimentos para geração de casos de teste de segurança a partir de relatórios do SonarQube:

- **Branch 1 — Direct LLM:** achado SAST enviado diretamente à LLM.
- **Branch 2 — RAG CWE/WSTG:** achado SAST enriquecido com referências CWE e OWASP WSTG.
- **Branch 3 — RAG + Code Context:** achado SAST, referências recuperadas por RAG e trecho real do código-fonte relacionado ao finding.

Os comandos abaixo são para PowerShell no Windows. Execute-os na raiz do repositório.

---

## 1. Preparar o ambiente

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure as chaves no arquivo `.env`, usando `.env.example` como referência. Nunca publique esse arquivo nem compartilhe suas chaves. Antes de chamar uma LLM, confirme que a conta do provedor tem créditos/cota disponíveis.

---

## 2. Branch 3 — RAG + código-fonte: passo a passo

### 2.1. Como o experimento funciona

Para cada finding do relatório SonarQube, a branch 3:

1. Lê regra, severidade, mensagem, arquivo e linha.
2. Consulta a base vetorial usando regra, mensagem e tags do finding para recuperar referências CWE/WSTG.
3. Associa o trecho de código fornecido para aquele finding.
4. Envia à LLM o finding, o trecho de código e os documentos recuperados.

**O trecho de código não é usado na consulta do RAG.** A recuperação é feita pelos metadados do finding; o código é acrescentado depois como contexto para a LLM.

Não é necessário que outro pesquisador clone, instale ou execute o Juice Shop. Ele pode abrir o repositório do projeto avaliado, copiar o trecho correspondente e colá-lo no terminal do experimento.

### 2.2. Encontrar e copiar o código real

Projeto usado como referência:

- Repositório: https://github.com/ASTRID-RESEARCH/SAST-COGNITIVE-LOAD-TEST-SECURITY
- Código do Juice Shop: diretório `juice-shop/`.

Use sempre a mesma versão/commit do código que foi analisada pelo SonarQube, para que arquivo e linha correspondam ao relatório.

**Exemplo para `GT01.json`:**

O relatório aponta:

- `component`: `juice-shop:routes/b2bOrder.ts`
- `line`: `23`

Abra o arquivo correspondente no GitHub:

https://github.com/ASTRID-RESEARCH/SAST-COGNITIVE-LOAD-TEST-SECURITY/blob/main/juice-shop/routes/b2bOrder.ts

Localize a linha indicada e copie um bloco de código real, incluindo linhas anteriores e posteriores suficientes para entender o fluxo. Não copie somente a linha isolada se ela perder o contexto. Não invente nem reescreva o código.

Para `GT02.json`, `GT03.json` e os demais, repita usando o `component` e a linha registrados em cada finding. Cada finding pode apontar para outro arquivo.

### 2.3. Iniciar a captura manual no terminal

Com o ambiente virtual ativado, execute **sem** `--auto-snippets` e **sem** `--execute`:

```powershell
python query.py --provider Gemini --only GT01.json --snippets-dir data/code_snippets
```

O programa exibirá o finding e solicitará o código. Exemplo:

```text
[SNIPPETS] GT01.json: informe o código para cada finding.
Finding 1/1
Rule: typescript:S1523
Message: Make sure that this dynamic injection or execution of code is safe.
Component: juice-shop:routes/b2bOrder.ts
Line: 23
Cole o snippet abaixo (terminador ###):
```

Cole diretamente o trecho copiado do GitHub/arquivo local no terminal. Depois do código, pressione Enter e digite `###` sozinho em uma linha:

```text
###
```

Esse terminador informa ao programa que o trecho daquele finding terminou. Não coloque `###` dentro do código. O programa repetirá a solicitação para cada finding do relatório.

Para pular um finding, deixe a entrada vazia e digite `###`; ele será processado sem código. Para o cenário S3, evite pular findings.

### 2.4. Conferir se os snippets foram carregados

O comando anterior é um **dry run**: prepara os contextos, mas não chama a API de geração.

Confira a linha `[RAG]`, por exemplo:

```text
[RAG] GT01.json: findings=1, snippets=1/1, docs=...
```

Para um relatório com um finding, o esperado é `snippets=1/1`. Para três findings, o esperado é `snippets=3/3`.

- `snippets=0/1`: nenhum código foi recebido.
- `snippets=2/3`: um dos três findings ficou sem código.
- `snippets=N/N`: todos os findings receberam um trecho.

**Não execute a LLM enquanto a contagem não estiver completa.** A quantidade `docs=...` é o total de documentos RAG recuperados para os findings.

### 2.5. Executar a geração com uma LLM

Depois de confirmar a contagem, execute novamente com `--execute`. A captura é interativa novamente, então cole os trechos e finalize cada um com `###`:

```powershell
python query.py --provider Gemini --only GT01.json --snippets-dir data/code_snippets --execute
```

Para usar outro provedor, altere `--provider` para `GPT`, `Kimi` ou `Claude`. Exemplo:

```powershell
python query.py --provider Kimi --only GT01.json --snippets-dir data/code_snippets --execute
```

Os resultados são gravados por provedor:

- GPT: `results/GPT5.5/GT01_LLM.json`
- Gemini: `results/Gemini/GT01_LLM.json`
- Kimi: `results/Kimi/GT01_LLM.json`
- Claude: `results/Claude/GT01_LLM.json`

Resultados existentes são preservados por padrão. Use `--force` somente quando desejar sobrescrever o arquivo de resultado existente.

### 2.6. Processar vários relatórios

Dry run para todos os relatórios:

```powershell
python query.py --provider Gemini --allreports
```

Geração real para todos:

```powershell
python query.py --provider Gemini --allreports --execute
```

O modo interativo pedirá os snippets para cada finding de cada relatório. Para executar apenas outro relatório, por exemplo:

```powershell
python query.py --provider Gemini --only GT02.json
```

### 2.7. Alternativa: deixar os snippets salvos em JSON

A captura interativa não salva automaticamente o que foi colado. Para reutilizar trechos sem colá-los toda vez, crie um JSON por relatório em `data/code_snippets/`. O nome deve ser igual ao relatório:

```text
data/
  code_snippets/
    GT01.json
    GT02.json
```

O conteúdo pode ser uma lista de strings na mesma ordem de `issues` no relatório SAST:

```json
[
  "TRECHO REAL DO CÓDIGO DO PRIMEIRO FINDING",
  "TRECHO REAL DO CÓDIGO DO SEGUNDO FINDING"
]
```

Também é aceito o objeto com a propriedade `code_snippets`:

```json
{
  "code_snippets": [
    "TRECHO REAL DO CÓDIGO DO PRIMEIRO FINDING",
    "TRECHO REAL DO CÓDIGO DO SEGUNDO FINDING"
  ]
}
```

A posição de cada item corresponde à posição do finding em `issues`. Não altere a ordem. Use `null` ou string vazia somente quando realmente não houver snippet.

Carregar JSON em dry run:

```powershell
python query.py --provider Gemini --only GT01.json --snippets-dir data/code_snippets --auto-snippets
```

Executar usando o JSON:

```powershell
python query.py --provider Gemini --only GT01.json --snippets-dir data/code_snippets --auto-snippets --execute
```

### 2.8. Alternativa: extrair do código-fonte local

Se o projeto avaliado já estiver no computador, é possível informar a pasta raiz do código:

```powershell
python query.py --provider Gemini --only GT01.json --source-root "C:\caminho\para\SAST-COGNITIVE-LOAD-TEST-SECURITY\juice-shop" --auto-snippets
```

Para gerar resultados:

```powershell
python query.py --provider Gemini --only GT01.json --source-root "C:\caminho\para\SAST-COGNITIVE-LOAD-TEST-SECURITY\juice-shop" --auto-snippets --execute
```

A extração tenta localizar o caminho do componente e usa o nome do arquivo como alternativa. Sempre confira `snippets=N/N`, pois uma correspondência não encontrada deixa o finding sem contexto de código.

---

## 3. Comandos úteis

Ver as opções da branch 3:

```powershell
python query.py --help
```

Um relatório específico em dry run, com entrada manual:

```powershell
python query.py --provider Gemini --only GT01.json
```

Um relatório específico com geração real:

```powershell
python query.py --provider Gemini --only GT01.json --execute
```

Todos os relatórios com todos os provedores:

```powershell
python query.py --provider all --allreports --execute
```

`--execute` chama as APIs dos provedores e pode consumir créditos/cota. Faça primeiro o dry run e valide os snippets.

---

## 4. Comparação dos experimentos

| Experimento | Contexto fornecido à LLM |
|---|---|
| S1 — Direct LLM | Achado do SonarQube |
| S2 — RAG CWE/WSTG | Achado do SonarQube + documentos CWE/WSTG recuperados |
| S3 — RAG + Code Context | Achado do SonarQube + documentos CWE/WSTG recuperados + trecho real do código-fonte |

Para uma comparação consistente, use o mesmo relatório/finding, a mesma versão do código e os mesmos parâmetros sempre que possível. Registre no S3 o arquivo e o intervalo de linhas fornecido à LLM.

---

## 5. Solução de problemas

- **`snippets=0/N`:** no modo manual, verifique se colou o código e encerrou com `###` em uma linha isolada. No modo automático, confira nome e formato do JSON.
- **`docs=0`:** confira se a base de conhecimento foi ingerida e se o ChromaDB está acessível.
- **Erro 401/403:** confira a chave, as permissões e o modelo habilitado na conta.
- **Erro 429, saldo insuficiente ou quota:** o provedor recusou a chamada por limite ou saldo. Isso não significa que o snippet falhou; regularize a conta antes de repetir.
- **Resultado já existente:** por padrão o arquivo existente é preservado. Use `--force` somente se desejar sobrescrevê-lo.
- **Linha incompatível:** confirme que o arquivo é da mesma versão/commit que passou pela análise SonarQube.

Não coloque chaves de API, tokens ou dados sensíveis nos snippets ou relatórios versionados.

---

## 6. Referências

- Repositório do projeto avaliado: https://github.com/ASTRID-RESEARCH/SAST-COGNITIVE-LOAD-TEST-SECURITY
- Arquivo usado como exemplo para `GT01.json`: https://github.com/ASTRID-RESEARCH/SAST-COGNITIVE-LOAD-TEST-SECURITY/blob/main/juice-shop/routes/b2bOrder.ts
