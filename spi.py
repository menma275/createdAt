import threading

spi_lock = threading.Lock()
epaper_busy = threading.Event()
