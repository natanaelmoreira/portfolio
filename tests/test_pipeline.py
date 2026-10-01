import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from src.pipeline import ROOT, run, export


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder / 'warehouse.db'

    def query(self, query):
        with sqlite3.connect(self.db) as conn:
            return conn.execute(query).fetchall()

    def initial(self):
        return run(ROOT / 'data/sample/orders_01.csv', self.db)

    def test_quality_and_lineage(self):
        result = self.initial()
        self.assertEqual((result['received'], result['rejected'], result['changed']), (7, 2, 4))
        self.assertEqual(self.query('SELECT COUNT(*) FROM bronze'), [(7,)])
        self.assertEqual(self.query('SELECT COUNT(*) FROM quarantine'), [(2,)])
        self.assertEqual(self.query('SELECT COUNT(*) FROM silver_orders s JOIN batches b ON s.batch_id=b.sha256'), [(4,)])

    def test_retry_is_idempotent(self):
        self.initial()
        self.assertEqual(self.initial()['status'], 'skipped')
        self.assertEqual(self.query('SELECT COUNT(*) FROM bronze'), [(7,)])
        self.assertEqual(self.query('SELECT COUNT(*) FROM batches'), [(1,)])

    def test_updates_cancellations_and_late_events(self):
        self.initial()
        result = run(ROOT / 'data/sample/orders_02.csv', self.db)
        self.assertEqual(result['unchanged_or_stale'], 1)
        self.assertEqual(self.query('SELECT SUM(revenue_cents), SUM(paid_orders), SUM(cancelled_orders) FROM gold_channel_daily'), [(71000, 5, 1)])
        self.assertEqual(self.query("SELECT amount_cents FROM silver_orders WHERE event_id='o004'"), [(9000,)])

    def test_reverse_batch_order_converges(self):
        run(ROOT / 'data/sample/orders_02.csv', self.db)
        self.initial()
        self.assertEqual(self.query('SELECT SUM(revenue_cents) FROM gold_customer_summary'), [(71000,)])

    def test_same_version_conflict_is_quarantined(self):
        self.initial()
        source = self.folder / 'conflict.csv'
        source.write_text('event_id,updated_at,order_date,customer_id,channel,amount_cents,status\n'
                          'o001,2026-09-01,2026-09-01,c001,organic,99999,paid\n', encoding='utf-8')
        self.assertEqual(run(source, self.db)['rejected'], 1)
        self.assertEqual(self.query("SELECT amount_cents FROM silver_orders WHERE event_id='o001'"), [(10000,)])

    def test_schema_failure_has_no_batch(self):
        source = self.folder / 'invalid.csv'
        source.write_text('id,value\n1,2\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            run(source, self.db)
        self.assertEqual(self.query('SELECT COUNT(*) FROM batches'), [(0,)])

    def test_exports_reconcile(self):
        self.initial()
        run(ROOT / 'data/sample/orders_02.csv', self.db)
        export(self.db, self.folder / 'gold')
        for table in ('gold_channel_daily', 'gold_customer_summary'):
            with (self.folder / 'gold' / f'{table}.csv').open(encoding='utf-8') as source:
                self.assertEqual(sum(int(row['revenue_cents']) for row in csv.DictReader(source)), 71000)


if __name__ == '__main__':
    unittest.main()
