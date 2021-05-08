from machine import SDCard
from machine import Pin 
import os
import wifiCfg
import config as c

try:
    sd = SDCard(slot=3, miso=Pin(38), mosi=Pin(23), sck=Pin(18), cs=Pin(4))
    sd.info()
    os.mount(sd, '/sd')
    print("SD card mounted at \"/sd\"")
except (KeyboardInterrupt, Exception) as e:
    # print('SD mount caught exception {} {}'.format(type(e).__name__, e))
    pass

wifiCfg.doConnect(c.ssid, c.psk)
if wifiCfg.is_connected():
    print('Connected to WiFi.')
