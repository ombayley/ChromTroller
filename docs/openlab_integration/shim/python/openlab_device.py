#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CT-side client for the OpenLab C# shim.

Runs in ChromTroller's normal 64-bit Python. Launches OpenLabShim.exe (32-bit) as a
child process and talks to it over stdin/stdout with a small line protocol. This is the
direct replacement for the Arduino-backed LCMSDevice: same "send command / read
response" shape, but the device underneath calls the OpenLab Acquisition SDK.

Design:
  * Policy (method library, defaults, whitelist, ranges) lives HERE - validated before
    anything reaches the instrument.
  * Instrument internals (module hashkeys, firmware strings, property ids) live in the
    shim's config, never here.
  * Synchronous replies (OK/ERR) are matched to commands; asynchronous run events
    (EVENT/RESULT) are delivered to an on_event callback by a background reader thread.

Intended home once integrated: src/hrd_control/devices/openlab_device.py
"""

import json
import re
import queue
import subprocess
import threading
from typing import Callable, Dict, Optional


# --------------------------------------------------------------------------- policy
# Logical method names -> actual method paths on the Acquisition PC. The client picks a
# name; CT resolves it so the client never needs to know AIC filesystem paths.
METHODS: Dict[str, str] = {
    "fast_gradient":   r"C:\CDSProjects\RoboChem\Methods\fast_gradient.amx",
    "isocratic_short": r"C:\CDSProjects\RoboChem\Methods\isocratic_short.amx",
}

# Defaults applied when the client omits a field.
DEFAULTS: Dict[str, object] = {
    "method":     "fast_gradient",
    "vial":       "P1-A1",
    "injvol":     1.0,
    "processing": r"C:\CDSProjects\RoboChem\Methods\standard.pmx",
}

# Simple per-run overrides the client may set: name -> validator(value) -> bool.
OVERRIDE_WHITELIST: Dict[str, Callable[[object], bool]] = {
    "method": lambda v: v in METHODS,
    "vial":   lambda v: bool(re.match(r"^P\d+-[A-H]\d+$", str(v))),
    "injvol": lambda v: 0.0 < float(v) <= 20.0,
}

# Deep method parameters (resource properties) the client may tune: name -> (lo, hi).
# Must match the keys in the shim config's ParamMap.
PARAM_WHITELIST: Dict[str, tuple] = {
    "flow":     (0.05, 2.0),    # mL/min
    "col_temp": (4.0, 80.0),    # degC
}

VALVE_POSITIONS = {"load", "inject"}


class ShimError(RuntimeError):
    """Raised when the shim returns ERR/FATAL or fails to respond."""


class OpenLabDevice:
    """Persistent client for OpenLabShim.exe."""

    def __init__(
        self,
        exe_path: str,
        config_path: str,
        on_event: Optional[Callable[[str, str], None]] = None,
        response_timeout: float = 120.0,
        ready_timeout: float = 180.0,
    ) -> None:
        self._exe = exe_path
        self._config = config_path
        self._on_event = on_event           # called as on_event(kind, payload) for EVENT/RESULT
        self._timeout = response_timeout
        self._ready_timeout = ready_timeout
        self._proc: Optional[subprocess.Popen] = None
        self._responses: "queue.Queue[str]" = queue.Queue()
        self._reader: Optional[threading.Thread] = None
        self._cmd_lock = threading.Lock()   # serialise command/response round-trips

    # ----------------------------------------------------------------- lifecycle
    def start(self) -> None:
        """Launch the shim and block until it reports READY (connected + control taken)."""
        self._proc = subprocess.Popen(
            [self._exe, self._config],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,                      # line-buffered
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        line = self._next_response(self._ready_timeout)
        if line != "READY":
            raise ShimError(f"shim did not start cleanly: {line!r}")

    def close(self) -> None:
        """Ask the shim to quit; force-kill if it does not exit promptly."""
        try:
            if self._proc and self._proc.poll() is None:
                self._send("QUIT")
                self._proc.wait(timeout=10)
        except Exception:
            if self._proc:
                self._proc.kill()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.close()

    # ----------------------------------------------------------------- public API
    def ping(self) -> str:
        return self._cmd("PING")

    def set_valve(self, position: str) -> str:
        """Switch the built-in column valve. position in {'load', 'inject'}."""
        if position not in VALVE_POSITIONS:
            raise ValueError(f"valve position {position!r} not allowed")
        return self._cmd(f"SET_VALVE {position}")

    def submit_run(self, request: dict, result_path: str) -> str:
        """
        Validate a client run request against defaults + whitelist, then submit it.
        Returns the run id (used to match EVENT/RESULT callbacks).

        request example:
            {"method": "isocratic_short", "vial": "P1-B3", "params": {"flow": 0.5}}
        """
        merged = {**DEFAULTS,
                  **{k: request[k] for k in OVERRIDE_WHITELIST if k in request}}

        for key, ok in OVERRIDE_WHITELIST.items():
            if not ok(merged[key]):
                raise ValueError(f"override {key}={merged[key]!r} rejected")

        # Whitelisted deep params are staged first, one SET_PARAM each.
        for name, val in request.get("params", {}).items():
            if name not in PARAM_WHITELIST:
                raise ValueError(f"param {name!r} not on whitelist")
            lo, hi = PARAM_WHITELIST[name]
            if not (lo <= float(val) <= hi):
                raise ValueError(f"param {name}={val} out of range [{lo}, {hi}]")
            self._cmd(f"SET_PARAM {name}={val}")

        payload = json.dumps({
            "method":     METHODS[merged["method"]],
            "processing": merged["processing"],
            "vial":       merged["vial"],
            "injvol":     float(merged["injvol"]),
            "result":     result_path,
        })
        return self._cmd("START_RUN " + payload)   # -> run id

    def abort(self) -> str:
        return self._cmd("ABORT")

    def status(self) -> str:
        return self._cmd("STATUS")

    # ----------------------------------------------------------------- internals
    def _cmd(self, line: str) -> str:
        with self._cmd_lock:
            self._send(line)
            reply = self._next_response(self._timeout)
        verb, _, rest = reply.partition(" ")
        if verb == "OK":
            return rest
        # ERR / FATAL / anything unexpected
        raise ShimError(rest or reply)

    def _send(self, line: str) -> None:
        if not self._proc or self._proc.poll() is not None:
            raise ShimError("shim process is not running")
        assert self._proc.stdin is not None
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()

    def _next_response(self, timeout: float) -> str:
        try:
            return self._responses.get(timeout=timeout)
        except queue.Empty:
            raise ShimError("timeout waiting for shim response")

    def _read_loop(self) -> None:
        """Background: classify stdout lines into async events vs command responses."""
        assert self._proc is not None and self._proc.stdout is not None
        for raw in self._proc.stdout:
            line = raw.rstrip("\n")
            if not line:
                continue
            if line.startswith("EVENT ") or line.startswith("RESULT "):
                if self._on_event:
                    kind, _, payload = line.partition(" ")
                    try:
                        self._on_event(kind, payload)
                    except Exception:
                        pass            # never let a callback kill the reader
            else:
                # OK / ERR / FATAL / READY -> synchronous response stream
                self._responses.put(line)
