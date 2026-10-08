"""CPU stand-in for the SGLang server: /health, /v1/chat/completions with usage, SGLang-style log lines, one child in its group."""
import json, os, signal, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
port = int(sys.argv[sys.argv.index('--port') + 1])
frspec = '--speculative-token-map' in sys.argv
delay = 0.20 if frspec else 0.14          # FR-Spec off is clearly faster in this fake, so the gate must say ADOPT
if os.environ.get('FAKE_IGNORE_TERM') == '1':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, '-c', 'import time, signal; signal.signal(signal.SIGTERM, signal.SIG_IGN) if __import__("os").environ.get("FAKE_IGNORE_TERM")=="1" else None; time.sleep(600)'])
ts = lambda: time.strftime('[%Y-%m-%d %H:%M:%S]')
print(ts(), 'Load weight end. elapsed=1.50 s, type=Fake', flush=True)
print(ts(), 'KV Cache is allocated. dtype: torch.float8_e4m3fn, #tokens: 1011264, K size: 5.79 GB', flush=True)
inflight = [0]; lock = threading.Lock(); t_ready = time.time() + 1.5
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        code = 200 if self.path == '/health' and time.time() >= t_ready else 503
        self.send_response(code); self.end_headers()
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert body['model'] == 'flashnext' and body['messages'][-1]['role'] == 'user' and body['max_tokens'] == 2048
        with lock: inflight[0] += 1
        time.sleep(delay)
        with lock: inflight[0] -= 1
        out = json.dumps({'choices': [{'finish_reason': 'tool_calls'}], 'usage': {'completion_tokens': 100, 'prompt_tokens': 5000, 'prompt_tokens_details': {'cached_tokens': 4900}}}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(out))); self.end_headers(); self.wfile.write(out)
def logger():
    while True:
        time.sleep(0.5)
        with lock: n = inflight[0]
        if n:
            print(ts(), 'Decode batch, #running-req: %d, #full token: 1, full token usage: 0.10, accept len: %.2f, accept rate: 0.55, cuda graph: True, gen throughput (token/s): %.1f, #queue-req: 0'
                  % (n, 2.6 if frspec else 2.8, 500.0 if frspec else 555.0), flush=True)
threading.Thread(target=logger, daemon=True).start()
ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
