"""Peer-to-peer snapshot exchange: closed regions receive no foreign population."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .game import VERSION, digest, island_task
from .worker import WorkerHandler, fingerprint


def request(url, data=None, timeout=30):
    payload = json.dumps(data).encode() if data is not None else None
    with urlopen(Request(url, payload, {'Content-Type': 'application/json'}), timeout=timeout) as response:
        return json.load(response)


class RegionHandler(WorkerHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/snapshot':
            key = parse_qs(parsed.query).get('key', [''])[0]
            with self.server.snapshot_lock:
                payload = self.server.snapshots.get(key)
            if payload is None:
                self.reply(404, {'error': 'snapshot not staged'})
            else:
                self.reply(200, payload)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path not in ('/stage', '/region-step', '/probe'):
            self.reply(404, {'error': 'unsupported regional endpoint'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 32 * 1024 * 1024:
                raise ValueError('invalid request size')
            payload = json.loads(self.rfile.read(length))
            if self.path == '/probe':
                def probe(url):
                    try:
                        response = request(url.rstrip('/') + '/health', timeout=1)
                        return bool(response.get('ready'))
                    except Exception:
                        return False
                with ThreadPoolExecutor(max_workers=len(payload['urls'])) as executor:
                    observed = list(executor.map(probe, payload['urls']))
                self.reply(200, {'reachable': observed})
                return
            if payload['model'] != VERSION or payload['source_hash'] != fingerprint():
                raise ValueError('regional worker source mismatch')
            if self.path == '/stage':
                snapshot = payload['snapshot']
                if any(s['island'] != self.server.region for s in snapshot['speakers']):
                    raise ValueError('coordinator attempted to stage foreign speakers')
                checksum = digest(snapshot)
                with self.server.snapshot_lock:
                    self.server.snapshots[payload['key']] = dict(snapshot=snapshot, checksum=checksum)
                    while len(self.server.snapshots) > 2:
                        del self.server.snapshots[next(iter(self.server.snapshots))]
                self.reply(200, {'checksum': checksum})
                return
            task = payload['task']
            if task['island'] != self.server.region:
                raise ValueError('wrong region worker')
            allowed = set(task['topology'][self.server.region]) - {self.server.region}
            if {peer['island'] for peer in payload['peers']} != allowed:
                raise ValueError('peer request violates topology')
            with self.server.snapshot_lock:
                local = deepcopy(self.server.snapshots[payload['key']]['snapshot'])
            people = local['speakers'][:]
            for peer in payload['peers']:
                response = request(peer['url'] + '/snapshot?key=' + payload['key'])
                if response['checksum'] != peer['checksum'] or digest(response['snapshot']) != peer['checksum']:
                    raise ValueError('peer snapshot checksum mismatch')
                remote = response['snapshot']
                if remote['round'] != local['round'] or any(s['island'] != peer['island'] for s in remote['speakers']):
                    raise ValueError('peer snapshot ownership/round mismatch')
                people.extend(remote['speakers'])
            task['snapshot'] = dict(local, speakers=sorted(people, key=lambda s: s['id']))
            result = island_task(task)
            self.reply(200, {'result': result, 'checksum': digest(result)})
        except Exception as error:
            self.reply(400, {'error': str(error)})


class RegionTransport:
    def __init__(self, urls):
        self.urls = urls

    def map(self, function, tasks):
        if function is not island_task:
            raise ValueError('unsupported task function')
        key = digest([t['task_id'] for t in tasks])
        common = dict(model=VERSION, source_hash=fingerprint(), key=key)
        def stage(task):
            local = dict(task['snapshot'], speakers=[s for s in task['snapshot']['speakers'] if s['island'] == task['island']])
            reply = request(self.urls[task['island']] + '/stage', dict(common, snapshot=local))
            if reply['checksum'] != digest(local):
                raise ValueError('staging hash mismatch')
            return reply['checksum']
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            hashes = list(executor.map(stage, tasks))
        def execute(task):
            minimal = {key: value for key, value in task.items() if key != 'snapshot'}
            peers = [dict(island=i, url=self.urls[i], checksum=hashes[i])
                     for i in task['topology'][task['island']] if i != task['island']]
            response = request(self.urls[task['island']] + '/region-step', dict(common, task=minimal, peers=peers), timeout=90)
            if response['checksum'] != digest(response['result']):
                raise ValueError('result checksum mismatch')
            return response['result']
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            return list(executor.map(execute, tasks))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--island', type=int, required=True)
    parser.add_argument('--port', type=int, default=8100)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), RegionHandler) as server:
        server.region = args.island
        server.snapshots = {}
        server.snapshot_lock = threading.Lock()
        print(json.dumps(dict(region=args.island, port=server.server_port)), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
