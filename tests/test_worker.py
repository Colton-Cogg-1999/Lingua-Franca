from copy import deepcopy
from http.server import HTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from galapagos.game import Game, GameConfig, digest, island_task
from galapagos.worker import RemoteWorkers, WorkerHandler, fingerprint
from galapagos.game import VERSION


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(('127.0.0.1', 0), WorkerHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.game = Game(GameConfig(population=2))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_http_matches_reference_and_duplicate_is_idempotent(self):
        task = self.game.tasks()[0]
        remote = RemoteWorkers([self.url])
        self.assertEqual(remote.execute(task), island_task(task))
        self.assertEqual(remote.execute(task), remote.execute(task))

    def test_transient_failure_retries_same_task(self):
        task = self.game.tasks()[0]
        calls = []
        def flaky(request, **kwargs):
            calls.append(request.data)
            if len(calls) == 1:
                raise URLError('simulated lost connection')
            return urlopen(request, **kwargs)
        with patch('galapagos.worker.urlopen', side_effect=flaky):
            self.assertEqual(RemoteWorkers([self.url]).execute(task), island_task(task))
        self.assertEqual(calls[0], calls[1])

    def test_worker_rejects_different_model_source(self):
        task = self.game.tasks()[0]
        data = json.dumps(dict(task=task, task_hash=digest(task), model=VERSION, source_hash='wrong')).encode()
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.url + '/step', data), timeout=2)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_unavailable_worker_cannot_advance_authoritative_state(self):
        original = deepcopy(self.game.state)
        with patch('galapagos.worker.urlopen', side_effect=URLError('worker unavailable')):
            with self.assertRaises(URLError):
                self.game.step(RemoteWorkers([self.url], retries=0))
        self.assertEqual(original, self.game.state)


if __name__ == '__main__':
    unittest.main()
