"""WSGI entry point: run with Waitress behind an HTTPS reverse proxy."""
import io,os
from http import HTTPStatus
from email.message import Message
import server,clinical
if not os.environ.get('CLIMA_ADMIN_PASSWORD') or len(os.environ['CLIMA_ADMIN_PASSWORD'])<12:
 raise RuntimeError('Set CLIMA_ADMIN_PASSWORD to at least 12 characters')
if os.getenv('CLIMA_SERVERLESS')=='1':
 from cryptography.fernet import Fernet
 clinical.KEY=Fernet(os.environ['CLIMA_DATA_KEY'].encode())
else:
 server.init();clinical.start_scheduler(server.db)
class Adapter(server.Handler):
 def send_response(self,status,message=None):self.status=status
 def send_header(self,key,value):self.response_headers.append((key,str(value)))
 def end_headers(self):pass

def application(environ,start_response):
 if environ.get('PATH_INFO')=='/api/cron':
  import scheduled,json
  if environ.get('REQUEST_METHOD')!='POST' or not scheduled.authorized(environ.get('HTTP_AUTHORIZATION','')):
   start_response('403 Forbidden',[('Content-Type','application/json'),('Cache-Control','no-store')]);return [b'{"error":"Access denied"}']
  try:
   body=json.dumps(scheduled.run(server.db)).encode();status='200 OK'
  except Exception:
   body=b'{"error":"Scheduled task failed"}';status='503 Service Unavailable'
  start_response(status,[('Content-Type','application/json'),('Cache-Control','no-store')]);return [body]
 import cloud_transport
 transfer=cloud_transport.incoming(environ,start_response)
 if transfer is not None:return transfer
 h=Adapter.__new__(Adapter);h.command=environ.get('REQUEST_METHOD','GET');h.path=environ.get('PATH_INFO','/')
 if environ.get('QUERY_STRING'):h.path+='?'+environ['QUERY_STRING']
 h.headers=Message()
 for k,v in environ.items():
  if k.startswith('HTTP_'):h.headers[k[5:].replace('_','-')]=str(v)
 for key in ['CONTENT_TYPE','CONTENT_LENGTH']:
  if environ.get(key):h.headers[key.replace('_','-')]=str(environ[key])
 h.rfile=environ['wsgi.input'];h.wfile=io.BytesIO();h.client_address=(environ.get('REMOTE_ADDR','unknown'),0);h.status=200;h.response_headers=[]
 if h.command not in ['GET','POST']:h.send(405,{'error':'Method not allowed'})
 else:h.handle_request()
 body=h.wfile.getvalue();h.response_headers.extend([('Content-Length',str(len(body))),('Referrer-Policy','no-referrer'),('X-Frame-Options','DENY'),('X-Content-Type-Options','nosniff')])
 return cloud_transport.outgoing(environ,start_response,f'{h.status} {HTTPStatus(h.status).phrase}',h.response_headers,body)
