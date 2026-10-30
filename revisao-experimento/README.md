# Pacote de revisão — SAST + LLM

Esta branch reúne cópias dos artefatos para facilitar a revisão, sem alterar `main` nem as branches experimentais.

## Relatórios SAST (ground truth)

Os oito relatórios GT01–GT08 estão em:
- [Relatórios SAST copiados para esta branch](./relatorios-sast/)

## Resultados GPT-5.5 por estratégia

- [Estratégia 1 — Direct LLM](./resultados/branch-1-direct-llm/GPT5.5/)
- [Estratégia 2 — RAG CWE/WSTG](./resultados/branch-2-rag-cwe-wstg/GPT5.5/)
- [Estratégia 3 — RAG com contexto de código](./resultados/branch-3-rag-code-context/GPT5.5/)

Cada estratégia tem os resultados GT01–GT08, totalizando 24 arquivos de resultado GPT-5.5. Os relatórios SAST GT01–GT08 são compartilhados entre as estratégias e foram copiados uma vez para evitar duplicação desnecessária.

## Referências às branches originais

- [Branch 1 — Direct LLM](https://github.com/yhsww/sast-llm/tree/branch-1-direct-llm)
- [Branch 2 — RAG CWE/WSTG](https://github.com/yhsww/sast-llm/tree/branch-2-rag-cwe-wstg)
- [Branch 3 — RAG Code Context](https://github.com/yhsww/sast-llm/tree/branch-3-rag-code-context)

## Escopo e observações

- Esta branch é uma cópia organizada para revisão; os arquivos originais continuam nas branches experimentais.
- O conteúdo copiado aqui inclui os relatórios SAST GT01–GT08 e os 24 resultados GPT-5.5.
- Não considerar outros provedores/modelos como completos sem verificar os respectivos arquivos e logs de execução.
- A correspondência dos snippets de código da estratégia 3 com os alertas do Juice Shop deve ser conferida durante a revisão.
- Nenhuma nova chamada paga a APIs de LLM foi feita nesta organização.

## Como revisar

1. Comece pelos relatórios SAST em `relatorios-sast/`.
2. Compare cada GT com os resultados correspondentes de cada estratégia.
3. Registre divergências, alertas não cobertos, falsos positivos e problemas de contexto.

## Auditoria dos demais provedores

- [Ponto de controle para Rubens — resultados parciais Gemini, Claude e Kimi](./auditoria/PONTO_DE_CONTROLE_PARA_RUBENS.md)
- [Status de Gemini, Kimi e Claude](./auditoria/outros_modelos/LEIA-ME.md)
- [Matriz resumida de status por estratégia e provedor](./auditoria/matriz_status_resultados.csv)
- [Notas metodológicas para revisão](./auditoria/NOTAS_METODOLOGIA.md)

A branch contém os relatórios SAST e os 24 JSONs GPT-5.5 disponíveis. Os resultados reais de Gemini, Kimi e Claude não foram incluídos porque os arquivos JSON/ERROR correspondentes não estavam entre os arquivos recebidos; os logs são registrados como evidência auxiliar, não como resultados.
