"""Stateless island worker HTTP service for trusted local research deployments."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import hashlib
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import game as model
from .game import VERSION, digest, island_task

MAX_REQUEST = 32 * 1024 * 1024

def fingerprint():
    return hashlib.sha256(Path(model.__file__).read_bytes()).hexdigest()


class RemoteWorkers:
    def __init__(self, urls, timeout=30, retries=2):
        self.urls = list(urls)
        self.timeout = timeout
        self.retries = retries

    def execute(self, task):
        url = self.urls[task['island'] % len(self.urls)].rstrip('/') + '/step'
        request_hash = digest(task)
        payload = json.dumps(dict(task=task, task_hash=request_hash, model=VERSION, source_hash=fingerprint())).encode()
        for attempt in range(self.retries + 1):
            try:
                with urlopen(Request(url, payload, {'Content-Type': 'application/json'}), timeout=self.timeout) as response:
                    reply = json.load(response)
                if reply['task_hash'] != request_hash or reply['result_hash'] != digest(reply['result']):
                    raise ValueError('worker response integrity mismatch')
                return reply['result']
            except HTTPError:
                raise  # Invalid tasks are not transient transport failures.
            except (URLError, TimeoutError, ConnectionError):
                if attempt == self.retries:
                    raise
                time.sleep(0.05 * (attempt + 1))

    def map(self, function, tasks):
        if function is not island_task:
            raise ValueError('remote transport accepts island tasks only')
        with ThreadPoolExecutor(max_workers=len(self.urls)) as executor:
            return list(executor.map(self.execute, tasks))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class WorkerHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Coordinator may have timed out; retry is deterministic.

    def do_GET(self):
        self.reply(200 if self.path == '/health' else 404, {'ready': self.path == '/health'})

    def do_POST(self):
        if self.path != '/step':
            self.reply(404, {'error': 'unknown endpoint'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_REQUEST:
                raise ValueError('invalid request size')
            payload = json.loads(self.rfile.read(length))
            if payload['model'] != VERSION or payload['source_hash'] != fingerprint():
                raise ValueError('worker model/source mismatch')
            if digest(payload['task']) != payload['task_hash']:
                raise ValueError('request hash mismatch')
            result = island_task(payload['task'])
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.reply(400, {'error': str(error)})
            return
        self.reply(200, dict(task_hash=payload['task_hash'], result_hash=digest(result), result=result))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8100)
    args = parser.parse_args()
    with HTTPServer((args.host, args.port), WorkerHandler) as server:
        print(json.dumps(dict(url=f'http://{args.host}:{server.server_port}')), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
