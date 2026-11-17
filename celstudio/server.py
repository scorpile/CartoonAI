from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import errno
import json
import mimetypes
import re
import shutil
import threading
import uuid
import webbrowser
from .model import asset_path, identifier, ContractError
from .v2.api import Service as V2Service

WEB = Path(__file__).resolve().parent.parent/'web'
MAX_BODY = 28*1024*1024


class Studio:
    def __init__(self, projects):
        self.projects = Path(projects).resolve()
        self.projects.mkdir(parents=True,exist_ok=True)
        self.lock = threading.RLock()
        self.jobs = {}
        self.workers = {}
        self.v2 = V2Service(self.projects)

    def root(self,pid):
        return self.projects/identifier(pid)

    def start_task(self,pid,kind,work):
        # Generic job for engine v2: work(job_id, update, cancelled) -> result dict.
        with self.lock:
            if any(j['status'] in ('queued','running') for j in self.jobs.values()):
                raise ContractError('Ya hay un trabajo en curso. Espera o cancélalo.')
            jid = uuid.uuid4().hex[:12]
            job = {'id':jid,'project':pid,'kind':kind,'status':'queued','done':0,'total':1,'message':'Preparando','cancel':threading.Event()}
            self.jobs[jid] = job
        def update(done,total,message):
            with self.lock:
                job.update(done=done,total=total,message=message)
        def run():
            try:
                job['status']='running'
                job['result']=work(jid,update,job['cancel'].is_set)
                job.update(status='completed',done=job['total'],message='Completado')
            except Exception as exc:
                job.update(status='cancelled' if job['cancel'].is_set() else 'failed', message=str(exc))
        worker=threading.Thread(target=run,daemon=True)
        self.workers[jid]=worker
        worker.start()
        return self.job(jid)

    def job(self,jid):
        with self.lock:
            if jid not in self.jobs:
                raise ContractError('Trabajo inexistente')
            return {k:v for k,v in self.jobs[jid].items() if k != 'cancel'}


def handler(studio):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def send(self,value,status=200,kind='application/json; charset=utf-8'):
            content = json.dumps(value,ensure_ascii=False).encode('utf-8') if kind.startswith('application/json') else value
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def send_file(self,path):
            # Stream long episodes with bounded memory, including seeking support.
            size=path.stat().st_size
            start,end,status=0,size-1,200
            requested=self.headers.get('Range')
            if requested:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
                if not match or not any(match.groups()):
                    return self.send({'error':'Rango inválido'},416)
                left,right=match.groups()
                if left:
                    start=int(left)
                    end=min(size-1,int(right)) if right else size-1
                else:
                    start=max(0,size-int(right))
                if start>end or start>=size:
                    return self.send({'error':'Rango fuera del archivo'},416)
                status=206
            self.send_response(status)
            self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(max(0,end-start+1)))
            self.send_header('Accept-Ranges','bytes')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if status==206:
                self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            with path.open('rb') as stream:
                stream.seek(start)
                remaining=end-start+1
                while remaining>0:
                    chunk=stream.read(min(1024*1024,remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining-=len(chunk)

        def route(self,method):
            try:
                port = self.server.server_address[1]
                if self.headers.get('Host') not in (f'127.0.0.1:{port}',f'localhost:{port}'):
                    return self.send({'error':'Host no permitido'},403)
                if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                    return self.send({'error':'Origen no permitido'},403)
                parsed = urlparse(self.path)
                parts = [unquote(p) for p in parsed.path.strip('/').split('/') if p]
                query = parse_qs(parsed.query)
                body={}
                if method == 'POST':
                    if not self.headers.get('Content-Type','').startswith('application/json'):
                        return self.send({'error':'Se requiere application/json'},415)
                    size=int(self.headers.get('Content-Length','0'))
                    if size < 0 or size > MAX_BODY:
                        return self.send({'error':'Archivo demasiado grande (máximo 20 MB)'},413)
                    body=json.loads(self.rfile.read(size))
                    if not isinstance(body,dict):
                        raise ContractError('El cuerpo debe ser un objeto JSON')
                if parts == ['api','health']:
                    return self.send({'app':'cel-studio','version':'0.3.0','ffmpeg':bool(shutil.which('ffmpeg'))})
                if len(parts)>=3 and parts[:2]==['api','v2']:
                    value,status,kind=studio.v2.handle(studio,method,parts[2:],query,body)
                    return self.send(value,status,kind)
                if len(parts)>=3 and parts[:2]==['api','jobs']:
                    jid=identifier(parts[2])
                    if method=='POST':
                        studio.jobs[jid]['cancel'].set()
                    return self.send(studio.job(jid))
                if len(parts)>=4 and parts[0]=='files' and method=='GET':
                    if len(parts)>=6 and parts[2]=='episodes':      # files/<serie>/episodes/<ep>/renders/<file>
                        root=studio.root(parts[1])/'episodes'/identifier(parts[3])
                        if parts[4]!='renders':
                            raise ContractError('Carpeta no pública')
                        return self.send_file(asset_path(root,'/'.join(parts[4:])))
                    root=studio.root(parts[1])
                    if parts[2] not in ('assets','refs','renders'):
                        raise ContractError('Carpeta no pública')
                    file=asset_path(root,'/'.join(parts[2:]))
                    return self.send_file(file)
                pages={'':'studio.html','studio.html':'studio.html','studio.js':'studio.js','studio.css':'studio.css','style.css':'style.css'}
                if method=='GET' and len(parts)<=1 and (parts[0] if parts else '') in pages:
                    file=WEB/pages[parts[0] if parts else '']
                    kind={'.js':'text/javascript','.css':'text/css','.html':'text/html'}[file.suffix]+'; charset=utf-8'
                    return self.send(file.read_bytes(),kind=kind)
                self.send({'error':'Ruta inexistente'},404)
            except (ValueError, KeyError, TypeError, OSError, IndexError) as exc:
                try:
                    self.send(getattr(exc,'payload',None) or {'error':str(exc)},400)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def do_GET(self):
            self.route('GET')

        def do_POST(self):
            self.route('POST')
    return Handler


def create_server(studio,port=8768):
    request_handler=handler(studio)
    try:
        return ThreadingHTTPServer(('127.0.0.1',port),request_handler)
    except OSError as exc:
        # Windows reports Winsock codes, while POSIX uses errno values.
        unavailable=(exc.errno in (errno.EADDRINUSE,errno.EACCES,10048,10013)
                     or getattr(exc,'winerror',None) in (10048,10013))
        if not port or not unavailable:
            raise
        server=ThreadingHTTPServer(('127.0.0.1',0),request_handler)
        print(f'El puerto {port} no está disponible; se usará el puerto {server.server_address[1]}.',flush=True)
        return server


def serve(projects,port=8768,open_browser=False):
    studio=Studio(projects)
    server=create_server(studio,port)
    url=f'http://127.0.0.1:{server.server_address[1]}'
    print(f'Cel Studio — {url}',flush=True)
    print('Solo local. Ctrl+C para cerrar. No se genera audio.',flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in studio.jobs.values():
            job['cancel'].set()
        for worker in studio.workers.values():
            worker.join(timeout=15)
        server.server_close()
