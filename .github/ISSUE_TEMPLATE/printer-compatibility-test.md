---
name: Printer Compatibility Test
about: Test a specific Creality printer model with this integration
title: "[TEST] [Printer Model] Compatibility"
labels: ["testing", "compatibility"]
assignees: []
---

## Printer Information
- **Model:** [e.g., Creality K1, Ender-3 V3 SE, Halot-One]
- **Type:** [FDM/Resin]
- **Firmware Version:** [if known]
- **Network Setup:** [WiFi/Ethernet]

## Test Configuration
- **IP Address:** [e.g., 192.168.1.100]
- **Port Used:** [9999/18188]
- **Password Required:** [Yes/No]
- **Camera Available:** [Yes/No/Unknown]

## Test Results

### ✅ Connection Test
- [ ] Successfully connected to printer
- [ ] WebSocket communication established
- [ ] Data received from printer

### 📊 Sensors Test
- [ ] Printer Model sensor
- [ ] Firmware Version sensor
- [ ] Temperature sensors (nozzle/bed)
- [ ] Print Progress sensor
- [ ] Print Status sensor
- [ ] Position sensors (X/Y/Z)
- [ ] Fan status sensors
- [ ] Material usage sensors
- [ ] Time remaining sensor

### 🎮 Controls Test
- [ ] Pause/Resume Print button
- [ ] Stop Print button
- [ ] Home All Axes button
- [ ] Home X/Y/Z buttons (if available)
- [ ] Emergency Stop button (if available)
- [ ] Fan control buttons (if available)

### 📷 Camera Test (if applicable)
- [ ] Camera entity created
- [ ] Camera image loads successfully
- [ ] Camera snapshot works
- [ ] Camera stream displays properly

## Issues Encountered
[Describe any problems, errors, or unexpected behavior]

## Logs
```
[Paste relevant Home Assistant logs here]
```

## Additional Notes
[Any other observations or suggestions]

## Test Environment
- **Home Assistant Version:** [e.g., 2024.10.0]
- **Integration Version:** [e.g., 1.1.0]
- **Test Date:** [YYYY-MM-DD]
