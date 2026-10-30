# Notas metodológicas para revisão

1. **Referência comum:** manter GT01–GT08 idênticos nas três condições, conforme o desenho de medidas repetidas do artigo.
2. **Cobertura dos modelos:** os ZIPs recebidos têm 8 resultados GPT-5.5 por condição. Não considerar Gemini, Claude ou Kimi concluídos sem os arquivos correspondentes.
3. **Branch 3 — contexto de código:** validar a correspondência entre cada snippet e o arquivo/linha apontado pelo alerta. Os snippets Java genéricos encontrados não parecem corresponder aos alertas TypeScript do OWASP Juice Shop.
4. **Rastreabilidade:** registrar modelo e versão, parâmetros, prompt, documentos recuperados, snippet usado, data de execução e falhas de API.
5. **Avaliação:** considerar correção técnica, reprodutibilidade prática, completude estrutural, clareza procedimental, alinhamento WSTG e ajustes manuais, como no artigo.
6. **Limite desta revisão:** não foram feitas chamadas novas a APIs de LLM nem inventados resultados.
