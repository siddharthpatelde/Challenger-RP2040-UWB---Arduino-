# Challenger RP2040 UWB (DWM3000) – Arduino toolchain Examples

This project shows how to program the Challenger RP2040 UWB module with the Arduino toolchain to

1. get a raw UWB data dump  
2. compute simple distance values

- Read the main project PDF here: [rp2040_uwb_progress.pdf](rp2040_uwb_progress.pdf)  
- First raw data example code: [raw_data_dump.ino](raw_data_dump.ino)

<!-- #TODOs 
1. create simple anchor teg system
2. increase the accuracy of UWB distance from cm to mm
3. get 2d/3d oriantation/position
4. pass the data to bigger µProcessor like (RP 5b) with ros/ros2 to make it part of bigger robotics system -->

## ToDo / Project Tasks

> This project is part of a student project at HTW Berlin, supervised by  
> **Prof. Dr.-Ing. Steffen Borchers-Tigasson**  
> https://www.htw-berlin.de/hochschule/personen/person/?eid=12130  

- [x] ~~0. Installation / bring-up / establishing communication with the UWB chips~~  
  - [x] 0.a) BU03-DW3000 via Raspberry Pi Pico  
  - [x] 0.b) Challenger DWM3000  
  - [x] Set up interfaces, e.g. Thonny, Arduino IDE, Windows Serial Debug Assistant  
  - [x] Basic documentation and simple test program (e.g. LED blink)  

- [x] ~~1. Create calibration data locally on the Pico/Challenger (requires 1 anchor and 1 tag)  ~~
  - [x] 1.a) Create a table:  
        `Distance (measured, real) | Distance (via UWB)`  
  - [x] 1.b) For 1 m, 2 m, 4 m, 8 m, 16 m collect 1000 data points each and save as CSV  
  - [x] 1.c) Evaluate accuracy and precision (mean values, variances) on the PC; transfer the data from the Pico to the PC  

- [x] ~~2. Determine / measure maximum data rate (requires 1 anchor and 1 tag)  ~~
  - [x] 2.a) Store distance data with timestamp (ms range) locally on the Pico, at least 1000 measurements  
        Table: `time | Distance (via UWB)`  
        Goal: determine measurement rate (frequency) and vary the data rate parameter (via AT commands on BU03, Challenger?)  
        Validate the configured data rate and push it towards the maximum (target: 60–100 Hz)  
  - [x] 2.b) Evaluation (mean, variance, min, max)  

- [ ] 3. Vary measurement method and repeat tasks 1 and 2  
  - Both chips support different measurement methods (e.g. TDoA, bidirectional)  
  - Compare methods regarding accuracy, precision and measurement rate  

- [ ] 4. Set up a real-time data connection from Pico to host PC via USB serial  
  - [ ] Send Pico data to the host in (near) real-time  
  - [ ] Insert the data into a database (in-memory or SQLite)  

- [ ] 5. Build a sensor network consisting of 4 anchors and 2 tags  
  - [ ] 5.a) Setup / topology configuration  
  - [ ] 5.b) Data transmission and functional testing  

- [ ] 6. Perform 3D localization on the PC with real-time data  
  - Goal: output and update x, y, z coordinates in real-time  
  - Possible methods:  
    - simple: Pythagoras / multilateration  
    - medium: optimization-based methods  
    - advanced: AI-based approaches  

- [ ] 7. Improve position accuracy using a Kalman filter  

- [ ] 8. Connect the system to the PTZ camera  
  - [ ] Use position data for camera control  
  - [ ] Test tracking and pointing accuracy
