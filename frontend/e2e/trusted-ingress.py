"""Native NGINX ingress protocol checks; no real API, database or deployment claim.

CADENTRA_TEST_NGINX must point to reviewed NGINX1.30.6 built with realip.
The only trust-policy adaptation replaces exact Traefik10.0.1.20 with127.0.0.1;
static paths, listener, API/DNS fixture addresses and runtime paths are local.
"""
import gzip
import hashlib
import http.client
import ipaddress
import json
import os
import socket
import socketserver
import struct
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get('CADENTRA_TEST_NGINX', '/tmp/cadentra-agent4-nginx-native/nginx-1.30.6/objs/nginx'))
DEV_SHA = '96b4280b974063368fa06ef76b4caeee9d2ec7a8dfe6e2a2311bc3288325bb99'
ROOT = Path(tempfile.mkdtemp(prefix='cadentra-trusted-ingress-'))
records, checks, dns_queries = [], [], []
sha = lambda value: hashlib.sha256(value).hexdigest()
assert sha((FRONTEND/'nginx.conf').read_bytes()) == DEV_SHA
version = subprocess.run([str(BINARY), '-V'], capture_output=True, text=True, check=True).stderr
assert 'nginx/1.30.6' in version and '--with-http_realip_module' in version

class Api(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond()
    def do_POST(self):
        self.respond()
    def respond(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode()
        record = {'method':self.command, 'path':self.path, 'body':body,
                  'headers':{name:self.headers.get_all(name) for name in [
                      'Host','Origin','Cookie','X-CSRF-Token','X-Cadentra-Client-IP',
                      'X-Forwarded-For','Forwarded','X-Real-IP','CF-Connecting-IP']}}
        records.append(record)
        payload = json.dumps({'fixture_only':True, **record}).encode()
        self.send_response(404 if '/missing' in self.path else 200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','private, no-store')
        self.send_header('Set-Cookie','fixture_only=yes; Path=/api; HttpOnly; SameSite=Lax')
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *args):
        pass

class Dns(socketserver.BaseRequestHandler):
    def handle(self):
        query, connection = self.request
        offset = 12
        labels = []
        while query[offset]:
            labels.append(query[offset+1:offset+1+query[offset]].decode('ascii'))
            offset += query[offset]+1
        name = '.'.join(labels)
        dns_queries.append(name)
        question = query[12:offset+5]
        if name != 'cadentra-api-proxy':
            connection.sendto(query[:2]+struct.pack('!HHHHH',0x8183,1,0,0,0)+question,self.client_address)
            return
        answer = query[:2]+struct.pack('!HHHHH',0x8180,1,1,0,0)+question
        answer += b'\xc0\x0c'+struct.pack('!HHIH',1,1,1,4)+socket.inet_aton('127.0.0.1')
        connection.sendto(answer,self.client_address)

api = ThreadingHTTPServer(('127.0.0.1',0),Api)
dns = socketserver.UDPServer(('127.0.0.1',0),Dns)
for server in [api,dns]:
    threading.Thread(target=server.serve_forever,daemon=True).start()
probe = socket.socket()
probe.bind(('127.0.0.1',0))
port = probe.getsockname()[1]
probe.close()
static = ROOT/'static'
(static/'assets').mkdir(parents=True)
index_body = b'<!doctype html><html><title>Protocol fixture only</title><body>Not the Cadentra application</body></html>'
(static/'index.html').write_bytes(index_body)
asset = b'/* protocol fixture only */\n'+b'window.fixtureOnly=true;\n'*100
(static/'assets/app-ABCDEF12.js').write_bytes(asset)
source = (FRONTEND/'nginx.production.conf').read_text()
assert source.count('10.0.1.20') == 2
adapted = source.replace('10.0.1.20','127.0.0.1')
adapted = adapted.replace('listen 8080;',f'listen 127.0.0.1:{port};')
adapted = adapted.replace('/usr/share/nginx/html',str(static))
assert source.count('server cadentra-api-proxy:8001 resolve;') == 1
adapted = adapted.replace('cadentra-api-proxy:8001',f'cadentra-api-proxy:{api.server_port}')
adapted = adapted.replace('127.0.0.11',f'127.0.0.1:{dns.server_address[1]}')
site = ROOT/'site.conf'
site.write_text(adapted)
mime = BINARY.parent.parent/'conf/mime.types'
config = ROOT/'nginx.conf'
config.write_text(f'''worker_processes 1;
pid {ROOT}/nginx.pid;
error_log {ROOT}/error.log warn;
events {{ worker_connections 256; }}
http {{
 include {mime};
 client_body_temp_path {ROOT}/client;
 proxy_temp_path {ROOT}/proxy;
 include {site};
}}
''')
subprocess.run([str(BINARY),'-e',str(ROOT/'error.log'),'-p',str(ROOT),'-c',str(config),'-t'],check=True)
process = subprocess.Popen([str(BINARY),'-e',str(ROOT/'error.log'),'-p',str(ROOT),'-c',str(config),'-g','daemon off;'])

def request(headers, path='/api/v1/echo?preserve=a%2Fb', peer='127.0.0.1', method='GET', body=None):
    connection = http.client.HTTPConnection('127.0.0.1',port,timeout=3,source_address=(peer,0))
    # putheader writes every tuple separately: duplicate CF/internal headers are
    # actually transmitted twice, not collapsed by a dictionary-based client.
    connection.putrequest(method,path,skip_host=True,skip_accept_encoding=True)
    connection.putheader('Host','cadentra.example')
    connection.putheader('Connection','close')
    for key,value in headers:
        connection.putheader(key,value)
    encoded = body.encode() if body is not None else None
    if encoded is not None:
        connection.putheader('Content-Length',str(len(encoded)))
    connection.endheaders(encoded)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result

try:
    deadline = time.monotonic()+10
    while True:
        try:
            assert request([])[0] == 403
            break
        except ConnectionRefusedError:
            assert time.monotonic()<deadline
            time.sleep(.05)
    checks.append({'case':'missing_cf_and_direct_http_health','status':403,'upstream_calls':0})
    valid = ['198.51.100.7','2001:0DB8:0000:0000:0000:0000:0000:0001','::ffff:192.0.2.1']
    for address in valid:
        start = len(records)
        status,headers,body = request([('CF-Connecting-IP',address)])
        assert status == 200
        received = json.loads(body)['headers']['X-Cadentra-Client-IP']
        assert len(received)==1 and ipaddress.ip_address(received[0])==ipaddress.ip_address(address)
        if address.startswith('2001:'):
            assert received==['2001:db8::1']
        assert len(records)==start+1
        checks.append({'case':'valid_ip','input':address,'forwarded':received,'status':status})
    spoofed = [('CF-Connecting-IP','203.0.113.9'),('X-Cadentra-Client-IP','1.1.1.1'),('x-cadentra-client-ip','2.2.2.2'),
               ('X-Forwarded-For','3.3.3.3, 4.4.4.4'),('Forwarded','for=5.5.5.5'),('X-Real-IP','6.6.6.6'),
               ('Origin','https://cadentra.example'),('Cookie','fixture_session=not-a-secret'),('X-CSRF-Token','fixture-csrf')]
    status,headers,body = request(spoofed,method='POST',body='{"fixture_only":true}')
    data = json.loads(body)
    assert status==200 and data['headers']['X-Cadentra-Client-IP']==['203.0.113.9']
    for name in ['X-Forwarded-For','Forwarded','X-Real-IP','CF-Connecting-IP']:
        assert data['headers'][name] is None
    assert data['headers']['Host']==['cadentra.example'] and data['headers']['Origin']==['https://cadentra.example']
    assert data['headers']['Cookie']==['fixture_session=not-a-secret'] and data['headers']['X-CSRF-Token']==['fixture-csrf']
    assert data['body']=='{"fixture_only":true}' and data['path']=='/api/v1/echo?preserve=a%2Fb'
    checks.append({'case':'spoofed_internal_overwritten_once_and_forwarding_stripped','status':status,'origin_cookie_csrf_body_query_preserved':True})
    rejected = [[],[('CF-Connecting-IP','')],[('CF-Connecting-IP','not-an-ip')],
                [('CF-Connecting-IP','999.1.1.1')],[('CF-Connecting-IP','001.2.3.4')],[('CF-Connecting-IP','1.2.3')],
                [('CF-Connecting-IP','198.51.100.7:443')],[('CF-Connecting-IP','[2001:db8::1]:443')],
                [('CF-Connecting-IP','2001:db8::gg')],[('CF-Connecting-IP','1:2:3:4:5:6:7:8:9')],
                [('CF-Connecting-IP','::ffff:001.2.3.4')],[('CF-Connecting-IP','198.51.100.7, 203.0.113.9')],
                [('CF-Connecting-IP','198.51.100.7'),('CF-Connecting-IP','198.51.100.7')],
                [('CF-Connecting-IP','198.51.100.7'),('cf-connecting-ip','2001:db8::1')],
                [('CF-Connecting-IP','127.0.0.1')]]
    for index,raw in enumerate(rejected):
        start = len(records)
        status,headers,body = request(raw)
        assert status==403 and len(records)==start, (raw,status)
        checks.append({'case':f'reject_{index}','raw_cf_values':[value for key,value in raw],'status':status,'upstream_calls':0})
    start = len(records)
    assert request([('CF-Connecting-IP','203.0.113.7')],peer='127.0.0.2')[0]==403 and len(records)==start
    checks.append({'case':'wrong_original_peer','status':403,'upstream_calls':0})
    trusted = [('CF-Connecting-IP','198.51.100.7')]
    for path in ['/','/index.html','/reset-password?token=public-fixture-only']:
        status,headers,body = request(trusted,path)
        assert status==200 and body==index_body, (path,status,body[:100])
        assert headers['Referrer-Policy']=='no-referrer' and headers['Cache-Control']=='no-store'
    status,headers,body = request(trusted,'/assets/app-ABCDEF12.js')
    assert status==200 and body==asset and headers['Cache-Control']=='public, max-age=31536000, immutable'
    status,headers,body = request(trusted+[('Accept-Encoding','gzip')],'/assets/app-ABCDEF12.js')
    assert headers['Content-Encoding']=='gzip' and gzip.decompress(body)==asset
    assert request(trusted,'/assets/missing.js')[0]==404
    status,headers,body = request(trusted,'/api/v1/missing?preserve=1')
    assert status==404 and json.loads(body)['path']=='/api/v1/missing?preserve=1'
    assert headers['Cache-Control']=='private, no-store' and headers['Set-Cookie']=='fixture_only=yes; Path=/api; HttpOnly; SameSite=Lax'
    assert dns_queries and set(dns_queries)=={'cadentra-api-proxy'}, dns_queries
    checks.append({'case':'spa_assets_cache_gzip_errors_cookie_referrer_preserved','passed':True,'dns_alias':'cadentra-api-proxy'})
finally:
    process.terminate()
    process.wait(timeout=5)
    for server in [api,dns]:
        server.shutdown(); server.server_close()

# Exercise the actual selector logic with immutable source fixtures. Runtime
# paths/mime/config directory are adapted under/tmp, never the host /etc.
selector = (FRONTEND/'docker-entrypoint.sh').read_text()
configs = ROOT/'immutable-configs'
configs.mkdir()
for name,source_name in [('nginx.production.conf','nginx.production.conf'),('nginx.development.conf','nginx.conf')]:
    text = (FRONTEND/source_name).read_text()
    text = text.replace('listen 8080;',f'listen 127.0.0.1:{port};').replace('/usr/share/nginx/html',str(static))
    (configs/name).write_text(text)
    (configs/name).chmod(0o444)
configs.chmod(0o555)
bin_dir = ROOT/'bin'
bin_dir.mkdir()
(bin_dir/'nginx').symlink_to(BINARY)
selector = selector.replace('/etc/cadentra',str(configs)).replace('/etc/nginx/mime.types',str(mime)).replace('/tmp/cadentra-nginx',str(ROOT/'selector-state'))
script = ROOT/'entrypoint.sh'
script.write_text(selector)
script.chmod(0o555)
source_hashes = {name:sha((configs/name).read_bytes()) for name in ['nginx.production.conf','nginx.development.conf']}
assert os.getuid()!=0
for selected in [None,'false','true']:
    environment = dict(os.environ,PATH=str(bin_dir)+os.pathsep+os.environ['PATH'])
    environment.pop('CADENTRA_TRUSTED_INGRESS',None)
    if selected is not None:
        environment['CADENTRA_TRUSTED_INGRESS']=selected
    result = subprocess.run(['sh',str(script),'nginx','-t'],env=environment,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    generated = (ROOT/'selector-state/nginx.conf').read_text()
    chosen = 'nginx.production.conf' if selected=='true' else 'nginx.development.conf'
    assert f'include {configs/chosen};' in generated
    checks.append({'case':'selector','value':selected,'selected':chosen,'nonroot_config_test':True})
for invalid in ['TRUE','1','yes','', 'false ']:
    result = subprocess.run(['sh',str(script),'nginx','-t'],env=dict(os.environ,CADENTRA_TRUSTED_INGRESS=invalid),capture_output=True,text=True)
    assert result.returncode==64
checks.append({'case':'unknown_selector_values_fail_closed','passed':True})
assert source_hashes=={name:sha((configs/name).read_bytes()) for name in source_hashes}
assert sha((FRONTEND/'nginx.conf').read_bytes())==DEV_SHA
report = {'fixture_only':True,'real_traefik_cloudflare_docker_api_or_database_verified':False,
          'base':'25e6351','uid':os.getuid(),'nginx_version':version.strip(),'nginx_binary_sha256':sha(BINARY.read_bytes()),
          'source_hashes':{name:sha((FRONTEND/name).read_bytes()) for name in ['nginx.conf','nginx.production.conf','docker-entrypoint.sh','Dockerfile']},
          'upstream_alias':'cadentra-api-proxy','dns_queries':sorted(set(dns_queries)),
          'alias_rationale':'Coordinator observed Dokploy default-network attachment; cadentra-api-proxy must resolve only on the dedicated proxy network, avoiding ambiguous default/api service aliases.',
          'checks':checks,'adaptations':['Exact trusted Traefik peer10.0.1.20 replaced only with127.0.0.1 in native policy; wrong peer127.0.0.2 tested.',
          'Listener/static/MIME/runtime paths and API/DNS protocol fixture destinations use task-owned loopback/temp resources.',
          'Selector config directory and MIME/runtime paths adapted under/tmp; source files0444 and directory0555; process nonroot.',
          'No actual read-only-rootfs mount or container execution; immutable configuration simulation only.'],
          'healthcheck':'No HTTP bypass. Missing identity returns403; use coordinator-approved local config/process health contract.',
          'runtime_directory':str(ROOT),'servers_stopped':True}
output = Path(os.environ.get('CADENTRA_INGRESS_EVIDENCE','/tmp/cadentra-agent4-trusted-ingress-evidence.json'))
output.write_text(json.dumps(report,indent=2))
print(json.dumps({'passed_checks':len(checks),'evidence':str(output),'source_hashes':report['source_hashes'],'binary_sha256':report['nginx_binary_sha256']}))
