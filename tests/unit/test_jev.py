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
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeJev)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    FakeJev.script, FakeJev.requests = [], []
    monkeypatch.setattr(jev, "ENDPOINT", f"http://127.0.0.1:{httpd.server_port}")
    monkeypatch.setattr(jev, "REQUEST_TIMEOUT", 0.4)
    monkeypatch.setattr(jev, "TOTAL_TIMEOUT", 0.5)
    yield FakeJev
    httpd.shutdown()


def items(count):
    return [SimpleNamespace(key=f"k{i}", is_folder=False, evidence={"path": f"f{i}.py"})
            for i in range(count)]


def ask(count=2):
    return jev.ask(items(count), ["src/"], KEY, "jev-latest")


def test_request_shape(server):
    assert ask() == {"k0": {"choice": "scratch", "probabilities": {"scratch": 0.9}},
                     "k1": {"choice": "scratch", "probabilities": {"scratch": 0.9}}}
    headers, body = server.requests[0]
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert body["state"]["repo"] == {"top_level": ["src/"]}
    assert list(body["questions"]["f1"]["criteria"])[0] == "belongs"
    assert "`files.f1`" in body["questions"]["f1"]["instructions"]


def test_batches_of_twenty(server):
    assert len(ask(45)) == 45
    assert sorted(len(b["questions"]) for _, b in server.requests) == [5, 20, 20]


def test_retry_once_then_ok(server, monkeypatch):
    monkeypatch.setattr(jev, "TOTAL_TIMEOUT", 3.0)  # the retry waits 1 s first
    server.script = [529]
    assert len(ask()) == 2
    assert len(server.requests) == 2


def test_retry_only_once(server, monkeypatch):  # T-11
    monkeypatch.setattr(jev, "TOTAL_TIMEOUT", 3.0)  # the retry waits 1 s first
    server.script = [529, 529]
    with pytest.raises(jev.JevError, match="HTTP 529"):
        ask()
    assert len(server.requests) == 2


@pytest.mark.parametrize("script, message", [
    ([401], "HTTP 401"), (["slow"], "did not answer"), (["html"], "not JSON"),
])
def test_errors(server, script, message):  # T-12, T-16
    server.script = script
    with pytest.raises(jev.JevError, match=message) as error:
        ask()
    assert KEY not in str(error.value)


def test_invalid_answer_is_dropped(server):
    server.script = ["bad"]
    assert list(ask()) == ["k1"]


def test_no_server(monkeypatch):
    monkeypatch.setattr(jev, "ENDPOINT", "http://127.0.0.1:1")
    with pytest.raises(jev.JevError, match="could not reach Jev"):
        ask()
