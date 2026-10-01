-- Receita em centavos: evita erros de representação de moeda em ponto flutuante.
CREATE VIEW IF NOT EXISTS gold_channel_daily AS
SELECT order_date, channel,
       COUNT(*) AS orders,
       SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS paid_orders,
       SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
       SUM(CASE WHEN status = 'paid' THEN amount_cents ELSE 0 END) AS revenue_cents,
       ROUND(1.0 * SUM(CASE WHEN status = 'paid' THEN amount_cents ELSE 0 END)
             / NULLIF(SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END), 0), 2)
             AS average_paid_ticket_cents
FROM silver_orders
GROUP BY order_date, channel;

CREATE VIEW IF NOT EXISTS gold_customer_summary AS
SELECT customer_id,
       MIN(CASE WHEN status = 'paid' THEN order_date END) AS first_paid_order,
       MAX(CASE WHEN status = 'paid' THEN order_date END) AS last_paid_order,
       SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS paid_orders,
       SUM(CASE WHEN status = 'paid' THEN amount_cents ELSE 0 END) AS revenue_cents
FROM silver_orders
GROUP BY customer_id;
