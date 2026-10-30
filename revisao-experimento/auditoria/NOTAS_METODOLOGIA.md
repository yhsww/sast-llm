# Notas para revisão com Rubens

1. **Referência comum:** GT01–GT08 são idênticos por hash nas três condições. Manter uma referência comum é coerente com o desenho de medidas repetidas do artigo.
2. **Cobertura de provedores:** os ZIPs nomeados `com-4-ias` contêm somente os oito JSONs de GPT-5.5. Não marcar Gemini, Claude ou Kimi como concluídos com base nesses arquivos.
3. **Branch 3 — contexto de código:** verificar a origem dos snippets Java genéricos em relação aos alertas Juice Shop em TypeScript. Confirmar que o pipeline realmente recupera o arquivo e o trecho corretos para cada alerta.
4. **Reprodutibilidade:** registrar versão/modelo, parâmetros, prompt, documentos recuperados e falhas de API por execução. Não substituir silenciosamente saídas existentes.
5. **Avaliação:** avaliar correção técnica, reprodutibilidade prática, completude estrutural, clareza, alinhamento WSTG e ajustes manuais, conforme o artigo.
6. **Integridade do repositório:** este material foi organizado para revisão em uma branch separada. Não sobrescrever `main` nem as branches experimentais originais.