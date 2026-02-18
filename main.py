import logging
import time
import math
import geocoder
from enum import Enum
from gpiozero import Button
from signal import pause

import led
import epaper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s"
)

logger = logging.getLogger("main")

class Mode(Enum):
    IDLE = 0
    ACTIVE = 1


mode = Mode.IDLE
button_press_time = None
sevenseg = None

def make_number(value):
    frac = value - math.floor(value)
    return 0.01 + frac * 0.09

def init():
    global mode, button_press_time, sevenseg
    
    logger.info("--- Init ---")

    mode = Mode.IDLE
    button_press_time = None

    try: 
        epaper.clear()
    except Exception as e:
        logger.warning(f"epaper.clear failed: {e}")

def on_reset_pressed():
    logger.info("Reset button pressed")
    init()

def on_button_press():
    global button_press_time, mode
    if button_press_time is None:
        return
    press_duration = time.time() - button_press_time
    logger.info(f"Button released - {press_duration:.3f}")
    
    button_press_time = None

    if press_duration < 0.05:
        logger.debug("Ignoring very short press {press_duration}")
        return

    toggle(press_duration)

def on_button_release():
    global button_press_time
    button_press_time = time.time()
    logger.debug("Button pressed")

def toggle(press_duration):
    global mode

    if mode == Mode.IDLE:
        mode = Mode.ACTIVE
        logger.info(f"Switch to ACTIVE - {press_duration:.3f}")
        sevenseg.set_mode(mode)
        sevenseg.freeze()

        g = geocoder.ip('me')
        lat = g.latlng[0]
        lng = g.latlng[1]
        seed = abs(lat * 100 + lng * 100)
        # -----
        block_size = int(press_duration)
        if block_size < 1:
            block_size = 1
        # -----
        hash_mode = int(seed% 11) 
        logger.info(f"Hash Mode: {hash_mode}")
        # -----
        is_perlin = int(seed)%2==0
        #is_perlin = True 
        logger.info(f"is Perlin - value: {seed}")
        logger.info(f"is Perlin: {is_perlin}")
        # -----
        ns = make_number(lat+lng)
        nsX = make_number(lat)
        nsY = make_number(lng)
        logger.info(f"noiseSize, noiseSizeX, noiseSizeY: {ns}, {nsX}, {nsY}")
        # -----

        epaper.draw_async(
                block_size,
                hash_mode,
                is_perlin,
                ns,
                nsX,
                nsY 
        )
    else:
        mode = Mode.IDLE
        logger.info(f"Switch to IDLE - {press_duration:.3f}")
        sevenseg.set_mode(mode)
        sevenseg.freeze()
        epaper.clear()
        sevenseg.unfreeze()

# --- init, boost ---
try:
    sevenseg = led.SevenSeg()

    time.sleep(0.3)

    init()

    time.sleep(0.3)

    # toggle button 
    button = Button(
        23,
        pull_up=True,
        bounce_time=0.05
    )

    button.when_pressed = on_button_press
    button.when_released = on_button_release


    reset_button = Button(
        26,
        pull_up=True,
        bounce_time=0.1
    )
    
    reset_button.when_pressed = on_reset_pressed

    logger.info("System ready")

    pause()

except KeyboardInterrupt:
    logger.info("Shutting down")
    try:
        sevenseg.stop()
    except:
        pass
