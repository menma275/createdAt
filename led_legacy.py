import logging
import spidev
import time
import threading

from spi import spi_lock, epaper_busy

logger = logging.getLogger("led")


class SevenSeg:
    def __init__(self, digits=8):
        logger.info("SevenSeg init start")

        self.digits = digits
        self.mode = "IDLE"
        self._lock = threading.Lock()
        self._frozen_value = ""

        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 1_000_000

        self._init_max7219()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        logger.info("SevenSeg init done / thread start")

    def _init_max7219(self):
        logger.info("init MAX7219")

        def w(r, d):
            with spi_lock:
                self.spi.xfer2([r, d])

        w(0x09, 0xFF)
        w(0x0A, 0x01)
        w(0x0B, self.digits - 1)
        w(0x0C, 0x01)
        w(0x0F, 0x00)

    def clear(self):
        for i in range(1, self.digits + 1):
            with spi_lock:
                self.spi.xfer2([i, 0x0F])

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
            self._frozen_value = ""

    def _unix_time(self):
        return f"{int(time.time()) % 100_000_000:08d}"

    def _parse(self, s):
        out = []
        for ch in s:
            out.append(int(ch) if ch.isdigit() else 0x0F)
            if len(out) == self.digits:
                break
        while len(out) < self.digits:
            out.append(0x0F)
        return list(reversed(out))

    def _display(self, s):
        for i, v in enumerate(self._parse(s)):
            with spi_lock:
                self.spi.xfer2([i + 1, v])

    def _run(self):
        logger.info("display thread running")
        next_tick = time.time()

        while True:
            if epaper_busy.is_set():
                time.sleep(0.05)
                continue

            with self._lock:
                if self._frozen_value:
                    disp = self._frozen_value
                elif self.mode == "ACTIVE":
                    disp = self._unix_time()
                else:
                    disp = self._unix_time()

            self._display(disp)

            next_tick += 1
            time.sleep(max(0, next_tick - time.time()))
