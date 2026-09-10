"""Unit and real-Caddy integration tests. No public ACME requests, no machine trust changes."""
import base64
import hashlib
import http.client
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
REAL = os.environ.get('CADDY_TEST_BINARY', '')


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='amp-caddy-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / 'server files'
        self.base.mkdir()
        self.home = Path(self.tmp.name) / 'home'
        self.home.mkdir()
        for name in ('amp-caddy.sh', 'install-caddy.sh'):
            shutil.copy2(ROOT / 'runtime' / name, self.base / name)
        self.binary = self.base / 'caddy'
        self.binary.write_text('#!/bin/bash\n[[ "$1" == validate ]] && exit "${FAKE_VALIDATE_FAIL:-0}"\nexit 0\n')
        self.binary.chmod(0o755)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('CADDY_', 'XDG_'))}
        self.env.update(HOME=str(self.home), CADDY_DOMAIN='gaminglive.mooo.com',
                        CADDY_UPSTREAM='127.0.0.1:7777', CADDY_BIND_ADDRESS='127.0.0.1')

    def call(self, **changes):
        env = {**self.env, **changes}
        return subprocess.run(['bash', str(self.base / 'amp-caddy.sh'), 'prepare'],
                              env=env, cwd='/', capture_output=True, text=True, timeout=10)

    def config(self):
        return (self.base / 'private/Caddyfile.generated').read_text()

    def test_minimal_configuration(self):
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.config()
        for fragment in ('http_port 18080', 'https_port 18443', 'admin off',
                         'protocols h1 h2', 'reverse_proxy 127.0.0.1:7777',
                         'redir https://gaminglive.mooo.com{uri} 308',
                         'header_up X-Real-IP {remote_host}'):
            self.assertIn(fragment, text)
        self.assertNotIn('file_server', text)
        self.assertNotIn('tls_insecure_skip_verify', text)
        self.assertEqual((self.base / 'private').stat().st_mode & 0o777, 0o700)

    def test_domain_normalized(self):
        self.assertEqual(self.call(CADDY_DOMAIN='GamingLive.MOOO.com').returncode, 0)
        self.assertIn('https://gaminglive.mooo.com {', self.config())

    def test_reject_domain_injection_and_wrong_formats(self):
        for value in ('', 'https://gaminglive.mooo.com', '*.mooo.com', '127.0.0.1',
                      'name..com', 'name.com:443', 'name.com/path', 'name.com\nimport /etc/passwd',
                      'name.com { }', '$(touch /tmp/never-do-this).com', 'a.test'):
            with self.subTest(value=value):
                self.assertNotEqual(self.call(CADDY_DOMAIN=value).returncode, 0)

    def test_reject_bad_upstream(self):
        for value in ('127.0.0.1:18443', 'gaminglive.mooo.com:443', 'http://localhost:7777',
                      '127.0.0.1:7777/path', 'localhost:99999', '999.1.1.1:80',
                      'host:0', 'host:80;id', '[::1]:7777', 'host:80\nfile_server'):
            with self.subTest(value=value):
                self.assertNotEqual(self.call(CADDY_UPSTREAM=value).returncode, 0)

    def test_reject_bad_ports_and_bind(self):
        for changes in ({'CADDY_HTTP_PORT': '80'}, {'CADDY_HTTPS_PORT': '18080'},
                        {'CADDY_HTTP_PORT': '-1'}, {'CADDY_HTTP_PORT': '18x'},
                        {'CADDY_BIND_ADDRESS': '0.0.0.0\nadmin :2019'},
                        {'CADDY_BIND_ADDRESS': '::'}, {'CADDY_HTTP_PORT': '018080'}):
            self.assertNotEqual(self.call(**changes).returncode, 0)

    def test_testmode_has_no_proxy(self):
        self.assertEqual(self.call(CADDY_MODE='test').returncode, 0)
        self.assertNotIn('reverse_proxy', self.config())
        self.assertIn('nur der Verbindungstest', self.config())

    def test_failed_validation_keeps_last_good_file(self):
        self.assertEqual(self.call().returncode, 0)
        original = self.config()
        result = self.call(CADDY_DOMAIN='other.mooo.com', FAKE_VALIDATE_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config(), original)
        self.assertEqual(list((self.base / 'private').glob('*.pending.*')), [])

    def test_previous_config_and_original_preserved(self):
        self.assertEqual(self.call().returncode, 0)
        previous = self.config()
        manual = self.base / 'Caddyfile'
        manual.write_text('# Private manual config is untouched\n')
        self.assertEqual(self.call(CADDY_MODE='test').returncode, 0)
        self.assertEqual((self.base / 'private/Caddyfile.generated.previous').read_text(), previous)
        self.assertEqual(manual.read_text(), '# Private manual config is untouched\n')

    def test_old_default_certificate_storage_is_reused(self):
        native = self.home / '.local/share/caddy'
        (native / 'certificates').mkdir(parents=True)
        marker = native / 'certificates/keep.key'
        marker.write_text('never copy this into a repository')
        (self.base / 'Caddyfile').write_text('{\n admin off\n}\n')
        self.assertEqual(self.call().returncode, 0)
        self.assertEqual((self.base / 'private/storage.path').read_text().strip(), str(native))
        self.assertEqual(marker.read_text(), 'never copy this into a repository')
        self.assertEqual(self.call(CADDY_DOMAIN='other.mooo.com').returncode, 0)

    def test_missing_old_storage_is_not_silently_replaced(self):
        (self.base / 'Caddyfile').write_text('{\n admin off\n}\n')
        self.assertNotEqual(self.call().returncode, 0)
        self.assertFalse((self.base / 'private/storage.path').exists())

    def test_custom_old_storage_requires_explicit_confirmation(self):
        (self.base / 'Caddyfile').write_text('{\n storage file_system {\n root /somewhere\n }\n}\n')
        self.assertNotEqual(self.call().returncode, 0)
        custom = Path(self.tmp.name) / 'existing certs'
        custom.mkdir()
        self.assertEqual(self.call(CADDY_STORAGE_DIRECTORY=str(custom)).returncode, 0)

    def test_storage_change_refused(self):
        self.assertEqual(self.call().returncode, 0)
        target = Path(self.tmp.name) / 'other'
        target.mkdir()
        self.assertNotEqual(self.call(CADDY_STORAGE_DIRECTORY=str(target)).returncode, 0)

    def test_storage_injection_refused(self):
        for value in ('relative', '/tmp/x" }', '/tmp/x\\y', '/tmp/x\ny', '/tmp/{$HOME}'):
            self.assertNotEqual(self.call(CADDY_STORAGE_DIRECTORY=value).returncode, 0)

    def test_symlink_cannot_redirect_output(self):
        private = self.base / 'private'
        private.mkdir()
        outside = Path(self.tmp.name) / 'outside'
        outside.write_text('keep')
        (private / 'Caddyfile.generated').symlink_to(outside)
        self.assertNotEqual(self.call().returncode, 0)
        self.assertEqual(outside.read_text(), 'keep')

    def test_bad_archive_preserves_binary_and_certificates(self):
        (self.base / 'caddy_2.11.4_linux_amd64.tar.gz').write_bytes(b'not the download')
        original = self.binary.read_bytes()
        result = subprocess.run(['bash', str(self.base / 'install-caddy.sh')],
                                capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.binary.read_bytes(), original)


class TemplateTests(unittest.TestCase):
    def test_bash_syntax(self):
        for file in (ROOT / 'runtime').glob('*.sh'):
            subprocess.run(['bash', '-n', str(file)], check=True)

    def test_manifests_and_setting_bindings(self):
        # Before activation the integration-only CI may still use the legacy template.
        kvp = ROOT / 'caddy-https.kvp'
        if not kvp.exists() or 'amp-caddy.sh' not in kvp.read_text():
            self.skipTest('new template not activated in this preparation commit')
        values = dict(line.split('=', 1) for line in kvp.read_text().splitlines() if '=' in line)
        settings = json.loads((ROOT / 'caddy-httpsconfig.json').read_text())
        environment = json.loads(values['App.EnvironmentVariables'])
        names = {s['FieldName'] for s in settings}
        self.assertEqual(len(names), len(settings))
        for s in settings:
            self.assertIsInstance(s['DefaultValue'], str)
            self.assertIn('{{' + s['FieldName'] + '}}', json.dumps(environment))
        self.assertEqual(values['Limits.SleepMode'], 'False')
        self.assertEqual(values['App.ExecutableLinux'], '/bin/bash')
        self.assertEqual(values['App.ExitMethod'], 'SIGTERM')
        self.assertIn('{{$HttpPort}}', json.dumps(environment))
        self.assertIn('{{$HttpsPort}}', json.dumps(environment))
        ports = json.loads((ROOT / 'caddy-httpsports.json').read_text())
        self.assertEqual({p['Ref'] for p in ports}, {'HttpPort', 'HttpsPort'})
        self.assertTrue(all(p['Protocol'] == 'TCP' for p in ports))
        self.assertTrue(any(s['FieldName'] == 'Domain' and s['Required'] for s in settings))
        for file in ROOT.glob('*.json'):
            json.loads(file.read_text())


class EchoBackend(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def do_GET(self):
        if self.headers.get('Upgrade', '').lower() == 'websocket':
            key = self.headers['Sec-WebSocket-Key']
            accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            self.send_response(101)
            self.send_header('Upgrade', 'websocket')
            self.send_header('Connection', 'Upgrade')
            self.send_header('Sec-WebSocket-Accept', accept)
            self.end_headers()
            self.wfile.write(b'\x81\x05hello'); self.wfile.flush()
            self.close_connection = True
            return
        self.echo()
    def do_POST(self): self.echo()
    def echo(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        data = json.dumps({'path': self.path, 'headers': dict(self.headers), 'body': body.decode()}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Set-Cookie', 'sample=1; HttpOnly; Secure; SameSite=Strict')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def log_message(self, *args): pass


def freeport():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


@unittest.skipUnless(REAL, 'real Caddy unavailable; CI must run these before release')
class RealCaddyTests(unittest.TestCase):
    setUp = RuntimeTests.setUp
    call = RuntimeTests.call
    config = RuntimeTests.config
    def test_real_tls_http_websocket_and_restart(self):
        shutil.copy2(REAL, self.binary); self.binary.chmod(0o755)
        backend = http.server.ThreadingHTTPServer(('127.0.0.1', 0), EchoBackend)
        backend.daemon_threads = True
        thread = threading.Thread(target=backend.serve_forever, daemon=True); thread.start()
        self.addCleanup(backend.server_close); self.addCleanup(backend.shutdown)
        hp, sp = freeport(), freeport()
        while sp == hp: sp = freeport()
        self.env.update(CADDY_HTTP_PORT=str(hp), CADDY_HTTPS_PORT=str(sp),
                        CADDY_UPSTREAM=f'127.0.0.1:{backend.server_port}',
                        CADDY_DOMAIN='amp-check.example.net')
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = self.config()
        # Test-only transformation: use a private CA; never contact production ACME or install trust.
        config = config.replace('    admin off', '    local_certs\n    skip_install_trust\n    admin off', 1)
        fixture = self.base / 'integration.Caddyfile'
        fixture.write_text(config)
        subprocess.run([str(self.binary), 'validate', '--config', str(fixture), '--adapter', 'caddyfile'],
                       check=True, capture_output=True)
        logpath = self.base / 'integration.log'
        logfile = logpath.open('wb'); self.addCleanup(logfile.close)
        def launch():
            proc = subprocess.Popen([str(self.binary), 'run', '--config', str(fixture), '--adapter', 'caddyfile'],
                                    env=self.env, stdout=logfile, stderr=logfile)
            self.addCleanup(lambda: proc.poll() is not None or proc.terminate())
            deadline = time.monotonic() + 15
            rootca = self.base / 'private/caddy-data/pki/authorities/local/root.crt'
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    self.fail(logpath.read_text())
                if rootca.exists():
                    try:
                        ctx = ssl.create_default_context(cafile=str(rootca))
                        with socket.create_connection(('127.0.0.1', sp), timeout=1) as raw:
                            with ctx.wrap_socket(raw, server_hostname='amp-check.example.net'):
                                return proc, ctx, rootca
                    except (OSError, ssl.SSLError): pass
                time.sleep(0.05)
            proc.terminate(); proc.wait(5)
            self.fail(logpath.read_text())
        proc, ctx, rootca = launch()
        initial_ca = rootca.read_bytes()
        conn = http.client.HTTPConnection('127.0.0.1', hp, timeout=5)
        conn.request('GET', '/abc?x=1', headers={'Host': 'amp-check.example.net'})
        response = conn.getresponse()
        self.assertEqual(response.status, 308)
        self.assertEqual(response.getheader('Location'), 'https://amp-check.example.net/abc?x=1')
        response.read(); conn.close()
        def request(path, method='GET', data=None, headers=None):
            raw = socket.create_connection(('127.0.0.1', sp), timeout=5)
            tls = ctx.wrap_socket(raw, server_hostname='amp-check.example.net')
            c = http.client.HTTPConnection('amp-check.example.net'); c.sock = tls
            h = {'Host': 'amp-check.example.net', **(headers or {})}
            c.request(method, path, body=data, headers=h)
            r = c.getresponse(); result = (r.status, dict(r.getheaders()), r.read()); c.close()
            return result
        status, headers, body = request('/api/echo', 'POST', b'{"x":1}',
            {'Content-Type': 'application/json', 'Origin': 'https://amp-check.example.net',
             'X-Real-IP': '1.2.3.4', 'Forwarded': 'for=1.2.3.4', 'Cookie': 'sample=1'})
        self.assertEqual(status, 200)
        payload = json.loads(body); echoed = {k.lower(): v for k, v in payload['headers'].items()}
        self.assertEqual(echoed['host'], 'amp-check.example.net')
        self.assertEqual(echoed['x-real-ip'], '127.0.0.1')
        self.assertEqual(echoed['origin'], 'https://amp-check.example.net')
        self.assertNotIn('forwarded', echoed)
        self.assertIn('Secure', headers['Set-Cookie'])
        self.assertEqual(payload['body'], '{"x":1}')
        for path in ('/.env', '/.git/config', '/private/storage.path', '/Caddyfile'):
            self.assertEqual(request(path)[0], 404)
        with socket.create_connection(('127.0.0.1', sp), timeout=5) as raw:
            with ctx.wrap_socket(raw, server_hostname='amp-check.example.net') as tls:
                tls.sendall(b'GET /socket.io/?EIO=4&transport=websocket HTTP/1.1\r\nHost: amp-check.example.net\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n')
                reply = b''
                while b'hello' not in reply:
                    chunk = tls.recv(4096)
                    self.assertTrue(chunk, 'WebSocket closed before payload')
                    reply += chunk
                self.assertIn(b'101 Switching Protocols', reply)
                self.assertIn(b'\x81\x05hello', reply)
        proc.terminate(); self.assertEqual(proc.wait(15), 0)
        proc, ctx, rootca = launch()
        self.assertEqual(rootca.read_bytes(), initial_ca)
        backend.shutdown(); backend.server_close()
        self.assertEqual(request('/api/health')[0], 503)
        proc.terminate(); self.assertEqual(proc.wait(15), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
