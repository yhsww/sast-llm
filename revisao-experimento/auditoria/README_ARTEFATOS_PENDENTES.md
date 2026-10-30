# Artefatos de outras LLMs — estado e próximos passos

A pasta de revisão contém as evidências textuais disponíveis e o status por caso. Ela ainda não contém os JSONs reais de Gemini, Kimi e Claude.

## Por que os resultados brutos não foram adicionados

Os arquivos disponíveis nesta sessão foram ZIPs de branches que continham apenas os resultados GPT-5.5. As saídas de outras LLMs apareceram apenas em trechos de logs colados durante a conversa; os arquivos locais originais não foram incluídos.

## Próxima etapa para Rubens

1. Revisar [o ponto de controle](./PONTO_DE_CONTROLE_PARA_RUBENS.md).
2. Consultar [as evidências de execução](./evidencias_execucao_modelos.md) e [a matriz de status](./matriz_status_resultados.csv).
3. Para avaliar as respostas reais, receber de quem executou o experimento um ZIP com as pastas `results/branch-*/Gemini`, `results/branch-*/Claude` e `results/branch-*/Kimi` que existirem, incluindo `GT##_LLM.json` e `GT##_ERROR.txt`.
4. Não incluir `.env`, tokens ou valores de chaves.

Não foram inventados JSONs nem executadas novas chamadas a APIs como parte desta organização.
