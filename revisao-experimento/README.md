# Revisão do experimento SAST + LLM

Esta branch foi criada separadamente a partir de `main` para reunir a documentação de revisão sem alterar `main` nem as três branches experimentais existentes.

## Referência metodológica

O artigo compara oito alertas SAST em três condições:

1. `branch-1-direct-llm`: alerta SAST sem contexto recuperado.
2. `branch-2-rag-cwe-wstg`: alerta enriquecido com documentação CWE/WSTG via RAG.
3. `branch-3-rag-code-context`: alerta enriquecido com CWE/WSTG e trecho de código local.

A comparação deve usar os mesmos alertas GT01–GT08 em todas as condições, para que a variável observada seja o contexto fornecido ao LLM.

## Situação dos artefatos revisados

- Foram recebidos oito relatórios SAST GT01–GT08 por condição; os hashes dos oito arquivos conferem entre as três cópias examinadas.
- Os snapshots recebidos contêm oito resultados GPT-5.5 por condição: 24 resultados no total.
- Não foram identificados resultados completos de Gemini, Claude ou Kimi nos três ZIPs examinados.
- A validação sintática dos JSONs de relatório e resultados foi executada; o inventário está em `audit/manifest.json`.

## Questão metodológica prioritária

Os snippets incluídos na Branch 3 são arquivos Java genéricos, enquanto os alertas GT examinados referenciam arquivos TypeScript do OWASP Juice Shop. É necessário confirmar que cada alerta recebe o trecho real e correspondente ao arquivo/linha vulnerável. Caso contrário, a condição 3 não representa adequadamente o experimento descrito no artigo.

## Próximo passo

O pacote de revisão completo — incluindo os oito alertas e os 24 resultados GPT-5.5 — foi preparado como arquivo ZIP separado. Ele ainda precisa ser adicionado a esta branch como arquivos individuais para que todos os artefatos fiquem navegáveis no GitHub. Nenhuma saída nova de LLM foi gerada nesta revisão.

## Proteção do original

Esta branch parte de `main`. Nenhum commit foi feito em `main`, nenhuma branch existente foi sobrescrita e nenhuma pull request foi aberta.
