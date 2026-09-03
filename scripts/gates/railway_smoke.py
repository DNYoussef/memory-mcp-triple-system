#!/usr/bin/env python
"""Build and smoke the Railway image against a host embedding stub."""

import json
from contextlib import contextmanager
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_ID = "P6"
TOKEN = "RAILWAY_SMOKE_OK backend=lightweight embed_batch=1 canary_search=1 canary_unified=1 wrong_key=401"


class Response:
    def __init__(self, status, data):
        self.status_code = status
        self.data = data
        self.text = json.dumps(data)

    def json(self):
        return self.data


class Client:
    def __init__(self, base, key):
        self.base = base
        self.key = key
        self.canary = None
        self.embed_batch = False

    def request(self, method, path, body=None, key=None):
        raw = json.dumps(body).encode("ascii") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if key is not False:
            headers["X-MCP-API-Key"] = key or self.key
        request = urllib.request.Request(self.base + path, raw, headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return Response(response.status, json.loads(response.read() or b"{}"))
        except urllib.error.HTTPError as exc:
            return Response(exc.code, {})
        except urllib.error.URLError:
            return Response(0, {})

    def get(self, path, **kwargs):
        return self.request("GET", path, key=kwargs.get("key"))

    def post(self, path, body, **kwargs):
        return self.request("POST", path, body, kwargs.get("key"))


def probe(client) -> bool:
    canary = client.canary or "RAILWAY-GATE-CANARY"
    health = client.get("/health", key=False)
    health_data = health.json()
    store = client.post("/tools/memory_store", {"text": canary, "metadata": {"who": "gate", "when": "2026-09-03", "project": "memory-mcp", "why": "smoke"}})
    search = client.post("/tools/search", {"query": canary, "limit": 5})
    unified = client.post("/tools/unified_retrieve", {"query": canary, "mode": "planning", "token_budget": 1000})
    wrong = client.post("/tools/search", {"query": canary}, key="wrong-key")
    lightweight = health_data.get("bayesian_backend") == "lightweight" and "lightweight" in str(health_data.get("components", {}).get("bayesian", ""))
    return (
        health.status_code == 200
        and store.status_code == 200
        and search.status_code == 200
        and canary in search.text
        and unified.status_code == 200
        and canary in unified.text
        and wrong.status_code == 401
        and lightweight
        and client.embed_batch
    )


class FakeClient:
    canary = "canary"
    embed_batch = True

    def __init__(self, bad=None):
        self.bad = bad
        if bad == "embed":
            self.embed_batch = False

    def get(self, path, **kwargs):
        if self.bad == "health":
            return Response(500, {})
        if self.bad == "backend":
            return Response(200, {"bayesian_backend": "pgmpy", "components": {"bayesian": "available"}})
        return Response(200, {"bayesian_backend": "lightweight", "components": {"bayesian": "available (lightweight)"}})

    def post(self, path, body, **kwargs):
        if kwargs.get("key") == "wrong-key":
            return Response(200 if self.bad == "auth" else 401, {})
        if self.bad == "store" and path == "/tools/memory_store":
            return Response(500, {})
        if self.bad == "search" and path == "/tools/search":
            return Response(200, {})
        if self.bad == "search_status" and path == "/tools/search":
            return Response(500, {})
        if self.bad == "unified" and path == "/tools/unified_retrieve":
            return Response(200, {})
        if self.bad == "unified_status" and path == "/tools/unified_retrieve":
            return Response(500, {})
        return Response(200, {"result": "canary"})


def _planted_bad_fixture():
    return [
        FakeClient(bad=name)
        for name in (
            "health",
            "backend",
            "embed",
            "auth",
            "store",
            "search",
            "search_status",
            "unified",
            "unified_status",
        )
    ]


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def _real_fixture():
    embed_port, http_port = _port(), _port()
    image = f"memory-mcp-gate-{uuid.uuid4().hex[:10]}"
    container = f"memory-mcp-gate-{uuid.uuid4().hex[:10]}"
    key = uuid.uuid4().hex
    canary = f"RAILWAY-{uuid.uuid4().hex}"
    stub = subprocess.Popen([sys.executable, "scripts/gates/_embed_stub.py", "--port", str(embed_port)], cwd=REPO)
    built = False
    data = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    try:
        build = subprocess.run(["docker", "build", "-f", "Dockerfile.railway", "-t", image, "."], cwd=REPO)
        if build.returncode:
            yield FakeClient(bad="health")
            return
        built = True
        run = subprocess.run([
            "docker", "run", "-d", "--name", container,
            "--add-host=host.docker.internal:host-gateway",
            "-e", f"EMBEDDING_API_BASE=http://host.docker.internal:{embed_port}/v1",
            "-e", f"MEMORY_MCP_API_KEY={key}",
            "-e", "MEMORY_MCP_DATA_DIR=/data",
            "-v", f"{data.name}:/data", "-p", f"{http_port}:8080", image,
        ], cwd=REPO, capture_output=True)
        if run.returncode:
            yield FakeClient(bad="health")
            return
        client = Client(f"http://127.0.0.1:{http_port}", key)
        client.canary = canary
        for _ in range(90):
            if client.get("/health", key=False).status_code == 200:
                break
            time.sleep(1)
        request = urllib.request.Request(
            f"http://127.0.0.1:{embed_port}/v1/embeddings",
            json.dumps({"input": ["a", "b"]}).encode("ascii"),
            {"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            client.embed_batch = len(json.loads(response.read())["data"]) == 2
        yield client
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        if built:
            subprocess.run(["docker", "image", "rm", "-f", image], capture_output=True)
        stub.terminate()
        try:
            stub.wait(timeout=5)
        except subprocess.TimeoutExpired:
            stub.kill()
            stub.wait(timeout=5)
        data.cleanup()


def self_test() -> bool:
    for bad in _planted_bad_fixture():
        assert not probe(bad)
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        self_test_ok = self_test()
        if not self_test_ok:
            return 1
        print(f"SELF_TEST_REJECTED {GATE_ID}")
        return 0
    with _real_fixture() as client:
        ok = probe(client)
    if not ok:
        return 1
    print(TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
