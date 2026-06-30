# ChromTroller Control Box — Assembly Guide

> Hardware build notes for the ChromTroller valve/trigger controller

---

## 📦 Overview

The **ChromTroller control box** is a small microcontroller-based module that:
- Drives a **VICI micro‑electric actuator** to toggle a **two‑position, six‑port** switching valve for sample injection.
- Issues and reads **digital I/O** signals to/from the **Agilent ERI (Enhanced Remote Interface)** on compatible 1290 Infinity II modules to start/stop and monitor runs.
- Optionally interfaces with an **OCB350 phase sensor** for flow-phase monitoring.
- Provides a **fused power path** for the actuator and a front‑panel **power switch**.
- Communicates with the host PC via **USB serial** (Arduino Uno R3).

This ensures the physical injection is **time‑aligned** with UPLC data acquisition, giving reproducible retention times.

---

## 🧰 Bill of Materials (BOM)

| Component | Qty | Supplier | Price (ea) | Part No.      |
|---|---:|---|---:|---------------|
| Arduino Uno R3 | 1 | Conrad | € 16.17 | 191789        |
| Power switch | 1 | Conrad | € 2.30 | 1588060       |
| DC barrel connector 5.5 mm / 2.5 mm | 5 | Conrad | € 1.29 | 1582328       |
| Fuse holder (box) | 1 | Conrad | € 1.49 | 533769        |
| 10 A fuse 5×20 mm (pack of 10) | 1 | ESKA | € 1.49 | 522.627       |
| D‑Sub 9 female | 1 | Conrad | € 0.56 | 1924663‑8J    |
| D‑Sub 9 male | 1 | Conrad | € 0.35 | 1303906‑8J    |
| D‑Sub 15 female | 1 | Conrad | € 0.64 | 1586473‑8J    |
| Module box (print) | 1 | — | — | `LC_ENC.stl`  |
| Module box lid (print) | 1 | — | — | `LC_ENCL.stl` |

*Prices as purchased; may change.*

You will also need hookup wire, crimp pins/hoods for D‑Sub connectors, stand‑offs/screws for the Arduino, and heat‑shrink.

---

## 🧱 Enclosure & Front Panel

- 3D‑print `LC_ENC.stl` (box) and `LC_ENCL.stl` (lid).
- Front panel typical cut‑outs: **power switch**, **fuse holder**, **barrel DC jack(s)**, and **status LEDs** (optional).
- Rear panel typical cut‑outs: **D‑Sub‑15** (ERI), **D‑Sub‑9** (valve/aux), and **USB‑B** (Arduino).

> Keep high‑current actuator wiring physically separated from logic lines to reduce noise. Tie grounds at a single star point.

---

## ⚡ Power & Safety

- The actuator is powered via the fused DC input (**5×20 mm, 10 A**). Size the fuse for your actuator’s supply and inrush.
- The **Arduino** is powered via **USB** from the PC. If you power it from the actuator supply, use a regulated 5 V rail and common ground.
- Use **strain relief** for all external cables.
- **Always disconnect power** before rewiring. Verify polarity and fuse rating before first power‑up.

> **Disclaimer:** You are responsible for safe mains/DC wiring and compliance with your local regulations.

---

## 🔌 Interfaces (High‑level)

- **VICI actuator controller:** digital input for **Position A/B** (check your controller’s manual). The control box outputs logic‑level signals from the Arduino to the actuator controller input. 
- **Agilent ERI (Enhanced Remote Interface):** provides digital **Start/Ready/Prepare** lines. The exact pinout **depends on the module**; refer to the Agilent ERI documentation for your model. In practice, a **Sample Prep** method in **OpenLab CDS v2.8** is configured to await a rising edge on a chosen input line (commonly “pin 1”) before starting acquisition.
- **Phase sensor (OCB350):** connect signal and supply per the sensor datasheet. The Arduino reads the sensor for phase monitoring and calibration.

> For detailed wiring schematics and mechanical drawings, see the figures referenced as *Figure S1.66–S1.67* in your documentation folder.

---

## 🧪 Assembly Steps

1. **Prep enclosure**: Deburr prints, test‑fit all panels and connectors.
2. **Mount hardware**: Install the power switch, fuse holder, barrel jack(s), D‑Sub connectors, and Arduino with stand‑offs.
3. **Power wiring**: Wire DC jack → fuse → power switch → actuator supply rail. Keep logic ground connected to the actuator ground at a **single star point**.
4. **ERI harness**: Crimp a D‑Sub‑15 harness to the ERI cable. Map **Start**, **Ready**, **Prepare**, and **GND** per **Agilent ERI** manual for the modules you use.
5. **Actuator harness**: Wire Arduino output pin(s) to actuator controller inputs (through appropriate series resistors or driver stage if required by your actuator). Share **GND**.
6. **Phase sensor**: Provide the sensor supply (per datasheet). Connect signal output to an Arduino digital/analog pin specified in firmware.
7. **Label** all external connectors, add strain relief, close the lid.

---

## 🔧 Firmware & Serial Protocol

Flash the **Arduino Uno R3** with the ChromTroller control firmware (see repository). Connect via **USB serial**.
Commands use human‑readable syntax:

- **Set/Write:** `Sx=y`  
  *Sets variable `x` to value `y` (type depends on variable).*
- **Get/Read:** `Rx`  
  *Reads variable `x` and prints its value.*

> Unless specified, `Sx=y` does not print a response. `Rx` always prints a value.

### Variables

| No. | Access | Type | Description |
|---:|:---:|:---|:---|
| 1 | R/W | `STRING[20]` | Device identifier |
| 2 | R | `INT[0–254]` | Error register `x-y` (type‑value). Resets on read |
| 3 | CMD | `NONE` | Save defaults |
| 4 | CMD | `NONE` | Factory reset |
| 5 | R/W | `INT[0–1]` | **Valve position** (0=A, 1=B). Sends acknowledge when done |
| 6 | CMD | `NONE` | Send **START REQUEST** to UPLC |
| 7 | CMD | `NONE` | Send **STOP** |
| 8 | R | `INT[0–1]` | Read **READY** from UPLC |
| 9 | CMD | `NONE` | **Calibrate** phase sensor |
|10 | R | `INT[0–3]` | Read phase sensor output |
|11 | R | `INT[0–1]` | Read LCMS **power state** |
|12 | R | `INT[0–1]` | Read UPLC **start** signal |
|13 | R | `INT[0–1]` | Read UPLC **prepare** signal |

*If the value type is `NONE`, the equal sign is still required (e.g., `S6=`).*

### Quick Test (Arduino IDE Serial Monitor)

1. Set the valve to A/B: `S5=0` → wait for ack, then `S5=1`  
2. Read READY state: `R8`  
3. Trigger a run (with OpenLab **Sample Prep** method waiting): `S6=`  
4. Stop signal (if configured): `S7=`  
5. Phase sensor: `S9=` to calibrate, then `R10` to read

---

## 🧪 Commissioning with OpenLab CDS v2.8

1. Create/modify a **Sample Prep** method that **waits for external trigger** (e.g., *pin 1* on ERI).  
2. On the instrument PC, start **ChromTroller** and connect the control box via USB.
3. **Queue** runs in OpenLab. They will remain pending until a **START REQUEST** is received.  
4. From ChromTroller (or manual serial), coordinate:
   - Set valve to *LOAD*; fill loop from RoboChem.  
   - Switch to *INJECT* and **immediately** issue `S6=` to start acquisition.  
   - Monitor **READY/START/PREPARE** lines to verify timing.  

This coupling ensures **1.4 µL** effective injection (1 µL loop + valve dead volume) is time‑aligned with data acquisition.

---

## 📎 Notes

- Effective injection volume is ~**1.4 µL** due to loop (1.0 µL, 90 mm × 0.12 mm) plus valve dead volume.
- Keep cable runs short and shielded where possible; reference grounds carefully.
- For ERI pin mapping, **always** consult your module’s manual.

---

## 📄 Figures & Files

- Controller photos & wiring: *Figure S1.67*
- ERI I/O overview: *Figure S1.66*
- Valve sampling/injection: *Figure S1.65*
- General UPLC connectivity: *Figure S1.64*

STLs: `LC_ENC.stl`, `LC_ENCL.stl` (see `docs/` or `hardware/` folder in repo)
