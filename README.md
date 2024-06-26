# <img src = "utils/CrocLogo.png" width = "100"> ChromTroller

## Overview
This package controls the triggering of the LCMS unit used in the NRG's RoboChem systems. 
The package includes a server interface to communicate with RoboChem (or any external program), controller software to interpret server commands and instrument data, and code for the arduino microcontroller.

---

## Hardware
The LCMS unit is composed of an Agilent 1290 Infinity II UPLC-MS, an external VICI switch valve controlled by a VICI Two Position Actuator Controller and an OCB350 phase sensor board which are all controlled by a central Arduino microcontroller.

---

## General Architecture
The codebase is built in 3 parts: the **Arduino code** (found in the Arduino Sketches directory), the **device** programs, the **controller** program and the **server** program.

```mermaid
graph TD;
    RbC(RoboChem)
    cli(CT Client)
    ser(CT Server)
    CT(ChromTroller)
    Ard(Arduino)
    dev(LCMSDevice)
    lcms(Agilent LCMS)
    SW(Switch Valve)
    PS(Phase Sensor)
    log(CT RunLog)
    mon(CT Monitor)
    anal(CT Analysis)
    cal(Calibration)
    lams(Analysis)
    
    RbC --> cli
    cli<--Socket-->ser
    ser <--> CT
    log <--> CT
    CT <--> mon
    CT --> Hardware & Analysis
    subgraph Hardware
    dev <--Serial-->Ard;
    Ard-->lcms & SW & PS;
    end
    subgraph Analysis
    anal --> cal & lams    ;
    end
```
### LCMS Server
The **server program** allows Server-Client type communication between this system and an external program through a socket.

This architecture is designed to improve the independence of the UPLC-MS module by creating a generic server which can be connected to by any device and handles all of the more complex comands independantly of the external program.
Helps isolate the LCMS with the socket communication allowing the client to operate independently, which is helpful in dealing with the 32 vs 64 bit issues encountered in the robochem platform.

### LCMS Controller
The **device programs** act as the pyhton-side interface with the Arduino and is split into `ArduinoDevice` and `LCMSDevice`. 
The `ArduinoDevice` contains basic Arduino operations (e.g. open/close connection, send/read data, etc...) while `LCMSDevice` inherits the `ArduinoDevice` class and contains methods specific to the instrument (e.g. set valve to position X, start LCMS run, read phase sensor, etc...).
The **control program** controls the complex behaviour for the system (e.g. runs a seperate thread to monitor the phase sensor data, runs checks to ensure analysis is only triggerred under set conditions, takes user commands and calls the desired method, etc...).

### Arduino Microcontroller
allows communication between the PC (Serial) and the hardware (Digital I/O) and incldes the nessessary comands/responses for the Arduino. 

The arduino sketch is built to take serial commands as 

The device is controlled via serial-through-USB using human readable commands with the following syntax:

- `Sx=y`<br>
Set variable x to value y. Variable numbers are integer, values type depends on the variable.<br>
- `Rx`<br>
Read variable x and print its value to serial.<br>

---
## Installation and Setup
pip install server side to server computer ...
conda env...
Arduino IDE ...
Wire pins to Ard and set the pins in the Ard code...
Flash Arduino code and identify COM port ...
config file setup ...
    set COM for Serial comm with Ard in python prog ...
    set the host, port and user/password for the server side...
start server ...
Calibrate phase sensor to empty

---
## Useage

Client example code

---

### Header 2
**Bold Text** , *Italic Text* , Normal text
- Bullet Point

``Text Box`` 


    Copy Box

---

*Author: ***Olly Bayley*** <o.m.bayley at uva.nl>,* ***Noël Research Group, 2024***