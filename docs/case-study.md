# Revenue Data Pipeline

## Problema de negócio

Uma operação de vendas recebe pedidos em arquivos periódicos. Reenvios, correções e cancelamentos podem duplicar receita ou manter indicadores desatualizados. O objetivo é disponibilizar uma base confiável para comparar canais e acompanhar compras por cliente.

## Entrega

Um pipeline batch que preserva os registros recebidos, valida um contrato explícito, aplica atualizações e produz duas visões: receita diária por canal e resumo de compras por cliente. A fixture inclui falhas e atualizações de propósito para demonstrar o comportamento.

## Decisões e contrapartidas

| Decisão | Motivo | Limite |
| --- | --- | --- |
| SQLite e biblioteca padrão | Facilitar a reprodução sem serviços pagos | Não demonstra processamento distribuído |
| Valores em centavos inteiros | Evitar aproximações na soma de moeda | Exige conversão para exibição em reais |
| Identidade de lote por hash dos bytes | Impedir repetição do mesmo arquivo | Mudanças de formatação criam outro lote; a chave do pedido evita duplicação na Silver |
| Última versão por `updated_at` | Aceitar correções e ignorar versões atrasadas | Resolução diária, não adequada a múltiplas mudanças no mesmo dia |
| Quarentena de conflito na mesma versão | Não sobrescrever silenciosamente um valor divergente | A primeira versão permanece até resolução na origem |
| Gold como views | Refletir atualizações sem refresh manual | Custo de consulta cresce com o volume |
| Transação por lote | Evitar lote parcialmente aplicado no banco | Exportação dos CSVs é uma etapa posterior |

## Leitura dos resultados

Depois dos dois lotes, a receita paga é R$ 710,00. O canal pago soma R$ 250,00, o orgânico R$ 190,00 e indicação R$ 270,00. São apenas resultados dos dados fictícios do teste, não ganhos empresariais.

Não se calcula ROI ou CAC: o conjunto não possui investimento em mídia nem atribuição de aquisição. Recorrência é observada por contagem de pedidos; não se infere churn sem janela temporal e definição de cliente ativo.

## Como avaliar tecnicamente

1. Execute os dois lotes e confira os indicadores no README.
2. Reexecute um lote: o hash deve impedir nova ingestão.
3. Leia a quarentena: há valor negativo e data impossível.
4. Consulte o pedido `o004`: a versão antiga não desfaz a correção para 9000 centavos.
5. Execute os testes para verificar cancelamento, conflito de versão e reconciliação das duas views.

## Próximos experimentos

- Substituir a versão diária por timestamp UTC e sequência de origem.
- Gerar massa sintética maior e medir tempo, memória e planos de consulta.
- Criar dimensão de clientes com histórico quando existirem atributos que mudem.
- Comparar custo e latência antes de escolher processamento distribuído.
