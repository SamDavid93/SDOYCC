"""Run the explicitly isolated local laboratory. No connection to Hub accounts."""
import argparse
import uvicorn

from lab import create_app
from provision import DEFAULT_ROOT


def main():
    parser = argparse.ArgumentParser(description='SDOYCC – lokales DuelZone-Techniklabor')
    parser.add_argument('--port', type=int, default=8014)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535: parser.error('Port muss zwischen 1024 und 65535 liegen.')
    url = f'http://127.0.0.1:{args.port}'
    app = create_app(DEFAULT_ROOT, origins=(url,))
    print('Isoliertes Techniklabor. Keine echten Konten oder Bestandsänderungen.')
    print('In zwei getrennten Browserprofilen öffnen: ' + url)
    print('Persönlicher Laborzugang Spieler 1: ' + app.state.codes[0])
    print('Persönlicher Laborzugang Spieler 2: ' + app.state.codes[1])
    print('Zugänge bleiben lokal; nicht öffentlich teilen. Beenden mit Strg+C.')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, ws_max_size=4096)


if __name__ == '__main__': main()
