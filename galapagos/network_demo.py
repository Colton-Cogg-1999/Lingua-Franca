"""Launch three loopback workers, run an experiment, and clean up owned processes."""
import argparse
import json
from pathlib import Path
import selectors
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('examples/contact-game.json'))
    parser.add_argument('--rounds', type=int, default=50)
    parser.add_argument('--output', type=Path, default=Path('runs/communication-http'))
    args = parser.parse_args()
    processes, endpoints = [], []
    try:
        for _ in range(3):
            process = subprocess.Popen([sys.executable, '-m', 'galapagos.worker', '--port', '0'],
                                       stdout=subprocess.PIPE, text=True)
            processes.append(process)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=10):
                    raise RuntimeError('worker startup timeout')
            endpoints.append(json.loads(process.stdout.readline())['url'])
        command = [sys.executable, '-m', 'galapagos.play', '--config', str(args.config),
                   '--rounds', str(args.rounds), '--output', str(args.output)]
        for endpoint in endpoints:
            command.extend(['--worker-url', endpoint])
        subprocess.run(command, check=True)
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if process.stdout:
                process.stdout.close()


if __name__ == '__main__':
    main()
