# Revisão do experimento SAST + LLM

Esta branch reúne o guia para revisão por pares. **Os relatórios e resultados já estão nas três branches experimentais existentes**; não foi necessário duplicar esses arquivos nesta branch. A branch `main` e as três branches experimentais não foram alteradas.

## Onde o Rubens deve olhar

| Condição | Branch | Relatórios SAST | Resultados GPT-5.5 |
|---|---|---|---|
| 1 — LLM direto | [branch-1-direct-llm](https://github.com/yhsww/sast-llm/tree/branch-1-direct-llm) | [GT01–GT08](https://github.com/yhsww/sast-llm/tree/branch-1-direct-llm/data/sast_reports) | [GPT5.5](https://github.com/yhsww/sast-llm/tree/branch-1-direct-llm/results/GPT5.5) |
| 2 — RAG com CWE/WSTG | [branch-2-rag-cwe-wstg](https://github.com/yhsww/sast-llm/tree/branch-2-rag-cwe-wstg) | [GT01–GT08](https://github.com/yhsww/sast-llm/tree/branch-2-rag-cwe-wstg/data/sast_reports) | [GPT5.5](https://github.com/yhsww/sast-llm/tree/branch-2-rag-cwe-wstg/results/GPT5.5) |
| 3 — RAG + contexto de código | [branch-3-rag-code-context](https://github.com/yhsww/sast-llm/tree/branch-3-rag-code-context) | [GT01–GT08](https://github.com/yhsww/sast-llm/tree/branch-3-rag-code-context/data/sast_reports) | [GPT5.5](https://github.com/yhsww/sast-llm/tree/branch-3-rag-code-context/results/GPT5.5) |

Cada uma das três branches foi conferida no GitHub e contém oito relatórios GT01–GT08 e oito resultados GPT-5.5, totalizando 24 resultados. Os oito relatórios SAST têm os mesmos hashes nas três branches.

## O que está sendo comparado

1. **LLM direto:** alerta SAST como contexto, sem RAG.
2. **RAG CWE/WSTG:** alerta SAST com documentação de segurança recuperada.
3. **RAG + código:** acrescenta contexto de código local ao RAG.

O desenho exige que os mesmos alertas sejam usados nas três condições; assim, a diferença principal é a estratégia de enriquecimento do contexto.

## Pontos para o revisor conferir

- Correção técnica e utilidade dos casos de teste gerados.
- Se os documentos recuperados em RAG são pertinentes e rastreáveis.
- Se os trechos de código da condição 3 correspondem ao alerta e ao arquivo vulnerável referenciado.
- Reprodutibilidade, completude e alinhamento com WSTG.
- Se há saídas ausentes de outros modelos.

## Limite dos resultados disponíveis

Os arquivos que foram revisados nesta entrega contêm resultados de **GPT-5.5**. Não trate Gemini, Claude ou Kimi como concluídos sem os resultados completos e verificáveis. Nenhuma nova chamada paga a modelos foi executada para preparar esta revisão.

## Auditoria leve

- [Notas metodológicas](audit/NOTAS_METODOLOGIA.md)
- [Manifesto/inventário](audit/manifest.json)

Esta branch contém apenas o guia e a auditoria leve. Os relatórios e resultados permanecem nas branches experimentais linkadas acima; não foram copiados nem sobrescritos.
