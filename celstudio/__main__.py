from pathlib import Path
import argparse
import sys


def main():
    parser=argparse.ArgumentParser(description='Cel Studio: estudio de animación 2D (motor v2). CLI de render: python -m celstudio.v2')
    commands=parser.add_subparsers(dest='command',required=True)
    server=commands.add_parser('serve',help='Abre el estudio v2 en http://127.0.0.1:<puerto>/')
    server.add_argument('--projects',default=str(Path(__file__).resolve().parent.parent/'projects'))
    server.add_argument('--port',type=int,default=8768)
    server.add_argument('--open',action='store_true')
    args=parser.parse_args()
    from .server import serve
    serve(args.projects,args.port,args.open)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        main()
    except Exception as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(1)
