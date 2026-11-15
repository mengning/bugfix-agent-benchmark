from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
import unittest

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
                case = BenchmarkCase.from_record({
                    "case_id": "case-1", "repository": "owner/repo",
                    "source_path": "fixture", "base_commit": "fixture-v1",
                    "problem_statement": "Fix the bug", "fail_to_pass": ["false"],
                })
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
