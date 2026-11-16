"""Read-committed ledger projection with SQLite-atomic event deduplication/offsets."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time


class Projection:
    def __init__(self, path):
        self.db=sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS seen(event_id TEXT PRIMARY KEY, payload_hash BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS offsets(topic TEXT, partition_id INTEGER, offset_id INTEGER, PRIMARY KEY(topic,partition_id));
        CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE IF NOT EXISTS boundaries(run_id TEXT, round_id INTEGER, topology TEXT, PRIMARY KEY(run_id,round_id));
        CREATE TABLE IF NOT EXISTS counts(run_id TEXT, round_id INTEGER, conversations INTEGER DEFAULT 0,
          first_success INTEGER DEFAULT 0, final_success INTEGER DEFAULT 0, migrations INTEGER DEFAULT 0,
          boundary_violations INTEGER DEFAULT 0, unverifiable INTEGER DEFAULT 0, PRIMARY KEY(run_id,round_id));
        CREATE TABLE IF NOT EXISTS summaries(run_id TEXT, round_id INTEGER, payload TEXT, PRIMARY KEY(run_id,round_id));
        ''')

    def ingest(self, records):
        """Records are (topic, partition, offset, raw event bytes)."""
        with self.db:
            for topic, partition, offset, raw in records:
                event=json.loads(raw)
                checksum=hashlib.sha256(raw).digest()
                inserted=self.db.execute('INSERT OR IGNORE INTO seen VALUES (?,?)',(event['event_id'],checksum)).rowcount
                if not inserted:
                    old=self.db.execute('SELECT payload_hash FROM seen WHERE event_id=?',(event['event_id'],)).fetchone()[0]
                    if old != checksum:
                        raise ValueError('same event ID has conflicting payloads')
                else:
                    self.apply(event)
                self.db.execute('INSERT INTO offsets VALUES (?,?,?) ON CONFLICT(topic,partition_id) DO UPDATE SET offset_id=max(offset_id,excluded.offset_id)',(topic,partition,offset))

    def apply(self,event):
        run,round_number=event['run_id'],event['round']
        kind=event['kind']
        if kind=='initialized':
            self.db.execute('INSERT OR REPLACE INTO runs VALUES (?,?)',(run,event.get('plan',{}).get('name',run)))
        if kind=='geography_changed':
            if event['checks']['expected'] != event['checks']['observed']:
                raise ValueError('ledger records failed boundary enforcement')
            self.db.execute('INSERT OR REPLACE INTO boundaries VALUES (?,?,?)',(run,round_number,json.dumps(event['topology'])))
        if kind in ('conversation','migration'):
            row=self.db.execute('SELECT topology FROM boundaries WHERE run_id=? AND round_id<=? ORDER BY round_id DESC LIMIT 1',(run,round_number)).fetchone()
            if kind=='conversation':
                origin,destination=event['source_island'],event['island']
            else:
                origin,destination=event['source'],event['destination']
            violation=int(row is not None and destination not in json.loads(row[0])[origin])
            self.db.execute('INSERT OR IGNORE INTO counts(run_id,round_id) VALUES (?,?)',(run,round_number))
            self.db.execute('''UPDATE counts SET conversations=conversations+?,first_success=first_success+?,
              final_success=final_success+?,migrations=migrations+?,boundary_violations=boundary_violations+?,unverifiable=unverifiable+?
              WHERE run_id=? AND round_id=?''',(int(kind=='conversation'),int(event.get('first_success',False)),
              int(event.get('final_success',False)),int(kind=='migration'),violation,int(row is None),run,round_number))
        if kind=='round_completed':
            summary={key:value for key,value in event['summary'].items() if key!='islands'}
            self.db.execute('INSERT OR REPLACE INTO summaries VALUES (?,?,?)',(run,round_number,json.dumps(summary)))

    def status(self):
        runs=[]
        for run,name in self.db.execute('SELECT run_id,name FROM runs ORDER BY name'):
            last=self.db.execute('SELECT max(round_id) FROM summaries WHERE run_id=?',(run,)).fetchone()[0]
            totals=self.db.execute('SELECT sum(conversations),sum(migrations),sum(boundary_violations),sum(unverifiable) FROM counts WHERE run_id=?',(run,)).fetchone()
            runs.append(dict(run_id=run,name=name,last_complete_round=last,conversations=totals[0] or 0,
                             migrations=totals[1] or 0,boundary_violations=totals[2] or 0,unverifiable=totals[3] or 0))
        return dict(updated_unix=time.time(),runs=runs)


def main():
    from confluent_kafka import Consumer, KafkaError, OFFSET_BEGINNING
    parser=argparse.ArgumentParser()
    parser.add_argument('--brokers',default='redpanda:9092')
    parser.add_argument('--topic',default='galapagos.evolution.v2')
    parser.add_argument('--database',type=Path,default=Path('/data/analytics/projection.sqlite'))
    args=parser.parse_args()
    args.database.parent.mkdir(parents=True,exist_ok=True)
    projection=Projection(args.database)
    consumer=Consumer({'bootstrap.servers':args.brokers,'group.id':'galapagos-research-analytics-v1',
                       'isolation.level':'read_committed','enable.auto.commit':False,'auto.offset.reset':'earliest'})
    def assigned(client,partitions):
        for partition in partitions:
            saved=projection.db.execute('SELECT offset_id FROM offsets WHERE topic=? AND partition_id=?',(partition.topic,partition.partition)).fetchone()
            partition.offset=saved[0]+1 if saved else OFFSET_BEGINNING
        client.assign(partitions)
    consumer.subscribe([args.topic],on_assign=assigned)
    last_report=0
    try:
        while True:
            records=[]
            for message in consumer.consume(num_messages=1000,timeout=1):
                if message.error():
                    raise RuntimeError(message.error())
                records.append((message.topic(),message.partition(),message.offset(),message.value()))
            if records:
                projection.ingest(records)
                consumer.commit(asynchronous=False)
            if time.monotonic()-last_report>5:
                status=projection.status()
                target=args.database.parent/'status.json'
                temporary=target.with_suffix('.pending')
                temporary.write_text(json.dumps(status,indent=2))
                temporary.replace(target)
                print(json.dumps(status),flush=True)
                last_report=time.monotonic()
    finally:
        consumer.close()
        projection.db.close()


if __name__=='__main__':
    main()
