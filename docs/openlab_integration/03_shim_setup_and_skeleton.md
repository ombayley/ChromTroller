# OpenLab Shim: Setup, Concepts, and Skeleton

This guide gets you from nothing to a running **C# shim** that drives the Agilent 1290 via
the OpenLab Acquisition SDK, controlled from ChromTroller's normal **64-bit Python**. It
covers environment setup, how the pieces fit together, and the full skeleton code.

**The skeleton files (all the code) live alongside this guide:**

```
docs/openlab_integration/shim/
  OpenLabShim/
    OpenLabShim.csproj      # x86 / net48 build definition + SDK references
    Program.cs              # the shim: connect, take control, dispatch loop, events
    shim.config.json        # discovered values (IDs, valve firmware cmds, param map)
  python/
    openlab_device.py       # CT-side client (default + whitelist policy lives here)
    example_usage.py        # minimal end-to-end demo
```

- C# shim: [Program.cs](shim/OpenLabShim/Program.cs), [OpenLabShim.csproj](shim/OpenLabShim/OpenLabShim.csproj), [shim.config.json](shim/OpenLabShim/shim.config.json)
- Python client: [openlab_device.py](shim/python/openlab_device.py), [example_usage.py](shim/python/example_usage.py)

---

## 1. How it works (conceptually)

```
RoboChem client ──TCP──► ChromTroller (64-bit Python)
                            │  stdin/stdout line protocol
                            ▼
                       OpenLabShim.exe (x86 .NET 4.8)  ← the ONLY 32-bit component
                            │  in-process SDK calls
                            ▼
                       OpenLab Acquisition ──► 1290 Infinity II
```

**Why a separate process at all.** The OpenLab Acquisition assemblies are **x86 /
.NET Framework**. Loading them *in-process* would force ChromTroller itself to be 32-bit
(breaking MOCCA/numpy). Putting them in a **separate process** decouples bitness: a 64-bit
and a 32-bit process coexist fine and just exchange text. The shim is the same architectural
role the Arduino plays today — an out-of-process device CT talks to over a line protocol —
only it calls the real SDK instead of toggling pins.

**Why it's persistent.** Connecting to the instrument is a slow, stateful handshake
(authenticate → `EstablishConnection` → wait for `AppInitialized` + `InstrumentStateChange`)
and run progress arrives as **events**. So the shim connects **once** at startup, takes
control, then loops reading commands. One process, many commands — exactly like opening a
serial port once.

**Two output channels on one pipe.** Every command gets a synchronous `OK ...` / `ERR ...`
reply. Run progress is *unsolicited*: `EVENT ...` lines during the run and a final
`RESULT <id> <path>`. The Python client's reader thread classifies the two — replies go to a
response queue the command call blocks on; events go to a callback CT uses to stream status
and detect completion.

**Where policy lives.** ChromTroller owns the *policy* — the method library, defaults, which
overrides are allowed and their ranges (the `default + whitelist` design). The shim owns the
*SDK mapping* — module hashkeys, the valve's firmware string, which property id a logical
param maps to. The client only ever uses logical names; instrument internals never leak out.

---

## 2. The line protocol

| Direction | Message | Meaning |
|---|---|---|
| CT → shim | `PING` | liveness check → `OK pong` |
| CT → shim | `SET_VALVE load` / `SET_VALVE inject` | switch built-in valve (firmware command) |
| CT → shim | `SET_PARAM flow=0.5` | stage a whitelisted deep method override |
| CT → shim | `START_RUN {json}` | submit a run (json: method, processing, vial, injvol, result) |
| CT → shim | `ABORT` | abort current run |
| CT → shim | `STATUS` | current instrument state |
| CT → shim | `QUIT` | disconnect and exit |
| shim → CT | `READY` | connected + control taken (emitted once at startup) |
| shim → CT | `OK <payload>` / `ERR <msg>` | synchronous reply to the last command |
| shim → CT | `EVENT STATE <state>` / `EVENT RUN <id> <status>` | async progress |
| shim → CT | `RESULT <id> <path>` | run complete; `.dx` result path |
| shim → CT | `FATAL <msg>` | startup/connection failure |

`START_RUN` uses a JSON payload (not space-delimited tokens) so method paths with spaces
escape cleanly.

---

## 3. Environment setup

### 3.1 Prerequisites (on the Acquisition PC / AIC)

- [ ] OpenLab CDS 2.8 **Acquisition** installed; the 1290 is configured and controllable
      from the OpenLab UI.
- [ ] **OpenLab SDK entitlement licensed** (Control Panel → Administration → Licenses).
      Without it `EstablishConnection` fails.
- [ ] You can read the **Instrument GUID** and **Project GUID** from the OpenLab Control
      Panel (used in `shim.config.json`).
- [ ] A service account (login/domain/password) the shim authenticates as.
- [ ] **Bench-discovery values** to fill the config: the column-valve firmware commands for
      each position, and the module-name/property-id for any deep params you expose
      (`flow`, `col_temp`). These come from the discovery script (next deliverable) / Lab
      Advisor — do not guess them.

### 3.2 C# build environment

- Install **Visual Studio 2022** with the **.NET desktop development** workload, *or* the
  **.NET Framework 4.8 Developer Pack** + .NET SDK (for `dotnet build`).
- The project targets **`net48`** and **`PlatformTarget=x86`** — both are mandatory and
  already set in [OpenLabShim.csproj](shim/OpenLabShim/OpenLabShim.csproj).
- Fix the assembly `HintPath`s in the csproj to match your install:
  - The two `Agilent.OpenLAB.Acquisition.*` assemblies are in the **32-bit GAC**. List the
    folder to get the exact version segment:
    ```bat
    dir "C:\Windows\Microsoft.NET\assembly\GAC_32\Agilent.OpenLAB.Acquisition.AutomationInstrument"
    ```
  - `Agilent.OpenLab.SharedServices*` are under
    `C:\Program Files (x86)\Agilent Technologies\OpenLab Services\Common\` and
    `...\OpenLab Acquisition\`.
- Build (x86):
  ```bat
  dotnet build docs\openlab_integration\shim\OpenLabShim\OpenLabShim.csproj -c Release
  ```
  or build the project in Visual Studio with the **x86** configuration. Output:
  `OpenLabShim.exe`.

> The build does **not** copy the Agilent DLLs locally (`<Private>false</Private>`). At
> runtime they (and their many dependencies) are resolved from the install dirs by the
> `AssemblyResolve` handler in `Program.cs`. Keep the exe on the AIC where those dirs exist.

### 3.3 Python environment

**No new environment.** This is the whole point — ChromTroller's existing **64-bit** env is
untouched. There is no pythonnet, no 32-bit Python, no second conda env.

1. Copy [openlab_device.py](shim/python/openlab_device.py) into
   `src/hrd_control/devices/` when you integrate (it has no third-party dependencies —
   stdlib only).
2. Edit the **policy block** at the top of `openlab_device.py` — `METHODS`, `DEFAULTS`,
   `OVERRIDE_WHITELIST`, `PARAM_WHITELIST` — to match your methods and the knobs you want
   the client to control. Keep the `PARAM_WHITELIST` keys in sync with the shim config's
   `ParamMap`.

### 3.4 Configure the shim

Edit [shim.config.json](shim/OpenLabShim/shim.config.json):

- `Login` / `Domain` / `Password` — the service account. **Do not commit a real password**;
  inject it at deploy time from a secret.
- `InstrumentId` / `ProjectId` — GUIDs from Control Panel.
- `ValveModuleMatch` — a substring of the column-compartment module name (e.g. `"Column Comp"`).
- `ValveFirmware.load` / `.inject` — the discovered firmware command strings.
- `ParamMap` — for each whitelisted deep param, the module-name substring + resource
  property id from discovery.

---

## 4. First run / smoke test

1. Build the shim (§3.2) and fill the config (§3.4).
2. Quick manual check straight from a terminal (type commands, watch replies):
   ```bat
   OpenLabShim.exe shim.config.json
   READY
   PING
   OK pong
   STATUS
   OK Idle
   QUIT
   OK bye
   ```
   If you see `FATAL ...` instead of `READY`, the connection failed — check the SDK
   license, the GUIDs, and that you're on the AIC.
3. End-to-end from Python: edit the paths at the bottom of
   [example_usage.py](shim/python/example_usage.py) and run it in your 64-bit env.
   It does: `set_valve("load")` → `submit_run(...)` → waits for the `RESULT` event.

---

## 5. Integrating into ChromTroller

The shim/client mirror the existing device abstraction, so integration is mostly swapping
the transport:

- Add `src/hrd_control/devices/openlab_device.py` (the client).
- In [ct_controller.py](../../src/hrd_control/ct_controller.py):
  - construct `OpenLabDevice(exe, config, on_event=...)` and `start()` it where the
    Arduino/`LCMSDevice` is set up today;
  - `run_sample_acquisition()` becomes: `set_valve("load")` → (await loop fill) →
    `submit_run(...)` → await the `RESULT` event → hand the `.dx` to
    [ct_analyser.py](../../src/analysis/ct_analyser.py);
  - route `on_event` status lines back to the TCP client.
- Retire the Arduino trigger path (`send_start_request`, ERI reads). Keep the Arduino only
  if the OCB350 phase sensor is still wired through it.
- The file-watch in [ct_monitor.py](../../src/file_mgmnt/ct_monitor.py) can be simplified or
  removed — `RESULT` carries the result path directly.

---

## 6. Known TODOs in the skeleton (confirm against your installed assembly)

These are member names taken from the SDK reference guide; verify when you build (search
`TODO confirm` in `Program.cs`):

- `Connection.TicketContainer.Ticket` — exact accessor for the security ticket string
  (Programmer's Guide, SharedServices section).
- The module name property (`.Name` vs `.DisplayName`) on `ic.Modules`.
- `RunSubmissionResult.RunId` and `RunRecordUpdate.ResultFilePath` field names.
- Whether deep overrides need the `Load → Set → SaveAs` path (used here) or persist into a
  submitted run without the save-as — verify on the bench.
- For **external** injection, whether `InjectionVolume` is meaningful or governed by the
  loop (`InjectionSource.SupportsUseMethodVolume`).

---

*Prerequisite for filling the config: the bench discovery script (valve firmware commands,
module/property ids, instrument/project GUIDs). See the migration report,
[02_chromtroller_migration_report.md](02_chromtroller_migration_report.md), for the overall
plan and phasing.*
