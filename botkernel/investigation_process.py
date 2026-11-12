"""Bounded subprocess execution for investigation computations."""
import ctypes
import json
import os
import signal
import subprocess
import sys
import time


class InvestigationTimeout(Exception):
    def __init__(self, pid, returncode):
        super().__init__("investigation execution timed out")
        self.pid = pid
        self.returncode = returncode


def execution_limits():
    try:
        deadline = float(os.getenv("INVESTIGATION_EXECUTION_TIMEOUT_SECONDS", "30"))
        grace = float(os.getenv("INVESTIGATION_TERMINATION_GRACE_SECONDS", "2"))
    except ValueError as error:
        raise ValueError("invalid investigation execution limits") from error
    if not 1 <= deadline <= 45 or not 0.1 <= grace <= 5:
        raise ValueError("invalid investigation execution limits")
    return deadline, grace


def install_parent_death_guard():
    """On Linux, kill this worker if its parent exits, including before setup."""
    expected = int(os.environ["BOTKERNEL_INVESTIGATION_PARENT_PID"])
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, 9, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "cannot install parent-death guard")
    elif os.name != "nt":
        raise RuntimeError("investigation process supervision is unsupported on this platform")
    if os.getppid() != expected:
        os._exit(1)


def _windows_job(process):
    if os.name != "nt":
        return None
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(job, process._handle):
        error = ctypes.get_last_error()
        kernel.CloseHandle(job)
        raise ctypes.WinError(error)
    return job


def run_process(command, payload, deadline, grace, *, env=None):
    child_env = dict(os.environ if env is None else env)
    child_env["BOTKERNEL_INVESTIGATION_PARENT_PID"] = str(os.getpid())
    for name in ("BOTKERNEL_OPERATOR_TOKEN", "BOTKERNEL_AGENT_TOKEN", "BOTKERNEL_METRICS_TOKEN"):
        child_env.pop(name, None)
        child_env.pop(name + "_FILE", None)
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=child_env,
                               start_new_session=(os.name != "nt"))
    job = None

    def terminate(force=False):
        if os.name == "nt":
            if force and job is not None:
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                if not kernel.TerminateJobObject(job, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
            elif process.poll() is None:
                process.kill() if force else process.terminate()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass

    try:
        job = _windows_job(process)
        try:
            stdout, _stderr = process.communicate(payload, timeout=deadline)
        except subprocess.TimeoutExpired:
            terminate()
            if os.name != "nt":
                # Keep the group leader unreaped until any surviving descendants are killed.
                time.sleep(grace)
                terminate(force=True)
                process.communicate()
            else:
                try:
                    process.communicate(timeout=grace)
                except subprocess.TimeoutExpired:
                    terminate(force=True)
                    process.communicate()
            raise InvestigationTimeout(process.pid, process.returncode)
        if process.returncode != 0:
            raise RuntimeError("investigation worker failed")
        return stdout
    finally:
        if process.poll() is None:
            terminate(force=True)
            process.communicate()
        if job is not None:
            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(ctypes.c_void_p(job))


def execute(incident_id, provider, report_id, deadline, grace):
    request = json.dumps({"incident_id": incident_id, "provider": provider, "run_id": report_id}).encode()
    output = run_process([sys.executable, "-m", "botkernel.investigation_worker"], request, deadline, grace)
    if len(output) > 210000:
        raise ValueError("investigation worker response too large")
    return json.loads(output)
