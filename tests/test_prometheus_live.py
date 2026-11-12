"""Optional real Prometheus scrape against the gateway on loopback."""
import os
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(os.getenv("BOTKERNEL_PROMETHEUS_TEST_BINARY"), "requires a local Prometheus binary")
class PrometheusScrapeTests(unittest.TestCase):
    def test_scoped_secret_scrapes_and_rejects_rotated_token(self):
        import httpx
        import uvicorn

        operator, metrics = "operator-" + "x" * 50, "metrics-" + "y" * 50
        settings = {
            "BOTKERNEL_OPERATOR_TOKEN": operator, "BOTKERNEL_OPERATOR_TOKEN_FILE": "",
            "BOTKERNEL_AGENT_TOKEN": "", "BOTKERNEL_AGENT_TOKEN_FILE": "",
            "BOTKERNEL_METRICS_TOKEN": metrics, "BOTKERNEL_METRICS_TOKEN_FILE": "",
        }
        with patch.dict(os.environ, settings), tempfile.TemporaryDirectory() as directory:
            from botkernel.api import app
            from botkernel.observability import REGISTRY

            root = Path(directory)
            credential = root / "metrics-token"
            credential.write_text(metrics, encoding="utf-8")
            api_port, prom_port = _port(), _port()
            while prom_port == api_port:
                prom_port = _port()
            source = Path("observability/prometheus.yml").read_text(encoding="utf-8")
            source = source.split("  - job_name: background", 1)[0]
            source = (source.replace("scrape_interval: 5s", "scrape_interval: 1s")
                      .replace("scrape_timeout: 4s", "scrape_timeout: 1s")
                      .replace("api:8000", f"127.0.0.1:{api_port}")
                      .replace("/run/secrets/metrics_token", str(credential)))
            config = root / "prometheus.yml"
            config.write_text(source, encoding="utf-8")
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port, log_level="error"))
            thread = threading.Thread(target=server.run, daemon=True)
            process = None
            with patch("botkernel.observability.generate_latest",
                       side_effect=lambda registry: b"bk_test_metric 1\n" if registry is REGISTRY else b""):
                try:
                    thread.start()
                    until = time.monotonic() + 10
                    while not server.started and time.monotonic() < until:
                        time.sleep(.05)
                    self.assertTrue(server.started)
                    url = f"http://127.0.0.1:{api_port}/metrics"
                    self.assertEqual(httpx.get(url).status_code, 401)
                    self.assertEqual(httpx.get(url, headers={"Authorization": f"Bearer {metrics}"}).status_code, 200)
                    process = subprocess.Popen([
                        os.environ["BOTKERNEL_PROMETHEUS_TEST_BINARY"],
                        f"--config.file={config}", f"--storage.tsdb.path={root / 'tsdb'}",
                        f"--web.listen-address=127.0.0.1:{prom_port}",
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    def wait_up(expected):
                        until = time.monotonic() + 20
                        while time.monotonic() < until:
                            if process.poll() is not None:
                                self.fail("Prometheus exited before scraping")
                            try:
                                response = httpx.get(f"http://127.0.0.1:{prom_port}/api/v1/query",
                                                     params={"query": 'up{job="gateway"}'}, timeout=1)
                                rows = response.json()["data"]["result"]
                                if rows and rows[0]["value"][1] == expected:
                                    return
                            except (httpx.HTTPError, KeyError, ValueError):
                                pass
                            time.sleep(.25)
                        self.fail(f"Prometheus scrape did not reach up={expected}")

                    wait_up("1")
                    credential.write_text("invalid", encoding="utf-8")
                    wait_up("0")
                    credential.write_text(metrics, encoding="utf-8")
                    wait_up("1")
                finally:
                    if process is not None and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                    server.should_exit = True
                    thread.join(timeout=10)
                    self.assertFalse(thread.is_alive(), "API test server did not stop")


if __name__ == "__main__":
    unittest.main()
