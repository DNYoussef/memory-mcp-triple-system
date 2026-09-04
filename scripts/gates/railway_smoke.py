#!/usr/bin/env python
"""Build and smoke the Railway image against a host embedding stub."""

import json
from contextlib import contextmanager
import os
import shutil
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
TOKEN = "RAILWAY_SMOKE_OK image_build=1 runtime_contract=1 backend=lightweight embed_batch=1 canary_search=1 canary_unified=1 wrong_key=401"
RECEIPT = REPO / "audits" / "railway-remote-2026-09-04.json"


class Response:
    def __init__(self, status, data):
        self.status_code = status
        self.data = data
        self.text = json.dumps(data)

    def json(self):
        return self.data


class Client:
    def __init__(self, base, key, embed_base):
        self.base = base
        self.key = key
        self.embed_base = embed_base
        self.canary = None
        self.image_build = True

    def request(self, method, path, body=None, key=None):
        raw = json.dumps(body).encode("ascii") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if key is not False:
            headers["X-MCP-API-Key"] = key or self.key
        request = urllib.request.Request(self.base + path, raw, headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return Response(response.status, json.loads(response.read() or b"{}"))
        except urllib.error.HTTPError as exc:
            return Response(exc.code, {})
        except urllib.error.URLError:
            return Response(0, {})

    def get(self, path, **kwargs):
        return self.request("GET", path, key=kwargs.get("key"))

    def post(self, path, body, **kwargs):
        return self.request("POST", path, body, kwargs.get("key"))

    def embedding_batch_seen(self):
        try:
            with urllib.request.urlopen(
                self.embed_base + "/stats", timeout=5
            ) as response:
                return json.loads(response.read())["max_batch"] > 1
        except (OSError, ValueError, KeyError):
            return False


def probe(client) -> bool:
    canary = client.canary or "RAILWAY-GATE-CANARY"
    health = client.get("/health", key=False)
    health_data = health.json()
    store = client.post(
        "/tools/memory_store",
        {
            "text": canary,
            "metadata": {
                "who": "gate",
                "when": "2026-09-03",
                "project": "memory-mcp",
                "why": "smoke",
            },
        },
    )
    companion = client.post(
        "/tools/memory_store",
        {
            "text": "RAILWAY-BATCH-" + canary[-16:],
            "metadata": {
                "who": "gate",
                "when": "2026-09-04",
                "project": "memory-mcp",
                "why": "embedding-batch-smoke",
            },
        },
    )
    search = client.post("/tools/search", {"query": canary, "limit": 5})
    unified = client.post(
        "/tools/unified_retrieve",
        {"query": canary, "mode": "planning", "token_budget": 1000},
    )
    wrong = client.post("/tools/search", {"query": canary}, key="wrong-key")
    lightweight = health_data.get(
        "bayesian_backend"
    ) == "lightweight" and "lightweight" in str(
        health_data.get("components", {}).get("bayesian", "")
    )
    return (
        health.status_code == 200
        and store.status_code == 200
        and search.status_code == 200
        and canary in search.text
        and unified.status_code == 200
        and canary in unified.text
        and wrong.status_code == 401
        and lightweight
        and companion.status_code == 200
        and client.embedding_batch_seen()
        and client.image_build
    )


class FakeClient:
    canary = "canary"
    image_build = True

    def __init__(self, bad=None):
        self.bad = bad
        if bad == "remote":
            self.image_build = False

    def get(self, path, **kwargs):
        if self.bad == "health":
            return Response(500, {})
        if self.bad == "backend":
            return Response(
                200,
                {"bayesian_backend": "pgmpy", "components": {"bayesian": "available"}},
            )
        return Response(
            200,
            {
                "bayesian_backend": "lightweight",
                "components": {"bayesian": "available (lightweight)"},
            },
        )

    def embedding_batch_seen(self):
        return self.bad != "embed"

    def post(self, path, body, **kwargs):
        if kwargs.get("key") == "wrong-key":
            return Response(200 if self.bad == "auth" else 401, {})
        if self.bad == "store" and path == "/tools/memory_store":
            return Response(500, {})
        if path == "/tools/memory_store":
            return Response(200, {"chunks_stored": 1})
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
            "remote",
        )
    ]


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_http(client, process=None, error_log=None):
    for _ in range(90):
        if client.get("/health", key=False).status_code == 200:
            return
        if process is not None and process.poll() is not None:
            error_log.seek(0)
            error = error_log.read()
            raise RuntimeError(f"HTTP server exited during startup: {error[-2000:]}")
        time.sleep(1)
    raise RuntimeError("HTTP server did not become healthy within 90 seconds")


def _stop(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _cleanup_dir(path):
    for attempt in range(20):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if attempt == 19:
                raise
            time.sleep(0.25)


@contextmanager
def _docker_fixture():
    embed_port, http_port = _port(), _port()
    image = f"memory-mcp-gate-{uuid.uuid4().hex[:10]}"
    container = f"memory-mcp-gate-{uuid.uuid4().hex[:10]}"
    key = uuid.uuid4().hex
    canary = f"RAILWAY-{uuid.uuid4().hex}"
    stub = subprocess.Popen(
        [sys.executable, "scripts/gates/_embed_stub.py", "--port", str(embed_port)],
        cwd=REPO,
    )
    built = False
    try:
        build = subprocess.run(
            ["docker", "build", "-f", "Dockerfile.railway", "-t", image, "."], cwd=REPO
        )
        if build.returncode:
            yield FakeClient(bad="health")
            return
        built = True
        run = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container,
                "--add-host=host.docker.internal:host-gateway",
                "-e",
                f"EMBEDDING_API_BASE=http://host.docker.internal:{embed_port}/v1",
                "-e",
                f"MEMORY_MCP_API_KEY={key}",
                "-e",
                "MEMORY_MCP_DATA_DIR=/data",
                "--tmpfs",
                "/data:rw",
                "-p",
                f"{http_port}:8080",
                image,
            ],
            cwd=REPO,
            capture_output=True,
        )
        if run.returncode:
            yield FakeClient(bad="health")
            return
        client = Client(
            f"http://127.0.0.1:{http_port}",
            key,
            f"http://127.0.0.1:{embed_port}",
        )
        client.canary = canary
        _wait_for_http(client)
        yield client
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
        if built:
            subprocess.run(["docker", "image", "rm", "-f", image], capture_output=True)
        _stop(stub)


@contextmanager
def _host_fixture():
    embed_port, http_port = _port(), _port()
    key = uuid.uuid4().hex
    data = Path(tempfile.mkdtemp(prefix="mmts-railway-host-"))
    error_log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "CHROMA_PERSIST_DIR": str(data / "chroma"),
            "EMBEDDING_API_BASE": f"http://127.0.0.1:{embed_port}/v1",
            "EMBEDDING_API_DIMENSIONS": "384",
            "EMBEDDING_API_MODEL": "text-embedding-3-small",
            "EMBEDDING_MODE": "api",
            "MEMORY_MCP_API_KEY": key,
            "MEMORY_MCP_BAYESIAN_BACKEND": "lightweight",
            "MEMORY_MCP_DATA_DIR": str(data),
            "PORT": str(http_port),
        }
    )
    stub = subprocess.Popen(
        [sys.executable, "scripts/gates/_embed_stub.py", "--port", str(embed_port)],
        cwd=REPO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    server = subprocess.Popen(
        [sys.executable, "-m", "src.mcp.http_server"],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=error_log,
        text=True,
    )
    try:
        client = Client(
            f"http://127.0.0.1:{http_port}",
            key,
            f"http://127.0.0.1:{embed_port}",
        )
        client.canary = f"RAILWAY-{uuid.uuid4().hex}"
        _wait_for_http(client, server, error_log)
        yield client
    finally:
        _stop(server)
        _stop(stub)
        error_log.close()
        _cleanup_dir(data)


def _run_quiet(args):
    try:
        return subprocess.run(args, cwd=REPO, text=True, capture_output=True)
    except OSError as error:
        return subprocess.CompletedProcess(args, 127, "", str(error))


def _docker_available():
    return _run_quiet(["docker", "info"]).returncode == 0


def _remote_build_ok():
    try:
        receipt = json.loads(RECEIPT.read_text(encoding="ascii"))
    except (OSError, ValueError):
        return False
    if receipt.get("status") != "SUCCESS":
        return False
    source = receipt.get("source_head", "")
    if _run_quiet(["git", "cat-file", "-e", f"{source}^{{commit}}"]).returncode:
        return False
    inputs = [
        "Dockerfile.railway",
        "requirements-api.txt",
        "railway.toml",
        ".dockerignore",
        "src",
        "config",
    ]
    worktree = _run_quiet(["git", "status", "--porcelain", "--", *inputs])
    if worktree.returncode or worktree.stdout.strip():
        return False
    unchanged = _run_quiet(["git", "diff", "--quiet", source, "--", *inputs])
    if unchanged.returncode:
        return False
    run = _run_quiet(
        [
            "railway.cmd" if os.name == "nt" else "railway",
            "deployment",
            "list",
            "--service",
            receipt["service"],
            "--environment",
            receipt["environment"],
            "--limit",
            "20",
            "--json",
        ]
    )
    if run.returncode:
        return False
    try:
        deployments = json.loads(run.stdout)
    except ValueError:
        return False
    deployment = next(
        (item for item in deployments if item.get("id") == receipt.get("deployment")),
        None,
    )
    if not deployment or deployment.get("status") != "SUCCESS":
        return False
    if deployment.get("meta", {}).get("cliMessage") != f"Memory MCP source {source}":
        return False
    build = deployment.get("meta", {}).get("serviceManifest", {}).get("build", {})
    if build.get("builder") != "DOCKERFILE" or not build.get(
        "dockerfilePath", ""
    ).endswith("Dockerfile.railway"):
        return False
    try:
        with urllib.request.urlopen(receipt["health_url"], timeout=20) as response:
            health = json.loads(response.read())
    except (OSError, ValueError, KeyError):
        return False
    return health.get("bayesian_backend") == "lightweight"


@contextmanager
def _real_fixture():
    docker = _docker_available()
    with _docker_fixture() if docker else _host_fixture() as client:
        client.image_build = docker or _remote_build_ok()
        yield client


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
