#!/usr/bin/env python
"""Small deterministic OpenAI-compatible embedding endpoint for smoke tests."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def embedding(text):
    vector = [0.0] * 384
    for byte in text.encode("utf-8"):
        vector[byte] += 1.0
    return vector


class Handler(BaseHTTPRequestHandler):
    max_batch = 0

    def do_GET(self):
        if self.path.rstrip("/") != "/stats":
            self.send_error(404)
            return
        raw = json.dumps({"max_batch": type(self).max_batch}).encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path.rstrip("/") not in ("/embeddings", "/v1/embeddings"):
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(size) or b"{}")
        texts = body.get("input", [])
        if isinstance(texts, str):
            texts = [texts]
        type(self).max_batch = max(type(self).max_batch, len(texts))
        payload = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": index, "embedding": embedding(text)}
                for index, text in enumerate(texts)
            ],
            "model": body.get("model", "gate-stub"),
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }
        raw = json.dumps(payload).encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
