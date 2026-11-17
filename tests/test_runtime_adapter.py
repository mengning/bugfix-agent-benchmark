from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO

from bugfix_benchmark.models import BenchmarkCase
from bugfix_benchmark.runtime_adapter import DevStarRuntimeAdapter


class RuntimeHandler(BaseHTTPRequestHandler):
    requests: list[dict] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        self.requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        self._send({"events": [{"event_id": 42, "target_registration_id": 8}]})

    def do_GET(self):
        self.requests.append({"path": self.path, "auth": self.headers.get("Authorization")})
        self._send({"event_id": 42, "status": "success", "result": {
            "artifact": {"case_id": "case-1", "patch": "diff --git a/a b/a\n"}
        }})

    def _send(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, _format, *_args):
        pass


class DevStarRuntimeAdapterTests(unittest.TestCase):
    def test_http_error_does_not_expose_response_body(self):
        secret = "example-sensitive-response"
        adapter = DevStarRuntimeAdapter(base_url="http://localhost", token="token",
                                        workspace=Path("."))
        failure = HTTPError("http://localhost", 403, "forbidden", {}, BytesIO(secret.encode()))
        with patch("bugfix_benchmark.runtime_adapter.urlopen", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                adapter._request("GET", "/test")
        self.assertIn("HTTP 403", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_dispatches_to_current_instance_and_reads_its_patch(self):
        RuntimeHandler.requests = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), RuntimeHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory) / "workspace"
                workspace.mkdir()
                subprocess.run(["git", "init", "--quiet"], cwd=workspace, check=True)
                case = BenchmarkCase(
                    case_id="case-1", repository="owner/repo", base_commit="",
                    problem_statement="Fix the bug", source_url="https://example.invalid/repo.git",
                )
                adapter = DevStarRuntimeAdapter(
                    base_url=f"http://127.0.0.1:{server.server_port}",
                    token="instance-secret", workspace=workspace, timeout_seconds=1,
                    poll_seconds=0.01,
                )
                artifact = adapter.run(case)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

        self.assertEqual("diff --git a/a b/a\n", artifact.patch)
        self.assertEqual("Bearer instance-secret", RuntimeHandler.requests[0]["auth"])
        self.assertEqual("/-/agent-services/instances/dispatch", RuntimeHandler.requests[0]["path"])
        self.assertEqual("/-/agent-services/events/42/result", RuntimeHandler.requests[1]["path"])
        request = RuntimeHandler.requests[0]["body"]
        self.assertTrue(request["target_self"])
        self.assertEqual("/evaluate-case", request["command"])
        self.assertEqual(str(workspace.resolve()), request["metadata"]["workspace"]["path"])
        self.assertEqual("", request["metadata"]["evaluation"]["base_commit"])


if __name__ == "__main__":
    unittest.main()
