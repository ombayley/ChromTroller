#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal end-to-end demo of the OpenLabDevice client driving the shim.

Mirrors the target ChromTroller workflow:
    set valve to load -> (client fills loop) -> submit run -> await completion -> analyse.
"""

import threading
from openlab_device import OpenLabDevice, ShimError

# Run completion is signalled asynchronously via the on_event callback.
_done = threading.Event()
_result = {}


def on_event(kind: str, payload: str) -> None:
    # kind is "EVENT" or "RESULT"
    if kind == "EVENT":
        # payload e.g. "RUN <id> Acquiring"  or  "STATE Run"
        print("status:", payload)
    elif kind == "RESULT":
        run_id, _, path = payload.partition(" ")
        _result["run_id"] = run_id
        _result["path"] = path
        print("result ready:", run_id, "->", path)
        _done.set()


def main() -> None:
    dev = OpenLabDevice(
        exe_path=r"C:\RoboChem\shim\OpenLabShim.exe",
        config_path=r"C:\RoboChem\shim\shim.config.json",
        on_event=on_event,
    )
    dev.start()                           # blocks until READY
    try:
        print("ping:", dev.ping())

        # 1. valve to load (the external process now fills the loop)
        dev.set_valve("load")

        # 2. ... client fills the sample loop here (variable duration) ...

        # 3. submit the run (method switches valve -> inject at t=0, then acquires)
        run_id = dev.submit_run(
            request={"method": "isocratic_short", "vial": "P1-B3", "params": {"flow": 0.5}},
            result_path=r"C:\CDSProjects\RoboChem\Results\run001",
        )
        print("submitted run:", run_id)

        # 4. wait for completion, then hand the .dx to the MOCCA pipeline
        if not _done.wait(timeout=3600):
            raise ShimError("run did not complete in time")
        print("analyse:", _result["path"])   # -> feed to src/analysis/ct_analyser.py

    except ShimError as e:
        print("shim error:", e)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
