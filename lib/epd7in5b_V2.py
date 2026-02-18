# *****************************************************************************
# * | File        :	  epd7in5b_V2.py
# * | Author      :   Waveshare team
# * | Function    :   Electronic paper driver
# * | Info        :
# *----------------
# * | This version:   V4.2
# * | Date        :   2022-01-08
# # | Info        :   python demo
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#


import logging
from . import epdconfig

# Import for hack method
import random
import numpy as np
from noise import pnoise1
from noise import pnoise2
from decimal import Decimal, getcontext
import hashlib
import math
import time
from datetime import datetime
import geocoder

# Display resolution
EPD_WIDTH       = 800
EPD_HEIGHT      = 480

logger = logging.getLogger(__name__)

class EPD:
    def __init__(self):
        self.reset_pin = epdconfig.RST_PIN
        self.dc_pin = epdconfig.DC_PIN
        self.busy_pin = epdconfig.BUSY_PIN
        self.cs_pin = epdconfig.CS_PIN
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.partFlag=1

    # Hardware reset
    def reset(self):
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200) 
        epdconfig.digital_write(self.reset_pin, 0)
        epdconfig.delay_ms(4)
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)   

    def send_command(self, command):
        epdconfig.digital_write(self.dc_pin, 0)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([command])
        epdconfig.digital_write(self.cs_pin, 1)

    def send_data(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte([data])
        epdconfig.digital_write(self.cs_pin, 1)
    
    def send_data2(self, data): #faster
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.digital_write(self.cs_pin, 0)
        epdconfig.spi_writebyte2(data)
        epdconfig.digital_write(self.cs_pin, 1)

    def ReadBusy(self):
        logger.debug("e-Paper busy")
        self.send_command(0x71)
        busy = epdconfig.digital_read(self.busy_pin)
        while(busy == 0):
            self.send_command(0x71)
            busy = epdconfig.digital_read(self.busy_pin)
        epdconfig.delay_ms(200)
        logger.debug("e-Paper busy release")
        
    def init(self):
        if (epdconfig.module_init() != 0):
            return -1
        
        # EPD hardware init start
        self.reset()

        self.send_command(0x01)
        self.send_data(0x07)
        self.send_data(0x07)
        self.send_data(0x3f)
        self.send_data(0x3f)

        self.send_command(0x06)
        self.send_data(0x17)
        self.send_data(0x17) 
        self.send_data(0x28)	
        self.send_data(0x17)

        self.send_command(0x04)
        epdconfig.delay_ms(100)
        self.ReadBusy()

        self.send_command(0X00)
        self.send_data(0x0F)

        self.send_command(0x61)		
        self.send_data(0x03)
        self.send_data(0x20)
        self.send_data(0x01)
        self.send_data(0xE0)

        self.send_command(0X15)
        self.send_data(0x00)

        self.send_command(0X50)
        self.send_data(0x11)
        self.send_data(0x07)

        self.send_command(0X60)
        self.send_data(0x22)
            
        return 0
    
    def init_Fast(self):
        if (epdconfig.module_init() != 0):
            return -1
        
        # EPD hardware init start
        self.reset()

        self.send_command(0X00)
        self.send_data(0x0F)

        self.send_command(0x04)
        epdconfig.delay_ms(100)
        self.ReadBusy()

        self.send_command(0x06)
        self.send_data(0x27)
        self.send_data(0x27) 
        self.send_data(0x18)		
        self.send_data(0x17)		

        self.send_command(0xE0)
        self.send_data(0x02)
        self.send_command(0xE5)
        self.send_data(0x5A)

        self.send_command(0X50)
        self.send_data(0x11)
        self.send_data(0x07)
        
        return 0
    
    def init_part(self):
        if (epdconfig.module_init() != 0):
            return -1
        # EPD hardware init start
        self.reset()

        self.send_command(0X00)
        self.send_data(0x1F)

        self.send_command(0x04)
        epdconfig.delay_ms(100)
        self.ReadBusy()

        self.send_command(0xE0)
        self.send_data(0x02)
        self.send_command(0xE5)
        self.send_data(0x6E)

        self.send_command(0X50)
        self.send_data(0xA9)
        self.send_data(0x07)

        # EPD hardware init end
        return 0


    # 数字をbit文字列へ(2進数化 or hash化) -----
    def numbers_to_bitstring(self, numbers, hash_mode=0):
        getcontext().prec = 200

        #Create a list if numbers is a single value
        if not isinstance(numbers, (list, tuple)):
            numbers = [numbers]

        #Create a bit array with SHA256
        seed = ",".join(str(n) for n in numbers).encode()
        match hash_mode:
            case 0:
                nums = [Decimal(str(n)) for n in numbers]

                vmin = min(nums)
                vmax = max(nums)

                pattern_bits = ""

                if vmin == vmax:
                    n = nums[0]
                    bits = bin(int(n))[2:]
                    return bits

                for n in nums:
                    norm = (n-vmin)/(vmax-vmin) 
                    norm = max(min(norm, 1), 0)
                    q = int((norm*3).to_integral_value(rounding="ROUND_HALF_UP"))
                    bits = format(q, "02b")
                    pattern_bits += bits

                print("Pattern Bits", pattern_bits)

                return pattern_bits
            case 1:
                digest = hashlib.md5(seed).hexdigest()
            case 2:
                digest = hashlib.sha1(seed).hexdigest()
            case 3:
                digest = hashlib.sha224(seed).hexdigest()
            case 4:
                digest = hashlib.sha384(seed).hexdigest()
            case 5:
                digest = hashlib.sha512(seed).hexdigest()
            case 6:
                digest = hashlib.sha3_224(seed).hexdigest()
            case 7:
                digest = hashlib.sha3_256(seed).hexdigest()
            case 8:
                digest = hashlib.sha3_384(seed).hexdigest()
            case 9:
                digest = hashlib.sha3_512(seed).hexdigest()
            case _:
                digest = hashlib.sha256(seed).hexdigest()
            
        binary_str = bin(int(digest, 16))[2:]
        return binary_str


    # bit文字列から1枚絵を生成 -----
    def makebuffer_from_bitstring(self, pattern_bits, block_size=1):
        width = self.width
        height = self.height

        buf_size = int(width/8)*height
        total_bits = buf_size * 8

        block_width = math.ceil(width/block_size)
        block_height = math.ceil(height/block_size)

        repeated_blocks = (pattern_bits * math.ceil(block_width*block_height/len(pattern_bits)))[:block_width*block_height]

        expanded_bits = []

        for row in range(block_height):
            row_bits = repeated_blocks[row*block_width:(row+1)*block_width]
            expanded_row = ''.join(bit*block_size for bit in row_bits)
            for _ in range(block_size):
                expanded_bits.append(expanded_row[:width])

        expanded_bitstring = ''.join(expanded_bits)[:total_bits]

        pad_len = (8-len(expanded_bitstring)%8)%8
        expanded_bitstring = expanded_bitstring + '0' * pad_len

        buf = bytearray(
            int(expanded_bitstring[i:i+8], 2)
            for i in range(0, len(expanded_bitstring), 8)
        )

        return buf

    def generatebuffer_time(self, hash_mode, block_size):
        t = time.time()
        dt = datetime.now()
        print(t)
        print(dt)

        bit_str = self.numbers_to_bitstring(t, hash_mode)
        buf = self.makebuffer_from_bitstring(bit_str, block_size)
        
        return buf

    def generatebuffer_perlin(self, base_buffer, ns, nsX, nsY):
        width = self.width
        height = self.height
        total_bits = width * height

        bits = ''.join(f"{byte:08b}" for byte in base_buffer)

        if len(bits) < total_bits:
            repeat = total_bits // len(bits) + 1
            bits = (bits * repeat)[:total_bits]
        else:
            bits = bits[:total_bits]

        buffer = []

        scale = ns 
        nxscale = nsX
        nyscale = nsY

        for y in range(height):
            byte = 0
            for x in range(width):
                b = x + x * y
                byte_str = bits[b:b+8]
                
                if len(byte_str) < 8:
                    byte_str = byte_str.ljust(8, "0")

                byte_val = int(byte_str, 2)

                nx = x * scale + byte_val * nxscale
                ny = y * scale + byte_val * nyscale

                n = pnoise2(nx, ny)

                bit = 1 if n > 0 else 0

                byte = (byte << 1) | bit

                if(x+1) % 8 == 0:
                    buffer.append(byte)
                    byte = 0

            if width % 8 != 0:
                buffer.append(byte << (8-width%8))
        
        return buffer
                

    # Original Generate Buffer function -----
    def getbuffer(self, image):
        img = image
        imwidth, imheight = img.size
        if(imwidth == self.width and imheight == self.height):
            img = img.convert('1')
        elif(imwidth == self.height and imheight == self.width):
            # image has correct dimensions, but needs to be rotated
            img = img.rotate(90, expand=True).convert('1')
        else:
            logger.warning("Wrong image dimensions: must be " + str(self.width) + "x" + str(self.height))
            # return a blank buffer
            return [0x00] * (int(self.width/8) * self.height)

        buf = bytearray(img.tobytes('raw'))
        # The bytes need to be inverted, because in the PIL world 0=black and 1=white, but
        # in the e-paper world 0=white and 1=black.
        for i in range(len(buf)):
            buf[i] ^= 0xFF
        return buf

    def display(self, imageblack, imagered):
        self.send_command(0x10)
        for i in range(len(imageblack)):
            imageblack[i] ^= 0xFF
        self.send_data2(imageblack)

        self.send_command(0x13)
        self.send_data2(imagered)
        
        self.send_command(0x12)
        epdconfig.delay_ms(100)
        self.ReadBusy()

    def display_Base_color(self, color):
        if(self.width % 8 == 0):
            Width = self.width // 8
        else:
            Width = self.width // 8 +1
        Height = self.height
        self.send_command(0x10)   #Write Black and White image to RAM
        for j in range(Height):
            for i in range(Width):
                self.send_data(color)
                
        self.send_command(0x13)  #Write Black and White image to RAM
        for j in range(Height):
            for i in range(Width):
                self.send_data(~color)

        self.send_command(0x12)
        epdconfig.delay_ms(100)
        self.ReadBusy()

    def display_Partial(self, Image, Xstart, Ystart, Xend, Yend):
        if((Xstart % 8 + Xend % 8 == 8 & Xstart % 8 > Xend % 8) | Xstart % 8 + Xend % 8 == 0 | (Xend - Xstart)%8 == 0):
            Xstart = Xstart // 8 * 8
            Xend = Xend // 8 * 8
        else:
            Xstart = Xstart // 8 * 8
            if Xend % 8 == 0:
                Xend = Xend // 8 * 8
            else:
                Xend = Xend // 8 * 8 + 1
                
        Width = (Xend - Xstart) // 8
        Height = Yend - Ystart
	
        # self.send_command(0x50)
        # self.send_data(0xA9)
        # self.send_data(0x07)

        self.send_command(0x91)		#This command makes the display enter partial mode
        self.send_command(0x90)		#resolution setting
        self.send_data (Xstart//256)
        self.send_data (Xstart%256)   #x-start    

        self.send_data ((Xend-1)//256)		
        self.send_data ((Xend-1)%256)  #x-end	

        self.send_data (Ystart//256)  #
        self.send_data (Ystart%256)   #y-start    

        self.send_data ((Yend-1)//256)		
        self.send_data ((Yend-1)%256)  #y-end
        self.send_data (0x01)

        if self.partFlag == 1:
            self.partFlag = 0
            self.send_command(0x10)
            for j in range(Height):
                    for i in range(Width):
                        self.send_data(0xff)

        self.send_command(0x13)   #Write Black and White image to RAM
        self.send_data2(Image)

        self.send_command(0x12)
        epdconfig.delay_ms(100)
        self.ReadBusy()
        
    def Clear(self):
        # Original buffer frame
        buf = [0x00] * (int(self.width/8) * self.height)    #bw
        buf2 = [0xff] * (int(self.width/8) * self.height)   #red

        self.send_command(0x10)
        self.send_data2(buf2)
            
        self.send_command(0x13)
        self.send_data2(buf)
                
        self.send_command(0x12)
        epdconfig.delay_ms(100)
        self.ReadBusy()

    def sleep(self):
        self.send_command(0x02) # POWER_OFF
        self.ReadBusy()
        
        self.send_command(0x07) # DEEP_SLEEP
        self.send_data(0XA5)
        
        epdconfig.delay_ms(2000)
        epdconfig.module_exit()
### END OF FILE ###

