import logging
import time
import threading
import geocoder
from gpiozero import DigitalOutputDevice
from spi import spi_lock, epaper_busy

logger = logging.getLogger("led")

class SevenSeg:
    def __init__(self, digits=8, modules=3):
        logger.info("SevenSeg init start")

        self.digits = digits
        self.modules = modules 
        self.mode = "IDLE"
        self._lock = threading.Lock()
        self._frozen_value = None
        self._running = True

        self._lat = None
        self._lng = None
        self._get_location()

        self.din = DigitalOutputDevice(16)
        self.cs = DigitalOutputDevice(20)
        self.clk = DigitalOutputDevice(21)

        self.cs.on()

        self._init_max7219()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        logger.info("SevenSeg init done / thread start")

    def _get_location(self):
        try:
            g = geocoder.ip("me")
            if g.latlng:
                lat = g.latlng[0]
                lng = g.latlng[1]
                logger.info(f"Location: lat={self._lat}, lng={self._lng}")
            else:
                logger.warning("Could not get location")
                lat =  0.0
                lng = 0.0 
        except Exception as e:
            logger.error(f"Error getting location: {e}")
            lat =  0.0
            lng = 0.0 

        with self._lock:
            self._lat = lat
            self._lng = lng

    def _pulse(self):
        self.clk.off()
        self.clk.on()

    def _shift_out(self, byte):
        for _ in range(8):
            self.clk.off()
            self.din.value = (byte & 0x80) != 0
            byte <<= 1
            self.clk.on()

    def _write(self, reg, data):
        self.cs.off()
        self._shift_out(reg)
        self._shift_out(data)
        self.cs.on()

    def _write_to_module(self, module_idx, reg, data):
        self.cs.off()
        for i in range(self.modules - 1, -1, -1):
            if i == module_idx:
                self._shift_out(reg)
                self._shift_out(data)
            else:
                self._shift_out(0x00)
                self._shift_out(0x00)
        self.cs.on()

    def _init_max7219(self):
        logger.info("init MAX7219(bitbang)")
        self._write(0x09, 0xFF)
        self._write(0x0A, 0x0F)
        self._write(0x0B, self.digits - 1)
        self._write(0x0C, 0x01)
        self._write(0x0F, 0x00)
        self.clear()

    def clear(self):
        for i in range(1, self.digits+1):
            self._write(i, 0x0F)

    def set_mode(self, mode):
        with self._lock:
            self.mode = mode.name
            self._frozen_value = ""

    def freeze(self):
        with self._lock:
            if not self._frozen_value:
                self._frozen_value = self._unix_time()

    def unfreeze(self):
        with self._lock:
            self._frozen_value = None

    def _unix_time(self):
        return f"{int(time.time()) % 100_000_000:08d}"

    def _format_coordinate(self, value):
        if value >= 100:
            formatted = f"{value:09.5f}"
        elif value >= 10:
            formatted = f"{value:09.6f}"
        else:
            formatted = f"{value:09.7f}"
        
        return formatted[:10] if value < 0 else formatted[:9]


    def _parse(self, s):
        out = []
        i = 0
        digit_count = 0

        while i < len(s) and digit_count < self.digits:
            ch = s[i]
            if ch == ".":
                if out:
                    out[-1] = out[-1] | 0x80
                i += 1
            elif ch.isdigit():
                out.append(int(ch))
                digit_count += 1
                i+=1
            elif ch == "-":
                out.append(0x0A)
                digit_count += 1
                i+=1
            else:
                out.append(0x0f)
                i+=1

        while len(out) < self.digits:
            out.append(0x0F)
        return list(reversed(out))

    def _display(self, s):
        for i, v in enumerate(self._parse(s)):
            self._write(i+1, v)

    def _display_all(self, module_values):
        try:
            for digit_pos in range(1, self.digits + 1):
                if epaper_busy.is_set():
                    return
                self.cs.off()
                for module_idx in range(self.modules - 1, -1, -1):
                    if module_idx < len(module_values):
                        parsed = self._parse(module_values[module_idx])
                        value = parsed[digit_pos - 1]
                    else:
                        value = 0x0F
                    self._shift_out(digit_pos)
                    self._shift_out(value)
                self.cs.on()
        except Exception as e:
            logger.error(f"Display Error: {e}")
            try:
                self.cs.on()
            except:
                pass

    def _run(self):
        logger.info("display thread running")
        next_tick = time.time()

        while self._running:
            if epaper_busy.is_set():
                time.sleep(0.05)
                next_tick = time.time() + 1
                continue
        
            try:
                with self._lock:
                    if self._frozen_value:
                        module0_value = self._frozen_value
                    else:
                        module0_value = self._unix_time()

                    if(self._lat == 0.0 and self._lng == 0.0) or self._lat is None:
                        self._get_location()

                    module1_value = self._format_coordinate(self._lat)
                    module2_value = self._format_coordinate(self._lng)
                    
                self._display_all([module0_value, module1_value, module2_value])

                next_tick += 1
                sleep_time = max(0, next_tick - time.time())

                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    next_tick = time.time()
            except Exception as e:
                logger.error(f"LED error: {e}")
                time.sleep(0.1)
                next_tick = time.time()

    def stop(self):
        self._running = False
        if self._thread.is_active():
            self._thread.join(timeout=2.0)
