"""Run the complete local app using the production WSGI server."""
import os,getpass,threading,webbrowser
if not os.getenv('CLIMA_ADMIN_PASSWORD'):
 while True:
  password=getpass.getpass('Admin password (12+ characters; input is hidden): ')
  if len(password)>=12:os.environ['CLIMA_ADMIN_PASSWORD']=password;break
  print('Please use at least 12 characters.')
os.environ.setdefault('CLIMA_REQUIRE_STAFF_MFA','1')
from waitress import serve
from wsgi import application
host=os.getenv('CLIMA_HOST','127.0.0.1');port=int(os.getenv('PORT','8080'))
print(f'CliMa Care: http://{host}:{port} | Admin username: admin')
if host=='127.0.0.1':threading.Timer(1,lambda:webbrowser.open(f'http://localhost:{port}')).start()
serve(application,host=host,port=port,threads=8,max_request_body_size=7500000)
