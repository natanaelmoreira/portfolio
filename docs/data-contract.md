# Contrato de dados — versão 1

Formato: CSV UTF-8, separador vírgula, cabeçalho obrigatório. Uma linha representa uma versão do estado de um pedido. Nesta demonstração `event_id` é a chave de negócio do pedido, não uma chave distinta para cada evento.

| Campo | Tipo | Regra |
| --- | --- | --- |
| event_id | texto | Obrigatório; identificador estável do pedido |
| updated_at | data | ISO `YYYY-MM-DD`; não anterior a `order_date` |
| order_date | data | Data válida em ISO `YYYY-MM-DD` |
| customer_id | texto | Obrigatório; identificador fictício do cliente |
| channel | categoria | `organic`, `paid` ou `referral`; normalizado para minúsculas |
| amount_cents | inteiro | Maior ou igual a zero; moeda única, BRL |
| status | categoria | `paid` ou `cancelled`; normalizado para minúsculas |

Espaços nas extremidades dos valores são removidos. Cabeçalho incompatível interrompe a ingestão antes de inserir linhas. Erros de linha são enviados à quarentena. Um registro com os mesmos identificador e versão, mas conteúdo divergente, também vai para quarentena. Duplicatas idênticas e versões antigas não alteram a Silver.

## Camadas e granularidade

- `batches`: uma linha por conteúdo de arquivo, com hash, nome e métricas.
- `bronze`: uma linha por registro CSV recebido, com payload JSON, lote e número sequencial. Preserva valores lidos, mas não os bytes originais nem a formatação exata do arquivo.
- `quarantine`: registros rejeitados e motivos; a origem também permanece na Bronze.
- `silver_orders`: uma linha por pedido, com a última versão aceita e referência ao lote.
- `gold_channel_daily`: uma linha por data do pedido e canal.
- `gold_customer_summary`: uma linha por cliente, incluindo clientes somente com cancelamentos.

Receita inclui somente `paid`. Ticket médio divide receita pelo número de pedidos pagos e retorna NULL sem pedidos pagos. Primeira e última compra consideram somente pedidos pagos. Cancelamento altera retrospectivamente os indicadores da data original; não representa um livro contábil de movimentações.
