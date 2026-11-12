"""Service-free tests exercise real OS subprocess termination."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from botkernel.investigation_process import InvestigationTimeout, execution_limits, run_process


class InvestigationProcessTests(unittest.TestCase):
    def test_completion_and_recovery_after_worker_failure(self):
        command = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"]
        self.assertEqual(run_process(command, b"report", 5, 1), b"report")
        with self.assertRaises(RuntimeError):
            run_process([sys.executable, "-c", "raise RuntimeError('failure')"], b"", 5, 1)
        self.assertEqual(run_process(command, b"next report", 5, 1), b"next report")

    def test_cpu_bound_worker_is_terminated_and_does_not_write_late(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "heartbeat"
            code = (
                "import os,sys,time; p=sys.argv[1]; n=0; last=0\n"
                "while True:\n"
                " n+=1\n"
                " if time.monotonic()-last>.05:\n"
                "  open(p,'w').write(str(n)); last=time.monotonic()\n"
            )
            started = time.monotonic()
            with self.assertRaises(InvestigationTimeout) as caught:
                run_process([sys.executable, "-c", code, str(marker)], b"", 1.5, 0.3)
            self.assertLess(time.monotonic() - started, 5)
            self.assertIsNotNone(caught.exception.returncode)
            self.assertTrue(marker.exists())
            stopped = marker.read_text()
            time.sleep(.25)
            self.assertEqual(marker.read_text(), stopped)

    def test_timeout_cleans_up_descendant_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "descendant-heartbeat"
            child = (
                "import signal,sys,time\n"
                "signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
                "while True:\n"
                " open(sys.argv[1],'w').write(str(time.monotonic()))\n"
                " time.sleep(.05)\n"
            )
            parent = (
                "import subprocess,sys,time\n"
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                "time.sleep(20)\n"
            )
            with self.assertRaises(InvestigationTimeout):
                run_process([sys.executable, "-c", parent, child, str(marker)], b"", 2, .3)
            self.assertTrue(marker.exists())
            stopped = marker.read_text()
            time.sleep(.3)
            self.assertEqual(marker.read_text(), stopped)

    @unittest.skipIf(os.name == "nt", "Windows terminate is already forceful")
    def test_ignoring_sigterm_requires_forced_kill(self):
        code = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(20)"
        with self.assertRaises(InvestigationTimeout) as caught:
            run_process([sys.executable, "-c", code], b"", 1, .2)
        self.assertEqual(caught.exception.returncode, -9)

    def test_limits_reject_invalid_values(self):
        from unittest.mock import patch
        with patch.dict(os.environ, {"INVESTIGATION_EXECUTION_TIMEOUT_SECONDS": "nan"}):
            with self.assertRaises(ValueError):
                execution_limits()
        with patch.dict(os.environ, {"INVESTIGATION_EXECUTION_TIMEOUT_SECONDS": "46"}):
            with self.assertRaises(ValueError):
                execution_limits()

    def test_worker_stops_when_its_supervisor_dies(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "heartbeat"
            child = (
                "from botkernel.investigation_process import install_parent_death_guard\n"
                "import sys,time\n"
                "install_parent_death_guard()\n"
                "sys.stdin.read()\n"
                "while True:\n"
                " open(sys.argv[1],'w').write(str(time.monotonic()))\n"
                " time.sleep(.05)\n"
            )
            parent = (
                "from botkernel.investigation_process import run_process\n"
                "import sys\n"
                "run_process([sys.executable,'-c',sys.argv[1],sys.argv[2]],b'',20,1)\n"
            )
            supervisor = subprocess.Popen([sys.executable, "-c", parent, child, str(marker)])
            try:
                until = time.monotonic() + 10
                while not marker.exists() and time.monotonic() < until:
                    time.sleep(.05)
                self.assertTrue(marker.exists(), "worker did not start")
                supervisor.kill()
                supervisor.wait(timeout=5)
                time.sleep(.3)
                stopped = marker.read_text()
                time.sleep(.3)
                self.assertEqual(marker.read_text(), stopped)
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                    supervisor.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
