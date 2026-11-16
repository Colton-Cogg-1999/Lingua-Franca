"""Publish a completed JSONL ledger to a Kafka-compatible broker.

At-least-once across reruns: consumers must deduplicate event_id. This is an
archive ingestion adapter, not a distributed simulation coordinator.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--brokers', default='localhost:19092')
    parser.add_argument('--topic', default='galapagos.events.v1')
    args = parser.parse_args()
    try:
        from confluent_kafka import Producer
    except ImportError:
        parser.error('install the ledger extra first: pip install -e ".[ledger]"')
    producer = Producer({'bootstrap.servers': args.brokers, 'enable.idempotence': True,
                         'delivery.timeout.ms': 30000})
    errors = []
    def delivered(error, message):
        if error:
            errors.append(str(error))
    with args.ledger.open() as source:
        for line in source:
            event = json.loads(line)
            # Whole-run key preserves the local simulator's total sequence order.
            while True:
                try:
                    producer.produce(args.topic, key=event['run_id'], value=line, callback=delivered)
                    break
                except BufferError:
                    producer.poll(0.1)
            producer.poll(0)
            if errors:
                raise RuntimeError(errors[0])
    remaining = producer.flush(35)
    if remaining or errors:
        raise RuntimeError(f'undelivered={remaining}, delivery errors={errors[:3]}')
    print('Ledger delivered; repeated imports retain the same event IDs for deduplication.')


if __name__ == '__main__':
    main()
