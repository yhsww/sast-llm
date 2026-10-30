# Ponto de controle para revisão — Gemini, Claude e Kimi

**Objetivo:** permitir que Rubens confira a configuração e os resultados já produzidos, indique correções e forneça/libere as credenciais necessárias para continuar as execuções.

## O que os logs locais registram até agora

| Estratégia | Gemini | Kimi | Claude |
|---|---|---|---|
| Branch 1 — Direct LLM | 2 JSONs, 3 erros e 3 casos sem arquivo | 0 JSONs e 8 erros | 0 JSONs; houve simulação, não execução real confirmada |
| Branch 2 — RAG CWE/WSTG | 8 JSONs, 0 erros no inventário local | 0 JSONs e 0 erros | 0 JSONs e 0 erros |
| Branch 3 — RAG com contexto de código | 2 JSONs e 6 erros | 0 JSONs e 0 erros | 0 JSONs e 0 erros |

O CSV adjacente contém o status caso a caso. Os estados são derivados dos logs e do inventário PowerShell colados na conversa, não de inspeção direta dos JSONs.

## Limitação importante para a revisão

Os ZIPs do repositório enviados para esta conversa contêm apenas os resultados GPT-5.5; os arquivos locais de Gemini, Kimi e Claude não vieram dentro deles. Portanto, os JSONs e arquivos `GT##_ERROR.txt` reais ainda **não foram publicados nesta branch**. Não foram reconstruídos nem inventados.

Para Rubens validar a qualidade das respostas, é necessário copiar do computador de execução os arquivos destas pastas:

- `results/branch-1-direct-llm/Gemini/`
- `results/branch-2-rag-cwe-wstg/Gemini/`
- `results/branch-3-rag-code-context/Gemini/`
- as pastas equivalentes de `Kimi/` e `Claude/`, quando existirem.

Incluir `GT##_LLM.json` e `GT##_ERROR.txt` (se houver). Pode enviar um ZIP apenas dessas pastas de resultados, sem incluir o arquivo `.env` nem qualquer chave de API.

## Pontos para Rubens decidir

1. Conferir se a estrutura dos relatórios gerados e os veredictos fazem sentido para os GTs.
2. Avaliar as falhas do Gemini, incluindo indisponibilidade 503 registrada em alguns casos.
3. Verificar por que a execução Direct do Kimi gerou oito erros e se a configuração/endpoint está correta.
4. Confirmar/liberar as credenciais necessárias e autorizar a continuação das execuções que faltam.
5. Validar a estratégia 3: os logs anteriores levantam uma possível divergência entre snippets Java e alertas do Juice Shop em TypeScript.

## Credenciais — não publicar segredos

Um log posterior registra a chave Claude configurada e um teste de autenticação bem-sucedido; isso não significa que os relatórios GT foram executados. Os logs também mostram chaves configuradas para Gemini e Kimi. Nunca colocar valores de chaves no GitHub; usar somente variáveis de ambiente no computador de execução.
