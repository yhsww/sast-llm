# Evidências de execução disponíveis — Gemini, Claude e Kimi

Este documento organiza os trechos de terminal compartilhados durante a execução local. Não substitui os JSONs/arquivos de erro originais, que não estavam nos arquivos ZIP recebidos nesta conversa. Nenhuma chave de API é registrada aqui.

## Inventário local informado no terminal

| Estratégia | Provedor | JSONs | Erros | Observação |
|---|---|---:|---:|---|
| Direct LLM | Gemini | 2 | 3 | GT01 e GT03 foram indicados como JSON; erros em GT02, GT04 e GT05; GT06–GT08 sem artefato no inventário daquele momento |
| RAG CWE/WSTG | Gemini | 8 | 0 | Inventário posterior informou oito JSONs; trecho de uma execução anterior só mostra quatro saídas salvas e quatro falhas antes de possíveis tentativas posteriores |
| RAG + contexto de código | Gemini | 2 | 6 | GT01–GT02 JSONs; GT03–GT08 erros |
| Direct LLM | Kimi | 0 | 8 | GT01–GT08 com erros |
| RAG CWE/WSTG | Kimi | 0 | 0 | Nenhum resultado live confirmado nos registros disponíveis |
| RAG + contexto de código | Kimi | 0 | 0 | Nenhum resultado live confirmado nos registros disponíveis |
| Direct LLM | Claude | 0 | 0 | Os trechos encontrados mostram simulações sem chamadas de geração; teste posterior de autenticação da API não confirma geração dos GTs |
| RAG CWE/WSTG | Claude | 0 | 0 | Nenhum resultado live confirmado |
| RAG + contexto de código | Claude | 0 | 0 | Nenhum resultado live confirmado |

## Trechos de log — Gemini / branch 2

Um trecho da execução local informa:

- GT01: resultado salvo em `GT01_LLM.json`
- GT02: falha registrada em `GT02_ERROR.txt`
- GT03: resultado salvo em `GT03_LLM.json`
- GT04: falha registrada em `GT04_ERROR.txt`
- GT05: falha registrada em `GT05_ERROR.txt`
- GT06: resultado salvo em `GT06_LLM.json`
- GT07: falha registrada em `GT07_ERROR.txt`
- GT08: resultado salvo em `GT08_LLM.json`

Os arquivos de erro exibidos nesse log incluíam respostas de servidor `503 UNAVAILABLE` por alta demanda temporária do modelo. O inventário posterior reportado no PowerShell listou oito JSONs e zero erros nessa estratégia; por isso o estado final foi registrado conforme o inventário, preservando esta diferença histórica para revisão.

## Trechos de log — Gemini / branch 3

O log local mostra GT01 e GT02 salvos como JSON e falhas em GT03–GT08. Os erros exibidos incluíam `429 RESOURCE_EXHAUSTED` (limite/cota da API) e `ValueError: Gemini returned an empty response.`

## Trechos de log — Kimi

O inventário PowerShell reportado listou zero JSONs e oito arquivos de erro para a estratégia Direct, cobrindo GT01–GT08. Execuções sem a flag `--execute` foram explicitamente marcadas como simulação e não devem ser tratadas como resultados reais. Para as estratégias 2 e 3, os logs disponíveis não comprovam execução live completa.

## Trechos de log — Claude

Os logs mostram comandos de simulação para GT01–GT08 com mensagens como `simulation only; no generation API call`. Um log posterior registra a chave configurada e um teste de autenticação bem-sucedido; isso apenas comprova autenticação, não a geração dos relatórios. O inventário disponível lista zero JSONs e zero erros para Claude nas três estratégias.

## O que ainda falta para a revisão de conteúdo

Os JSONs e arquivos `GT##_ERROR.txt` originais de Gemini/Kimi/Claude não estavam nos ZIPs disponíveis para esta sessão. Assim, esta auditoria permite revisar o estado operacional e orientar o diagnóstico, mas Rubens ainda precisará dos arquivos reais para avaliar a qualidade técnica das respostas já produzidas.

**Não subir o arquivo `.env` ou qualquer chave de API para o repositório.**
