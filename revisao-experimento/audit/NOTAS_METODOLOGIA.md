# Notas metodológicas para revisão

1. **Referência comum:** os relatórios GT01–GT08 estão disponíveis em cada uma das três branches experimentais. Os oito arquivos têm os mesmos hashes entre as branches.
2. **Resultados presentes:** cada condição tem oito arquivos de resultado GPT-5.5 (24 no total). Use os links do [guia de revisão](../README.md) para abrir cada pasta.
3. **Cobertura dos modelos:** esta entrega não comprova resultados completos para Gemini, Claude ou Kimi; não os considere concluídos sem os arquivos correspondentes.
4. **Branch 3 — contexto de código:** validar a correspondência entre cada snippet e o arquivo/linha apontado pelo alerta. Os snippets Java genéricos encontrados não parecem corresponder aos alertas TypeScript do OWASP Juice Shop.
5. **Rastreabilidade:** registrar modelo e versão, parâmetros, prompt, documentos recuperados, snippet usado, data de execução e falhas de API.
6. **Avaliação:** considerar correção técnica, reprodutibilidade prática, completude estrutural, clareza procedimental, alinhamento WSTG e ajustes manuais, como no artigo.
7. **Limite desta revisão:** não foram feitas chamadas novas a APIs de LLM nem inventados resultados.
