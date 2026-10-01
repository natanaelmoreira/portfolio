"""Pipeline demonstrativo, local e reproduzível; somente biblioteca padrão."""
import argparse
import csv
import hashlib
import json
import sqlite3
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'event_id', 'updated_at', 'order_date', 'customer_id', 'channel', 'amount_cents', 'status'}


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS batches (
            sha256 TEXT PRIMARY KEY, source_name TEXT NOT NULL,
            received_rows INTEGER NOT NULL, rejected_rows INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS bronze (
            batch_id TEXT NOT NULL, line_number INTEGER NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(batch_id, line_number));
        CREATE TABLE IF NOT EXISTS quarantine (
            batch_id TEXT NOT NULL, line_number INTEGER NOT NULL,
            reason TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(batch_id, line_number));
        CREATE TABLE IF NOT EXISTS silver_orders (
            event_id TEXT PRIMARY KEY, updated_at TEXT NOT NULL,
            order_date TEXT NOT NULL, customer_id TEXT NOT NULL,
            channel TEXT NOT NULL, amount_cents INTEGER NOT NULL,
            status TEXT NOT NULL, batch_id TEXT NOT NULL);
    ''')
    conn.executescript((ROOT / 'sql/gold.sql').read_text(encoding='utf-8'))
    return conn


def validate(row):
    if set(row) != FIELDS or any(value is None for value in row.values()):
        raise ValueError('colunas ou valores ausentes/excedentes')
    result = {key: value.strip() for key, value in row.items()}
    if not result['event_id'] or not result['customer_id']:
        raise ValueError('identificador vazio')
    for key in ('updated_at', 'order_date'):
        value = date.fromisoformat(result[key])
        if value.isoformat() != result[key]:
            raise ValueError('data deve usar YYYY-MM-DD')
    if result['updated_at'] < result['order_date']:
        raise ValueError('atualização anterior ao pedido')
    result['channel'] = result['channel'].lower()
    result['status'] = result['status'].lower()
    if result['channel'] not in {'organic', 'paid', 'referral'}:
        raise ValueError('canal inválido')
    if result['status'] not in {'paid', 'cancelled'}:
        raise ValueError('status inválido')
    result['amount_cents'] = int(result['amount_cents'])
    if result['amount_cents'] < 0:
        raise ValueError('valor negativo')
    return result


def run(source, database):
    start = time.monotonic()
    source = Path(source)
    raw = source.read_bytes()
    batch = hashlib.sha256(raw).hexdigest()
    conn = connect(database)
    try:
        if conn.execute('SELECT 1 FROM batches WHERE sha256=?', (batch,)).fetchone():
            return {'status': 'skipped', 'batch_id': batch}
        reader = csv.DictReader(raw.decode('utf-8-sig').splitlines())
        if len(reader.fieldnames or []) != len(FIELDS) or set(reader.fieldnames or []) != FIELDS:
            raise ValueError('cabeçalho incompatível com o contrato')
        received = rejected = changed = stale = 0
        with conn:
            for line, row in enumerate(reader, start=2):
                received += 1
                payload = json.dumps(row, ensure_ascii=False)
                conn.execute('INSERT INTO bronze VALUES (?, ?, ?)', (batch, line, payload))
                try:
                    item = validate(row)
                    previous = conn.execute(
                        'SELECT updated_at, order_date, customer_id, channel, amount_cents, status '
                        'FROM silver_orders WHERE event_id=?', (item['event_id'],)).fetchone()
                    current = tuple(item[key] for key in
                                    ('updated_at', 'order_date', 'customer_id', 'channel', 'amount_cents', 'status'))
                    if previous and previous[0] == current[0] and previous != current:
                        raise ValueError('versões conflitantes na mesma data; exige resolução na origem')
                except (ValueError, TypeError) as exc:
                    rejected += 1
                    conn.execute('INSERT INTO quarantine VALUES (?, ?, ?, ?)',
                                 (batch, line, str(exc), payload))
                    continue
                cursor = conn.execute('''
                    INSERT INTO silver_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        updated_at=excluded.updated_at, order_date=excluded.order_date,
                        customer_id=excluded.customer_id, channel=excluded.channel,
                        amount_cents=excluded.amount_cents, status=excluded.status,
                        batch_id=excluded.batch_id
                    WHERE excluded.updated_at > silver_orders.updated_at
                ''', (item['event_id'], *current, batch))
                changed += cursor.rowcount
                stale += 1 - cursor.rowcount
            duration = round((time.monotonic() - start) * 1000)
            conn.execute('INSERT INTO batches VALUES (?, ?, ?, ?, ?)',
                         (batch, source.name, received, rejected, duration))
        return {'status': 'success', 'batch_id': batch, 'received': received,
                'rejected': rejected, 'changed': changed, 'unchanged_or_stale': stale,
                'duration_ms': duration}
    finally:
        conn.close()


def export(database, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    conn = connect(database)
    try:
        for view in ('gold_channel_daily', 'gold_customer_summary'):
            cursor = conn.execute(f'SELECT * FROM {view} ORDER BY 1, 2')
            with (output / f'{view}.csv').open('w', newline='', encoding='utf-8') as target:
                writer = csv.writer(target)
                writer.writerow([column[0] for column in cursor.description])
                writer.writerows(cursor)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--db', type=Path, default=ROOT / 'build/warehouse.db')
    parser.add_argument('--export', type=Path, default=ROOT / 'build/gold')
    args = parser.parse_args()
    result = run(args.input, args.db)
    export(args.db, args.export)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
