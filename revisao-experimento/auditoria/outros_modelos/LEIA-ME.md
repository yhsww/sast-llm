# Status dos outros provedores — evidência disponível

Este arquivo registra o que foi possível confirmar pelos logs de terminal fornecidos. **Não transforma logs em resultados nem cria JSONs artificiais.**

## Resultados reais incluídos nesta revisão

- GPT-5.5: 8 JSONs por estratégia, total de 24 resultados.

## Outros provedores

- **Gemini**: logs/listagens locais indicam resultados existentes em GT01 e GT03 da estratégia Direct, GT01–GT08 da estratégia RAG CWE/WSTG, e GT01–GT02 da estratégia RAG com contexto de código. Também há erros registrados para parte dos casos. Os JSONs de Gemini não foram disponibilizados nos arquivos recebidos aqui, portanto seus conteúdos não puderam ser incluídos nem validados.
- **Kimi**: há registro de falha de execução para GT01–GT08 na estratégia Direct. A execução `--branch all` sem `--execute` era apenas simulação e não conta como resultado real.
- **Claude**: há registro de falha de execução para GT01–GT08 na estratégia Direct. Não foram fornecidos JSONs reais de resultado.
- Para Kimi/Claude nas estratégias 2 e 3, os logs disponíveis não comprovam resultados live completos.

## Como completar

Copiar do computador onde o experimento foi executado as pastas `results/branch-1-direct-llm/Gemini`, `results/branch-2-rag-cwe-wstg/Gemini`, `results/branch-3-rag-code-context/Gemini`, e as pastas equivalentes de Kimi e Claude que tenham sido executadas. Incluir arquivos `GT##_LLM.json` e, para auditoria, `GT##_ERROR.txt`. Sem os arquivos reais, não reconstruir nem inventar resultados.

A matriz `matriz_status_resultados.csv` diferencia os arquivos presentes neste pacote dos itens observados apenas nos logs.