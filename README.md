# Smart Orifice Flow Measurement System

SolidWorks Simulation of Flow
![Image](https://github.com/user-attachments/assets/752996d7-5ade-42c1-81fa-e24272f47b1e)

## Badges

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen?style=flat)]()
[![Version](https://img.shields.io/badge/version-1.0-blue?style=flat)]()
[![License](https://img.shields.io/badge/license-MIT-green?style=flat)]()
[![Platform](https://img.shields.io/badge/platform-Arduino%20%7C%20Python-blue?style=flat)]()

## 1. Project Overview

**Automated, Low-Cost Flow Measurement for Labs & Education.**

This repository contains a professional-grade flow measurement system integrating a precision ISO 5167-compliant orifice plate with novel capacitive sensor automation and full embedded software for real-time monitoring. The system is designed for both education and research, combining classical fluid mechanics principles with modern embedded hardware and data visualization solutions to create accessible, reproducible, and highly accurate laboratory instrumentation.

## 2. Table of Contents

- [Features](#features)
- [Specifications](#specifications)
- [Hardware](#hardware)
- [Software Overview](#software-overview)
- [System Architecture](#system-architecture)
- [Setup & Calibration](#setup--calibration)
- [Experimental Results](#experimental-results)
- [Safety & Handling](#safety--handling)
- [Future Directions](#future-directions)
- [References](#references)
- [Project Team](#project-team)

## 3. Features

- **ISO 5167-compliant orifice plate** for precision differential pressure measurements.
- **Custom capacitive sensor** automates the U-tube manometer, reducing manual error.
- **Arduino Uno data acquisition** with EMA filtering for smooth, reliable readings.
- **Real-time Python dashboard** for interactive visualization and logging.
- **Smart fallback system** ensures continuous operation under sensor drift or failure.
- **Cost-effective:** Achieves ±2.8% accuracy, well below typical student project error rates; total cost <$90 compared to $500+ for commercial devices.

## 4. Specifications

| Parameter | Value | Notes |
| :--- | :--- | :--- |
| **Main Pipe Diameter** | 26.6 mm (1 inch) | Standard PVC |
| **Orifice Diameter** | 14.6 mm (β = 0.55) | Laser-cut acrylic |
| **Manometer Fluid** | CCL4 (ρ = 1594 kg/m³) | Mineral oil option (requires recalibration) |
| **Max Range** | 14.5 cm | Manometer height |
| **Sampling Rate** | 4 Hz (250 ms) | Arduino interval timing |
| **System Accuracy** | ±2.8% | Validated experimentally |
| **Operating Range** | 0.01 - 0.145 m Δh | Differential height |

## 5. Hardware

- Arduino Uno (ATmega328P)
- Capacitive sensor circuit (1MΩ resistor, copper tape electrodes)
- LCD 16x2 with I2C backpack
- Laser-cut acrylic orifice plate (3 mm)
- 1-inch PVC pipe assembly
- U-tube manometer with copper tape electrodes
- Flow conditioner (10 cm parallel straws)

## 6. Software Overview

### Firmware (Arduino-Code)
- Arduino C++ implementation using `CapacitiveSensor` library.
- EMA filtering for smooth differential readings.
- Safety fallback and calibration routines.

### Dashboard (Python-Dashboard)
- Python 3 program with `matplotlib` live plots.
- Real-time CSV data export.
- Simple calibration logger (`calibration_logger.py`) for 2-point adjustment.

## 7. System Architecture

1.  Orifice plate creates measurable pressure drop in pipe.
2.  U-tube manometer records Δh; capacitive electrodes automate height sensing.
3.  Arduino captures sensor data, filters, displays, and transmits via Serial.
4.  Python dashboard logs, visualizes, and manages data in real-time.

## 8. Setup & Calibration

1.  **Mechanical Assembly:** Follow checklist; ensure proper installation of orifice plate, flow conditioner, manometer tubing, and electrodes.
2.  **Electronic Setup:** Arduino mounting, wiring LCD and sensor, upload `Calibration_Code.ino`.
3.  **Calibration:** Run `calibration_logger.py` script with known fluid levels (0% and 100% flow) to get `MIN` and `MAX` values.
4.  **Operation:** Enter these values into the `Main_Firmware.ino`, upload, and run `main_dashboard.py` to see live data.

## 9. Experimental Results

Flow Rate Monitoring Over Time

<img width="1000" height="600" alt="Image" src="https://github.com/user-attachments/assets/982ee0b8-6d91-4687-9b33-3b6cf1df2ba1">

Characteristic Curve (Q vs. Δh)
<img width="1000" height="600" alt="Image" src="https://github.com/user-attachments/assets/70867495-a85a-49c0-8138-25d57e380ddc">

- Achieves **±2.8% full-span accuracy** confirmed against manual measurements.
- Real-time visualization curve shows close match between experiment and theory.
- System repeatability: ±0.01 L/s; response time: <1.2 seconds.
- Built-in error mitigation for air bubbles, sensor drift, and temperature effects.

## 10. Safety & Handling

-  **CCL4 is toxic:** Handle in a ventilated area, use nitrile gloves, and consider mineral oil substitution (which requires recalibration).
- Arduino and electronics operate at safe 5V levels.
- Standard lab safety protocols apply.

## 11. Future Directions

- Add temperature compensation for fluid density.
- Wireless data transmission (Bluetooth/WiFi options).
- Mobile visualization app.
- Higher-resolution sensors (op-amp based).
- Automated multi-point calibration routines.

## 12. References

- ASME PTC 19.5-2004; ISO 5167-2:2003; Cengel & Cimbala (2018); Benedict (1980); Miller (1996)
- Arduino & Python technical resources.

## 13. Project Team

* **Mohamad Ashraf kamal AIfkharany (Team Lead)**
* Abdullah Mahmoud Elsaiyd Elhalawany
* Mohamed Elesawy Hussein Ahmed
* Mohamed Akram Ragb Mohamed
* Youssef Ahmed Muhammad Abu Khall
* Mohamed Walid Mohamed Salama
* Mohamed Shokry Sallam
* Mostafa Abdellal Mostafa
* Ashraf Ayman Mohamed Mahgoub
* Mohammed ELhosiney ELsayed Ramadan

---
**Contact:** Team Lead via GitHub Issues for support and questions.
