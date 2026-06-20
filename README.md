# Project "createdAt" - System Architecture

This project runs on a **Raspberry Pi Zero 2 WH**. It coordinates an e-paper display and a MAX7219-based 7-segment LED display to generate and display dynamic visual patterns (Perlin noise and mathematical hashing) determined by the current UNIX time and geographical coordinates (latitude and longitude).

---

## 🛠 Hardware Configuration

| Component | Interface | GPIO Pins | Details |
| :--- | :--- | :--- | :--- |
| **Raspberry Pi Zero 2 WH** | Main Controller | - | - |
| **7.5" E-Paper Display V2** | Hardware SPI | SPI Pins | 3-Color (Red/Black/White) |
| **MAX7219 7-Seg LED Modules** | Bitbang SPI | CS=20, DIN=16, CLK=21 | 3 daisy-chained modules |
| **Toggle Button** | GPIO Input | GPIO 23 (Pin 16) | Controls active/idle state transitions |
| **Reset Button** | GPIO Input | GPIO 26 (Pin 37) | Refreshes status and location |
| **Gravity GNSS GPS Module** | I2C / UART | (See Next Steps) | Switch Science SKU: 8924 / DFRobot TEL0157 |

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

## 🚀 Next Step: Integrating `gps.py`

Currently, location coordinates (latitude and longitude) are hardcoded in [main.py](file:///Users/k.sakamura/Downloads/work/createdAt/main.py) and [led.py](file:///Users/k.sakamura/Downloads/work/createdAt/led.py) to point to the *Tokyo Metropolitan Museum*. Follow these steps to transition to dynamic location sensing via the physical GPS module:

### 1. Hardware Connection

We recommend **I2C mode** because it works out of the box without disabling the Raspberry Pi serial console.

1. Set the physical switch on the Gravity GNSS module to **I2C**.
2. Connect to the Pi's GPIO pins:
   * **VCC** ➡ Raspberry Pi 3.3V (Pin 1)
   * **GND** ➡ Raspberry Pi GND (Pin 6)
   * **SDA** ➡ Raspberry Pi SDA / GPIO 2 (Pin 3)
   * **SCL** ➡ Raspberry Pi SCL / GPIO 3 (Pin 5)

*(If using UART, set the switch to UART, wire TX/RX to GPIO 14/15, disable the serial console via `sudo raspi-config` -> Interface Options -> Serial, and install `pyserial`.)*

### 2. Code Changes

To integrate the GPS module, implement the following edits:

#### A. Modify `led.py`
Import the GPS module and read from the sensor instead of hardcoded coordinates:

```diff
  import threading
  import geocoder
+ from gps import GravityGPS
  from gpiozero import DigitalOutputDevice

...

  class SevenSeg:
      def __init__(self, digits=8, modules=3):
          ...
          self._lat = None
          self._lng = None
+         self.gps = GravityGPS(mode="i2c")
+         self.gps.start()
          self._get_location()

...

      def _get_location(self):
-         with self._lock:
-             self._lat = 35.717420305092794
-             self._lng = 139.77294943554242
+         lat, lng, has_fix = self.gps.get_location()
+         with self._lock:
+             self._lat = lat
+             self._lng = lng
```

#### B. Modify `main.py`
Ensure the main loop fetches the latest GPS coordinates from `sevenseg.gps` rather than using the hardcoded ones:

```diff
  def toggle(press_duration):
      global mode

      if mode == Mode.IDLE:
          mode = Mode.ACTIVE
          logger.info(f"Switch to ACTIVE - {press_duration:.3f}")
          sevenseg.set_mode(mode)
          sevenseg.freeze()

-         # Tokyo Metroploitan Museum
-         lat = 35.717420305092794
-         lng = 139.77294943554242
+         # Get current position from the active GPS module
+         lat, lng, _ = sevenseg.gps.get_location()

          logger.info(f"Location: {lat} {lng}")
```
