import time
import logging
import threading

logger = logging.getLogger("gps")

DEFAULT_LATITUDE = 35.700000000000000
DEFAULT_LONGITUDE = 139.70000000000000


class GravityGPS:
    def __init__(
        self,
        mode="i2c",
        port="/dev/serial0",
        baudrate=115200,
        i2c_bus=1,
        i2c_address=0x20,
    ):
        """
        GPS Reader for DFRobot Gravity GNSS Module (TEL0157).

        :param mode: "i2c" or "uart"
        :param port: UART serial port path (used if mode="uart")
        :param baudrate: UART baud rate (usually 115200 or 9600)
        :param i2c_bus: I2C bus number (usually 1 on Raspberry Pi)
        :param i2c_address: I2C address of the module (default is 0x20)
        """
        self.mode = mode.lower()
        self.port = port
        self.baudrate = baudrate
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address

        # Last known coordinates (fallback)
        self.latitude = DEFAULT_LATITUDE
        self.longitude = DEFAULT_LONGITUDE
        self.has_fix = False

        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        """Start the background GPS reading thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("GPS reader thread started")

    def stop(self):
        """Stop the background GPS reading thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info("GPS reader thread stopped")

    def _run(self):
        if self.mode == "i2c":
            self._run_i2c()
        elif self.mode == "uart":
            self._run_uart()
        else:
            logger.error(f"Unknown GPS mode: {self.mode}")

    def _run_i2c(self):
        import smbus2

        bus = None
        zero_data_count = 0

        # Wait for system/hardware to stabilize on boot
        time.sleep(3.0)

        while self._running:
            try:
                if bus is None:
                    bus = smbus2.SMBus(self.i2c_bus)
                    # Initialize GPS Module via I2C commands
                    try:
                        # 1. Enable Power (Write 0x00 to Register 0x23)
                        bus.write_byte_data(self.i2c_address, 0x23, 0x00)
                        time.sleep(0.1)
                        # 2. Set GNSS Mode to GPS+BeiDou+GLONASS (Write 0x07 to Register 0x22)
                        bus.write_byte_data(self.i2c_address, 0x22, 0x07)
                        time.sleep(0.1)
                        # 3. Enable RGB LED indicator (Write 0x05 to Register 0x24)
                        bus.write_byte_data(self.i2c_address, 0x24, 0x05)
                        time.sleep(0.1)
                        logger.info("Sent I2C startup commands to GPS module (Power ON, GPS+BeiDou+GLONASS mode)")
                        zero_data_count = 0
                    except Exception as init_err:
                        logger.warning(f"GPS initialization write failed: {init_err}")
                        try:
                            bus.close()
                        except:
                            pass
                        bus = None
                        time.sleep(2.0)
                        continue
                
                # Read 23 bytes starting from register 0 using block read
                raw_data = bus.read_i2c_block_data(self.i2c_address, 0, 23)
                
                # Extract Time elements (Reg 4-6)
                hour = raw_data[4]
                minute = raw_data[5]
                second = raw_data[6]
                
                # Extract latitude elements (Reg 7-11, 18)
                lat_deg = raw_data[7]
                lat_min = raw_data[8]
                lat_frac = (raw_data[9] << 16) | (raw_data[10] << 8) | raw_data[11]
                lat_dir = chr(raw_data[18]) if raw_data[18] < 128 else '?'
                
                # Extract longitude elements (Reg 12-17)
                lon_deg = raw_data[13]
                lon_min = raw_data[14]
                lon_frac = (raw_data[15] << 16) | (raw_data[16] << 8) | raw_data[17]
                lon_dir = chr(raw_data[12]) if raw_data[12] < 128 else '?'
                
                # Convert minutes to decimal representation
                # lat_frac represents the 3rd to 7th digits behind the decimal point (e.g. 5 digits)
                lat_minutes = lat_min + lat_frac / 100000.0
                lon_minutes = lon_min + lon_frac / 100000.0
                
                # Calculate decimal degrees
                lat_val = lat_deg + lat_minutes / 60.0
                lon_val = lon_deg + lon_minutes / 60.0
                
                # Apply directions
                if lat_dir == 'S':
                    lat_val = -lat_val
                if lon_dir == 'W':
                    lon_val = -lon_val

                # If coordinates are 0.0 AND the direction registers are empty (0),
                # it means the module is in standby mode or not running.
                # If direction is present (e.g. 'N'/'E') but coordinates are 0.0,
                # it is actively searching for satellites (Do NOT reset).
                is_standby = (lat_val == 0.0 and lon_val == 0.0 and raw_data[18] == 0 and raw_data[12] == 0)
                if is_standby:
                    zero_data_count += 1
                    if zero_data_count >= 10:
                        logger.warning("GPS module appears to be in standby (all zero data) for 10s. Retrying full initialization...")
                        try:
                            bus.close()
                        except:
                            pass
                        bus = None
                        zero_data_count = 0
                        time.sleep(1.0)
                        continue
                else:
                    zero_data_count = 0

                # Simple validation of coordinates
                if 0.0 <= lat_val <= 90.0 and 0.0 <= lon_val <= 180.0 and not (lat_val == 0.0 and lon_val == 0.0):
                    with self._lock:
                        was_fixed = self.has_fix
                        self.latitude = lat_val
                        self.longitude = lon_val
                        self.has_fix = True
                        if not was_fixed:
                            logger.info(
                                f"GPS positioning successful (Fixed)! Lat: {lat_val:.6f}, Lon: {lon_val:.6f}"
                            )
                else:
                    with self._lock:
                        was_fixed = self.has_fix
                        self.has_fix = False
                        if was_fixed:
                            logger.warning("GPS lost signal (Unfixed)")

            except Exception as e:
                logger.warning(f"GPS I2C read failed: {e}")
                bus = None
                with self._lock:
                    self.has_fix = False

            time.sleep(1.0)

    def _run_uart(self):
        import serial

        ser = None

        while self._running:
            try:
                if ser is None:
                    ser = serial.Serial(self.port, self.baudrate, timeout=2)

                line = ser.readline().decode("ascii", errors="replace").strip()
                # Temp debug log to verify serial connection and baudrate
                logger.info(f"[DEBUG] UART Read: {line}")
                if not line:
                    continue

                # Parse standard NMEA-0183 sentences (GNGGA / GPGGA)
                if line.startswith("$GNGGA") or line.startswith("$GPGGA"):
                    parts = line.split(",")
                    if len(parts) > 6:
                        fix_quality = parts[6]
                        if fix_quality != "0" and parts[2] and parts[4]:
                            # Parse Latitude: DDMM.MMMMM
                            raw_lat = parts[2]
                            lat_dir = parts[3]
                            # Parse Longitude: DDDMM.MMMMM
                            raw_lon = parts[4]
                            lon_dir = parts[5]

                            lat_val = float(raw_lat[:2]) + float(raw_lat[2:]) / 60.0
                            if lat_dir == "S":
                                lat_val = -lat_val

                            lon_val = float(raw_lon[:3]) + float(raw_lon[3:]) / 60.0
                            if lon_dir == "W":
                                lon_val = -lon_val

                            with self._lock:
                                self.latitude = lat_val
                                self.longitude = lon_val
                                self.has_fix = True
                        else:
                            with self._lock:
                                self.has_fix = False
            except Exception as e:
                logger.warning(f"GPS UART read failed: {e}")
                if ser:
                    try:
                        ser.close()
                    except:
                        pass
                    ser = None
                with self._lock:
                    self.has_fix = False
                time.sleep(2.0)

    def get_location(self):
        """
        Get the current latitude and longitude.

        :return: (latitude, longitude, has_fix)
        """
        with self._lock:
            return self.latitude, self.longitude, self.has_fix
