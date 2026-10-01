# Operação e evolução

## Execução local

Execute os comandos na raiz do repositório. Para isolar uma demonstração, informe outros destinos:

```bash
python -m src.pipeline --input data/sample/orders_01.csv --db build/demo.db --export build/demo-gold
```

O banco guarda checkpoints em `batches`. Um arquivo com o mesmo conteúdo é ignorado. Um novo arquivo pode atualizar pedidos se trouxer uma versão mais recente. O pipeline mantém uma transação de escrita por lote. Falhas de banco durante a ingestão desfazem a transação; falha na exportação não desfaz um lote já confirmado. Reexecute o comando para repetir a exportação a partir do banco.

## Diagnóstico

O JSON de execução informa linhas recebidas, rejeitadas, alteradas, sem alteração e duração. Examine o banco com um cliente SQLite:

```sql
SELECT source_name, received_rows, rejected_rows, duration_ms FROM batches;
SELECT reason, COUNT(*) AS occurrences FROM quarantine GROUP BY reason;
SELECT * FROM gold_channel_daily ORDER BY order_date, channel;
```

Essas métricas são observabilidade local, sem alertas externos. Os CSVs exportados podem ser importados em ferramentas de BI; não há dashboard incluído.

## Resolução de erros

- Cabeçalho inválido: corrigir a origem e executar novamente.
- Linha inválida: consultar o motivo em quarentena e produzir um arquivo corrigido.
- Conflito de versão: resolver na origem e enviar uma versão mais recente. Não alterar o banco manualmente como fluxo normal.
- Reprocessamento completo: usar um novo caminho de banco para manter o anterior disponível para comparação.

## Limitações conhecidas

- Uso local com um único escritor; sem coordenação de concorrência.
- Leitura do arquivo inteiro em memória; não adequado a volumes arbitrários.
- Sem API externa, streaming, exclusão física de pedidos ou migração automática de schema.
- Versões com resolução diária. Conflitos empatados exigem resolução; a convergência independente de ordem vale para versões com datas distintas.
- Bronze preserva os campos extraídos do CSV, não um arquivo bruto imutável.
- Views e CSVs representam o estado atual. Não há snapshots históricos de fechamento.
- CSVs não são publicados atomicamente como um conjunto; leitores simultâneos exigiriam manifestos/versionamento.
- A massa de exemplo é pequena; nenhum benchmark de escala ou garantia de produção é alegado.

## Caminho proposto para Azure/Databricks

Esta tabela é um plano de evolução, não infraestrutura implantada.

| Componente local | Evolução possível | Validação necessária |
| --- | --- | --- |
| CSV e Bronze SQLite | Arquivos brutos em ADLS com partições e manifesto | Permissões, retenção e integridade |
| Validação Python | Job Spark com contrato versionado | Paridade das regras e custo operacional |
| Upsert SQLite | Tabela Delta com merge determinístico | Unicidade por chave e ordenação de eventos |
| Views Gold | Tabelas/modelos analíticos materializados | Reconciliação e tratamento de dados atrasados |
| Comando manual | Orquestração com tentativas e dependências | Idempotência, alertas e recuperação |
| CSVs analíticos | Camada semântica e Power BI | Definição das métricas e atualização |

## Privacidade

As amostras contêm apenas identificadores inventados. Não colocar credenciais, dados pessoais ou bases corporativas neste repositório público. Arquivos `.env`, bancos locais e saídas de execução estão ignorados pelo Git.
