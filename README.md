# Project "createdAt" - System Architecture

This project runs on a **Raspberry Pi Zero 2 WH**. It coordinates an e-paper display and a MAX7219-based 7-segment LED display to generate and display dynamic visual patterns (Perlin noise and mathematical hashing) determined by the current UNIX time and geographical coordinates (latitude and longitude).

---

## 🛠 Hardware Configuration

The system is wired to the **Raspberry Pi Zero 2 WH** using the following pin assignments.

### Detailed Pin Assignment Table

| Component | Signal Name | GPIO Number | Physical Pin | Description / Details |
| :--- | :--- | :--- | :--- | :--- |
| **Gravity GNSS GPS Module**<br>(DFRobot TEL0157) | SDA | GPIO 2 | Pin 3 | I2C Data |
| | SCL | GPIO 3 | Pin 5 | I2C Clock |
| | VCC | 3.3V or 5V | Pin 1 or Pin 2 | Power Supply |
| | GND | GND | Pin 6 | Ground |
| **7.5" E-Paper Display**<br>(Waveshare V2) | BUSY | GPIO 24 | Pin 18 | Busy Status (Output from display) |
| | RST | GPIO 17 | Pin 11 | Reset Pin |
| | D/C | GPIO 25 | Pin 22 | Data/Command Control Pin |
| | CS | GPIO 8 | Pin 24 | Hardware SPI Chip Select (CE0) |
| | SCLK | GPIO 11 | Pin 23 | Hardware SPI Clock |
| | DIN (MOSI) | GPIO 10 | Pin 19 | Hardware SPI Data |
| | VCC | 3.3V | Pin 17 | Power Supply |
| | GND | GND | Pin 20 | Ground |
| **MAX7219 7-Seg LED Module**<br>(3 modules daisy-chained) | DIN | GPIO 16 | Pin 36 | Software SPI Data |
| | CS | GPIO 20 | Pin 38 | Software SPI Load / Chip Select |
| | CLK | GPIO 21 | Pin 40 | Software SPI Clock |
| | VCC | 5V | Pin 4 | Power Supply (5V is recommended for MAX7219) |
| | GND | GND | Pin 34 | Ground |
| **Toggle Button** | Signal | GPIO 23 | Pin 16 | Mode toggle (pull-up, connects to GND) |
| | GND | GND | Pin 14 | Ground |
| **Reset Button** | Signal | GPIO 26 | Pin 37 | Reset / Refresh (pull-up, connects to GND) |
| | GND | GND | Pin 39 | Ground |

---

## 📁 System & File Structure

Here is an overview of the key components in the project:

*   **[main.py](file:///Users/k.sakamura/Downloads/work/createdAt/main.py)**: The main entry point. Orchestrates the application state (`IDLE` / `ACTIVE` modes), registers physical button callbacks, calculates the noise seeds, and initiates asynchronous rendering on the e-paper display.
*   **[led.py](file:///Users/k.sakamura/Downloads/work/createdAt/led.py)**: Manages the daisy-chained 7-segment displays. Runs a background thread updating the displays with:
    *   **Module 0:** Current UNIX timestamp
    *   **Module 1:** Current Latitude
    *   **Module 2:** Current Longitude
*   **[epaper.py](file:///Users/k.sakamura/Downloads/work/createdAt/epaper.py)**: Controls the 7.5-inch e-paper display. Generates visual patterns based on mathematical hash models and Perlin noise. Uses an internal task queue to draw asynchronously to avoid blocking the main execution thread.
*   **[spi.py](file:///Users/k.sakamura/Downloads/work/createdAt/spi.py)**: Defines threading synchronization primitives (`spi_lock` and `epaper_busy`) to prevent collisions on the SPI bus/GPIOs between the 7-segment and e-paper display threads.
*   **[gps.py](file:///Users/k.sakamura/Downloads/work/createdAt/gps.py)**: A helper library that handles reading coordinates from the DFRobot Gravity GNSS module. It supports reading via:
    *   **I2C Mode** (using `smbus2`, address `0x20` by default)
    *   **UART Mode** (using `pyserial`, reading standard NMEA `$GNGGA`/`$GPGGA` sentences from `/dev/serial0`)

---

## 🚀 GPS Integration & Setup

The system GNSS/GPS module (**DFRobot Gravity GNSS TEL0157**) is fully integrated via **I2C mode**. It dynamically reads latitude and longitude coordinates, updates the 7-segment display, and passes them as seeds for the e-paper rendering.

### 1. Hardware Configuration (I2C Mode)

1. Set the physical slide switch on the Gravity GNSS module to **I2C**.
2. Connect the module to the Pi's GPIO pins:
   * **VCC** ➡ Raspberry Pi 3.3V (Pin 1) or 5V (Pin 2/4)
   * **GND** ➡ Raspberry Pi GND (Pin 6/9/14/etc.)
   * **SDA** ➡ Raspberry Pi SDA / GPIO 2 (Pin 3)
   * **SCL** ➡ Raspberry Pi SCL / GPIO 3 (Pin 5)

> [!IMPORTANT]
> **Power Cycle Required:** The GPS module only reads the physical I2C/UART switch state during boot. If you change the switch position, you must completely disconnect the power (VCC pin) and plug it back in (power cycle) for the change to take effect.

---

### 2. Raspberry Pi I2C Speed Configuration

The GPS module's I2C MCU requires a lower clock speed to communicate reliably. If the I2C speed is too high (e.g. 400kHz), the module will return empty registers (`0xFF` / `255`). Setting the baudrate to **50kHz (50000)** is required.

1. Open `/boot/firmware/config.txt` (or `/boot/config.txt` on older OS versions) on the Pi:
   ```bash
   sudo nano /boot/firmware/config.txt
   ```
2. Add or modify the following line to enable I2C and set the clock speed:
   ```text
   dtparam=i2c_arm=on,i2c_arm_baudrate=50000
   ```
3. Save the file and reboot the Raspberry Pi:
   ```bash
   sudo reboot
   ```

---

### 3. System Behavior & Fallback

* **On Startup (Searching):**
  When first powered on, the GPS module searches for satellites (the onboard status LED is **Red**). While unfixed, the GPS driver automatically falls back to the default coordinates defined in [gps.py](file:///Users/sakamura/Downloads/createdAt/gps.py#L7-L8) (defaulting to the **Tokyo Metropolitan Museum**: `35.717420`, `139.772949`).
* **On Fix (Positioning Successful):**
  Once the module successfully acquires a satellite fix, the onboard status LED turns **Green** (or starts blinking green). The system automatically detects this change, outputs a log statement:
  `GPS positioning successful (Fixed)! Lat: XX.XXXXXX, Lon: XXX.XXXXXX`
  and updates both the 7-segment LED display and the e-paper rendering coordinates to the physical location.
