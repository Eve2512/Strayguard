import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from strayguard import jev

KEY = "secret-test-key-123"

class FakeJev(BaseHTTPRequestHandler):
    """Answers with the next item of `script`: 'ok', 'slow', 'bad', 'html' or an HTTP code."""

    script, requests = [], []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeJev.requests.append((dict(self.headers), body))
        action = FakeJev.script.pop(0) if FakeJev.script else "ok"
        if action == "slow":
            time.sleep(1.0)
        if isinstance(action, int):
            self.send_response(action)
            self.end_headers()
            return
        if action == "html":
            payload = b"<html>"
        else:
            answers = {fid: {"choice": "scratch", "probabilities": {"scratch": 0.9}}
                       for fid in body["questions"]}
            if action == "bad":
                answers["f1"] = {"choice": "not-an-option"}
            payload = json.dumps({"answers": answers}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture
def server(monkeypatch):
 

