# [cite_start]Smart Orifice-Based Flow Measurement System with Automated Fallback and Capacitive Sensing [cite: 1]

> [cite_start]A professional-grade flow measurement system integrating a precision-manufactured orifice plate with a novel capacitive sensor automation solution. [cite: 14, 15] [cite_start]This project demonstrates how classical fluid mechanics principles combined with modern embedded systems technology can create cost-effective, highly accurate laboratory measurement devices. [cite: 17]

![System Performance Curve](https://i.imgur.com/g0PqE4T.png) ---

## 1. Project Overview

[cite_start]Accurate fluid flow measurement is fundamental in engineering, but commercial differential pressure sensors are often prohibitively expensive for educational and research applications. [cite: 33, 35] 

[cite_start]This project solves this problem by developing a complete, low-cost measurement system that automates a traditional U-tube manometer using a custom-fabricated capacitive sensor. [cite: 36] [cite_start]The system provides a cost-effective ($90) alternative to commercial systems ($500+), making professional-grade instrumentation accessible to all. [cite: 303, 37]

## 2. Key Features

* [cite_start]**Precision Orifice Design:** Fabricated an orifice plate assembly meeting ISO 5167 standards. [cite: 40]
* [cite_start]**Novel Capacitive Sensor:** Developed a custom capacitive sensor for automated U-tube manometer displacement measurement. [cite: 41]
* [cite_start]**Intelligent Firmware:** Implemented Arduino C++ code with EMA filtering and a smart fallback system. [cite: 42, 48]
* [cite_start]**Real-time Dashboard:** Created a comprehensive Python dashboard for live data visualization and logging. [cite: 43]
* [cite_start]**Validated Accuracy:** Achieved **±2.8%** accuracy, validated against manual measurements across the full operating range. [cite: 44, 250]
* [cite_start]**Full Documentation:** Provides complete, reproducible documentation for all hardware and software components. [cite: 45]

## 3. Technologies Used

This project integrates three core domains:

* **Hardware:**
    * [cite_start]Orifice plate assembly (3mm laser-cut acrylic, β = 0.55) [cite: 85, 86]
    * [cite_start]Flow conditioner (10cm PVC with parallel straws) [cite: 95]
    * [cite_start]U-tube manometer with CCL4 fluid [cite: 47, 56]
    * [cite_start]**Arduino Uno** (ATmega328P) Microcontroller [cite: 110]
    * [cite_start]Custom-built capacitive sensor (Copper tape + 1 MΩ resistor) [cite: 105, 113]
    * [cite_start]LCD 16x2 with I2C backpack [cite: 116]

* **Firmware (Arduino C++)**
    * [cite_start]`CapacitiveSensor.h` library for sensing. [cite: 133]
    * [cite_start]Exponential Moving Average (EMA) filtering for noise reduction. [cite: 48, 142]
    * [cite_start]Two-point linear calibration logic. [cite: 122]
    * [cite_start]Serial data communication (9600 baud) in CSV format. [cite: 119, 120]

* **Software (Python)**
    * [cite_start]`PySerial` for Arduino communication. [cite: 156, 173]
    * [cite_start]`Matplotlib` for real-time animated data visualization. [cite: 209, 225]
    * [cite_start]`Threading` to handle data reading and plotting simultaneously. [cite: 202]
    * [cite_start]Python-based logger for easy sensor calibration. [cite: 129, 155]

## 4. How It Works

### Theoretical Foundation
The system's design is based on two fundamental fluid mechanics equations:

1.  **Manometer Equation:** Relates the pressure difference ($\Delta P$) to the manometer fluid height difference ($\Delta h$).
    [cite_start]$$P_1 - P_2 = (\rho_m - \rho_f) g \Delta h$$ [cite: 60]

2.  **Orifice Flow Equation:** Relates the volumetric flow rate ($Q$) to the pressure difference ($\Delta P$).
    [cite_start]$$Q = C_d A_o \frac{1}{\sqrt{1 - \beta^4}} \sqrt{\frac{2(P_1 - P_2)}{\rho_f}}$$ [cite: 68]

By combining these, we get the final system equation, which shows that flow rate is proportional to the square root of the height difference:
[cite_start]**$Q \propto \sqrt{\Delta h}$** [cite: 79]

### Electronic Sensor Principle
[cite_start]The custom sensor measures the change in capacitance as the dielectric manometer fluid (CCL4) moves between two parallel copper tape electrodes. [cite: 104]
* [cite_start]Higher fluid level → Higher capacitance → Higher raw sensor reading. [cite: 109]
* [cite_start]An Arduino `CapacitiveSensor` library measures this change by timing an RC circuit (1MΩ resistor). [cite: 110, 113]

## 5. Project Results

The system achieved **excellent** performance, meeting all project objectives.

### Performance Summary
| Metric | Value | Standard | Status |
| :--- | :--- | :--- | :--- |
| **Accuracy** | **±2.8%** | <±5% | ✓ **EXCELLENT** |
| **Repeatability**| ±0.01 L/s | <±0.02 L/s| ✓ **EXCELLENT** |
| **Response Time**| 1.2 sec | <2 sec | ✓ **GOOD** |
| **Sampling Rate**| 4 Hz | Adequate | ✓ **GOOD** |
[cite_start][cite: 250]

### Characteristic Curve (Q vs. Δh)
[cite_start]The experimental data (red dots) shows excellent agreement with the theoretical curve (blue line), validating the $Q \propto \sqrt{\Delta h}$ relationship. [cite: 240, 241]

[cite_start]![Orifice Characteristic Curve](https://i.imgur.com/g0PqE4T.png) * **R² Correlation:** > 0.98 [cite: 245]
* [cite_start]**Average Error:** ±2.8% [cite: 246]

### Real-Time Monitoring
[cite_start]The Python dashboard demonstrates smooth, stable, and responsive real-time flow monitoring. [cite: 229, 231, 235]

![Flow Rate Over Time](https://i.imgur.com/U0P9fU1.png) ## 6. How to Use this Repository

### Repository Structure
```
Smart-Orifice-Flow-System/
│
├── Arduino-Code/
[cite_start]│   ├── 1_Calibration_Code/           # Code to find sensor min/max [cite: 128]
│   │   └── 1_Calibration_Code.ino
[cite_start]│   └── 2_Main_Firmware/              # The final operating code [cite: 130]
│       └── 2_Main_Firmware.ino
│
├── Python-Dashboard/
[cite_start]│   ├── calibration_logger.py         # Script to run with calibration code [cite: 129]
[cite_start]│   └── main_dashboard.py             # The real-time visualization dashboard [cite: 131]
│
└── Documentation/
    ├── Orifice_Flow_Meter_Report.pdf # (ضع التقرير الكامل هنا)
    └── Schematics_and_CAD/           # (ضع ملفات SolidWorks والرسومات هنا)
```

### Setup and Operation

**Phase 1: Mechanical & Electronic Assembly**
1.  [cite_start]Assemble the mechanical components (PVC pipes, orifice, manometer) as detailed in the report. [cite: 274-277]
2.  [cite_start]Wire the electronic components (Arduino, LCD, Capacitive Sensor) as per the circuit diagram. [cite: 279-282]

**Phase 2: Sensor Calibration (Important!)**
1.  [cite_start]Upload the `1_Calibration_Code.ino` firmware to the Arduino. [cite: 283]
2.  Connect the Arduino to your PC. [cite_start]Run the `calibration_logger.py` script. [cite: 286]
3.  [cite_start]Follow the script's instructions to find your `SENSOR_RAW_MIN` (at zero flow) and `SENSOR_RAW_MAX` (at maximum flow). [cite: 287]

**Phase 3: Operation**
1.  Open the `2_Main_Firmware.ino` file.
2.  [cite_start]Update the `CONFIG` section with the calibration values (`SENSOR_RAW_MIN`, `SENSOR_RAW_MAX`) you found in Phase 2. [cite: 181, 185, 186, 289]
3.  [cite_start]Upload this final firmware to the Arduino. [cite: 291]
4.  [cite_start]Run the `main_dashboard.py` script to launch the real-time visualization dashboard. [cite: 292]

## 7. Future Improvements
* [cite_start]Implement temperature compensation for fluid density. [cite: 311]
* [cite_start]Integrate wireless data transmission (Bluetooth/WiFi). [cite: 312]
* [cite_start]Develop a mobile app for remote monitoring. [cite: 313]

## 8. Project Team
* [cite_start]**Mohamad Ashraf kamal AIfkharany (Team Lead)** [cite: 3]
* [cite_start]Abdullah Mahmoud Elsaiyd Elhalawany [cite: 4]
* [cite_start]Mohamed Elesawy Hussein Ahmed [cite: 5]
* [cite_start]Mohamed Akram Ragb Mohamed [cite: 6]
* [cite_start]Youssef Ahmed Muhammad Abu Khall [cite: 7]
* [cite_start]Mohamed Walid Mohamed Salama [cite: 8]
* [cite_start]Mohamed Shokry Sallam [cite: 9]
* [cite_start]Mostafa Abdellal Mostafa [cite: 10]
* [cite_start]Ashraf Ayman Mohamed Mahgoub [cite: 11]
* [cite_start]Mohammed ELhosiney ELsayed Ramadan [cite: 12]
