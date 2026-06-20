import time
import logging
import threading

logger = logging.getLogger("gps")

class GravityGPS:
    def __init__(self, mode="i2c", port="/dev/serial0", baudrate=115200, i2c_bus=1, i2c_address=0x20):
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
        
        # Last known coordinates (fallback to Tokyo Metropolitan Museum)
        self.latitude = 35.717420305092794
        self.longitude = 139.77294943554242
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
        
        while self._running:
            try:
                if bus is None:
                    bus = smbus2.SMBus(self.i2c_bus)
                
                # The register map starts at 7 (LAT_1) and ends at 18 (LAT_DIS)
                # Read 12 bytes:
                # 0: LAT_1 (deg)
                # 1: LAT_2 (min)
                # 2: LAT_X_24 (frac min high)
                # 3: LAT_X_16 (frac min mid)
                # 4: LAT_X_8 (frac min low)
                # 5: LON_DIS (lon dir character)
                # 6: LON_1 (deg)
                # 7: LON_2 (min)
                # 8: LON_X_24 (frac min high)
                # 9: LON_X_16 (frac min mid)
                # 10: LON_X_8 (frac min low)
                # 11: LAT_DIS (lat dir character)
                data = bus.read_i2c_block_data(self.i2c_address, 7, 12)
                
                # Extract latitude elements
                lat_deg = data[0]
                lat_min = data[1]
                lat_frac = (data[2] << 16) | (data[3] << 8) | data[4]
                lat_dir = chr(data[11])
                
                # Extract longitude elements
                lon_deg = data[6]
                lon_min = data[7]
                lon_frac = (data[8] << 16) | (data[9] << 8) | data[10]
                lon_dir = chr(data[5])
                
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
                
                # Simple validation of coordinates
                if 0.0 <= lat_val <= 90.0 and 0.0 <= lon_val <= 180.0:
                    with self._lock:
                        self.latitude = lat_val
                        self.longitude = lon_val
                        self.has_fix = True
                else:
                    with self._lock:
                        self.has_fix = False
                        
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
                
                line = ser.readline().decode('ascii', errors='replace').strip()
                if not line:
                    continue
                
                # Parse standard NMEA-0183 sentences (GNGGA / GPGGA)
                if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                    parts = line.split(',')
                    if len(parts) > 6:
                        fix_quality = parts[6]
                        if fix_quality != '0' and parts[2] and parts[4]:
                            # Parse Latitude: DDMM.MMMMM
                            raw_lat = parts[2]
                            lat_dir = parts[3]
                            # Parse Longitude: DDDMM.MMMMM
                            raw_lon = parts[4]
                            lon_dir = parts[5]
                            
                            lat_val = float(raw_lat[:2]) + float(raw_lat[2:]) / 60.0
                            if lat_dir == 'S':
                                lat_val = -lat_val
                                
                            lon_val = float(raw_lon[:3]) + float(raw_lon[3:]) / 60.0
                            if lon_dir == 'W':
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
