import logging
import threading
import queue
import time
from PIL import Image

from lib import epd7in5b_V2
from spi import spi_lock, epaper_busy 

logger = logging.getLogger("epaper")

_epd = None
_task_q = queue.Queue()
_worker_started = False
_init_lock = threading.Lock()

def init():
    global _epd, _worker_started

    with _init_lock:
        if _epd is None:
            logger.info("init start")
            epaper_busy.set()
            time.sleep(0.1)

            try:
                with spi_lock:
                    _epd = epd7in5b_V2.EPD()
                    _epd.init()
                logger.info("epd initialized")
            except Exception as e:
                logger.error(f"{e}", exc_info=True)
                epaper_busy.clear()
                raise
            finally:
                time.sleep(0.1)
                epaper_busy.clear()

        if not _worker_started:
            threading.Thread(target=_worker, daemon=True).start()
            _worker_started = True
            logger.info("worker thread started")

    return _epd


def clear():
    logger.info("clear display")
    epd = init()

    epaper_busy.set()
    time.sleep(0.1)

    try:
        with spi_lock:
            epd.Clear()
    finally:
        time.sleep(0.1)
        epaper_busy.clear()


def draw_async(block_size=10, hash_mode=0, is_perlin=False, ns=0.01, nsX=0.01, nsY=0.01):
    logger.info("draw_async requested")
    init()
    params = {
        "block_size": block_size,
        "is_perlin": is_perlin,
        "ns": ns,
        "nsX": nsX,
        "nsY": nsY
    }
    _task_q.put(("DRAW", params))


def _worker():
    logger.info("worker running")

    while True:
        task, params = _task_q.get()

        if task == "DRAW":
            logger.info("buffer generation start")

            block_size = params.get("block_size", 10)
            hash_mode = params.get("hash_mode", 0)
            is_perlin = params.get("is_perlin", False)
            ns = params.get("ns", 0.01)
            nsX = params.get("nsX", 0.01)
            nsY = params.get("nsY", 0.01)

            epd = _epd
            blank = Image.new("1", (epd.width, epd.height), 255)

            bw = epd.generatebuffer_time(hash_mode, block_size)
            if is_perlin:
                bw = epd.generatebuffer_perlin(bw, ns, nsX, nsY)
            red = epd.getbuffer(blank)

            logger.info("buffer generation done")

            epaper_busy.set()
            
            time.sleep(0.1)

            try:
                with spi_lock:
                    logger.info("draw start")
                    epd.display(bw, red)
                    logger.info("draw done")
            except Exception as e:
                logger.error(f"Draw failed: {e}", exc_info=True)
            finally:
                time.sleep(0.1)
                epaper_busy.clear()

        _task_q.task_done()
