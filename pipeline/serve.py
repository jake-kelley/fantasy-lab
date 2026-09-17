"""Portable local/Docker service with background refresh and last-good-bundle retention."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import sys
import threading
from .data import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--interval-hours', type=float, default=6)
    args = parser.parse_args()
    if args.interval_hours < 1: parser.error('Refresh interval must be at least one hour')
    stop = threading.Event()

    def update():
        while not stop.is_set():
            result = subprocess.run([sys.executable, '-m', 'pipeline.run'], cwd=ROOT)
            if result.returncode:
                print('Refresh failed; retaining the previous projection bundle.', flush=True)
            stop.wait(args.interval_hours * 3600)

    threading.Thread(target=update, daemon=True).start()
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(ROOT/'site'))
    server = ThreadingHTTPServer((args.bind,args.port), handler)
    print(f'Fieldwork: http://{args.bind}:{args.port}; refresh every {args.interval_hours:g} hours', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: stop.set();server.server_close()


if __name__ == '__main__': main()
