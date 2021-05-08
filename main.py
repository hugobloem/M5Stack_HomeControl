import m5stack
from m5stack_ui import M5Screen
# import m5ui
import ujson as json
import time
from urequests import get, post
from m5mqtt import M5mqtt
from machine import Timer
from time import sleep_ms
from math import sqrt, ceil
from easyIO import map_value
import lvgl as lv

import config as c

lv.init()
scr = lv.obj()
scr.clean()

lv.scr_load(scr)

class UI():
    def __init__(self):
        # Declare variables
        self.hor_res = c.hor_res
        self.ver_res = c.ver_res
        self.tiles = {}

        self.spinner = lv.spinner(scr)
        self.spinner.align(scr, lv.ALIGN.CENTER, 0, 0)
        self.spinner.set_hidden(True)

        self.wifi_led = lv.led(scr, None)
        self.wifi_led.set_size(12, 12)
        self.wifi_led.align(None, lv.ALIGN.IN_TOP_LEFT, 9, 9)
        self.wifi_led.move_foreground()
        self.wifi_led.off()

        self.bat_pct = map_value(m5stack.power.getBatVoltage(), 3.7, 4.1, 0, 100)
        self.battery = lv.label(scr, None)
        self.battery.set_text(str(self.bat_pct) + '%')
        self.battery.align(scr, lv.ALIGN.IN_TOP_RIGHT, -7, 7)
        @m5stack.timerSch.event('battery_timer')
        def update_battery():
            self.bat_pct = map_value(m5stack.power.getBatVoltage(), 3.7, 4.1, 0, 100)
            self.battery.set_text(str(self.bat_pct) + '%')
        m5stack.timerSch.run('battery_timer', 60000, 0x00)

        self.valid_pos = []
        self.tileview = lv.tileview(lv.scr_act())
        self.tileview.set_edge_flash(True)
        self.tileview.move_background()

        self.add_tile('Main', (0, 0))
        self.btns = {}


    def haptic(self, duration):
        name = 'haptic' + str(duration)
        if name not in m5stack.timerSch.timerList:
            m5stack.power.setVibrationIntensity(c.vibrationIntensity)
            @m5stack.timerSch.event(name)
            def haptictimer():
                m5stack.power.setVibrationEnable(False)
        m5stack.power.setVibrationEnable(True)
        m5stack.timerSch.run(name, duration, 0x01)
    
    def loading(self, state):
        self.spinner.move_foreground()
        self.spinner.set_hidden(not state)
    
    def add_tile(self, name, loc):
        self.tiles[name] = {}
        self.tiles[name]['loc'] = loc
        self.valid_pos.append({"x":loc[0], "y": loc[1]})
        self.tileview.set_valid_positions(self.valid_pos, len(self.valid_pos))

        # Add tile
        tile = lv.obj(self.tileview)
        tile.set_size(self.hor_res, self.ver_res)
        tile.set_pos(self.hor_res*loc[0], 
                     self.ver_res*loc[1])
        self.tileview.add_element(tile)
        self.tiles[name]['tile'] = tile

        # Add status bar
        status_bar = lv.obj(tile)
        status_bar.set_size(self.hor_res, c.status_bar_width)
        status_bar.align(tile, lv.ALIGN.IN_TOP_MID, 0, 0)
        status_bar.set_hidden(True)
        self.tiles[name]['status_bar'] = status_bar

        # Add main window
        window = lv.obj(tile)
        window.set_size(self.hor_res, self.ver_res - c.status_bar_width)
        window.align(tile, lv.ALIGN.IN_BOTTOM_MID, 0, 0)
        window.set_hidden(True)
        self.tiles[name]['window'] = window

        # Add title
        label = lv.label(tile)
        label.set_text(name)
        label.align(status_bar, lv.ALIGN.CENTER, 0, 0)

    def fill_entities(self, entities, parent):
        N = len(entities)
        Nx = 1 if N < 4 else 2
        Ny = ceil(N/Nx)

        win = ui.tiles[parent]['window']
        width = win.get_width()
        height = win.get_height()

        if N == 1:
            locs = [(width//2, height//2)]
        elif N == 2:
            locs = [(width//2, height//3), 
                    (width//2, height//3*2)]
        elif N == 3:
            locs = [(width//2, height//4), 
                    (width//2, height//4*2),
                    (width//2, height//4*3)]
        elif N == 4:
            locs = [(width//4, height//3),
                    (width//4, height//3*2),
                    (width//4*3, height//3),
                    (width//4*3, height//3*2)]

        for n, entity in enumerate(entities):
            btn = lv.btn(self.tiles[parent]['tile'])
            label = lv.label(btn)
            label.set_text(entity.name)
            btn.set_event_cb(entity.clicked)
            btn.set_pos(locs[n][0]-(btn.get_width()//2), locs[n][1]-(btn.get_height()//2) + c.status_bar_width)
            self.btns[entity.entity_id] = btn

    
    def add_list(self, entities, parent):
        lst = lv.list(self.tiles[parent]['tile'])
        lst.set_size(self.hor_res, self.ver_res - 40)
        lst.align(None, lv.ALIGN.IN_BOTTOM_MID, 0, 0)
        lst.set_scroll_propagation(True)
        lst.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        for entity in entities:
            btn = lst.add_btn(entity.symbol, entity.name)
            btn.set_event_cb(entity.clicked)
        self.tiles[parent]['list'] = lst

    def add_btnmatrix(self, entities, parent, width=2):
        btnm = lv.btnmatrix(self.tiles[parent]['tile'])
        lst.set_size(self.hor_res, self.ver_res - 40)
        lst.align(None, lv.ALIGN.IN_BOTTOM_MID, 0, 0)

        for entity in entities:
            btn = lst.add_btn(entity.symbol, entity.name)
        self.tiles[parent]['list'] = lst
        
        btn.set_event_cb(entity.clicked)

    def change_entity_options(self, entity):
        cont = lv.cont(lv.scr_act(), None)
        cont.set_auto_realign(True)                 # Auto realign when the size changes
        cont.align_mid(None,lv.ALIGN.CENTER,0,0)  # This parameters will be sued when realigned
        cont.set_fit(lv.FIT.TIGHT)
        cont.set_layout(lv.LAYOUT.COLUMN_MID)
        
        title = lv.label(cont)
        title.set_text(entity.name)

        def update_bright(source, event):
            if event == lv.EVENT.VALUE_CHANGED:
                entity.set_brightness(source.get_value())
                bright_label.set_text('Brightness: ' + str(source.get_value()) + '%')

        def update_ct(source, event):
            if event == lv.EVENT.VALUE_CHANGED:
                entity.set_ct(source.get_value())
                ct_label.set_text('Colour temperature: ' + str(source.get_value()) + 'K')

        def update_position(source, event):
            if event == lv.EVENT.VALUE_CHANGED:
                entity.set_position(source.get_value())
                pos_label.set_text('Position: ' + str(source.get_value()) + '%')

        def exit_popup(source, event):
            if event == lv.EVENT.CLICKED:
                cont.fade_out(750, 0)
                sleep_ms(750)
                cont.delete()
        try:
            if entity.brightness_pct:
                bright_label = lv.label(cont)
                bright_label.set_text('Brightness: ' + str(entity.brightness_pct) + '%')
                
                bright_slider = lv.slider(cont)
                bright_slider.set_range(0, 100)
                bright_slider.set_value(entity.brightness_pct, 0)
                bright_slider.set_event_cb(update_bright)
        except: pass

        try:
            if entity.kelvin:
                ct_label = lv.label(cont)
                ct_label.set_text('Color temperature: ' + str(entity.kelvin) + 'K')
                
                ct_slider = lv.slider(cont)
                ct_slider.set_range(entity.kelvin_min, entity.kelvin_max)
                ct_slider.set_value(entity.kelvin, 0)
                ct_slider.set_event_cb(update_ct)
        except: pass

        try:
            if entity.open:
                pos_label = lv.label(cont)
                pos_label.set_text('Position: ' + str(entity.open) + '%')
                
                pos_slider = lv.slider(cont)
                pos_slider.set_range(0, 100)
                pos_slider.set_value(entity.open, 0)
                pos_slider.set_event_cb(update_position)
        except: pass

        exitbtn = lv.btn(cont)
        exitbtn.set_event_cb(exit_popup)
        exitbtn_label = lv.label(exitbtn)
        exitbtn_label.set_text('Close')

def getEntities(entity_registry_path, type):
    with open(entity_registry_path, 'r') as f:
        entities = json.load(f)['data'][type]
    ent_dict = {}
    for entity in entities:
        ent_dict[entity['entity_id']] = entity
    return ent_dict

class Light():
    def __init__(self, entity):
        self.entity_id = entity['entity_id']
        self.name = entity['original_name']
        self.topic = 'home/light/' + self.entity_id
        self.symbol = None
        self.on = False
        ha.subscribe(self.topic + '/state', self._state_callback)

        try:
            self.brightness_pct = entity['brightness_pct']
            ha.subscribe(self.topic + '/brightness', self._bright_callback)
        except:
            self.brightness_pct = None

        try:
            self.kelvin = entity['kelvin']
            self.kelvin_max = entity['kelvin_max']
            self.kelvin_min = entity['kelvin_min']
            ha.subscribe(self.topic + '/color_temp', self._ct_callback)
        except:
            self.kelvin = None

    def _state_callback(self, topic_data):
        self.on = topic_data == 'on'
        if self.on:
            ui.btns[self.entity_id].set_state(3)
        else:
            ui.btns[self.entity_id].set_state(0)

    def _bright_callback(self, topic_data):
        self.brightness_pct = int(topic_data)

    def _bright_callback(self, topic_data):
        mired = int(topic_data)
        self.kelvin = 1e6//mired

    def turn_on(self):
        ha.publish(self.topic + '/state/set', "on")
        self.on = True

    def turn_off(self):
        ha.publish(self.topic + '/state/set', "off")
        self.on = False

    def set_brightness(self, brightness_pct):
        brightness = brightness_pct*255//100
        ha.publish(self.topic + '/brightness/set', str(brightness))
        self.on = True
        self.brightness_pct = brightness_pct

    def set_ct(self, kelvin):
        mired = 1e6//kelvin
        ha.publish(self.topic + '/color_temp/set', str(mired))
        self.on = True
        self.kelvin = kelvin

    def clicked(self, source, event):
        if event == lv.EVENT.SHORT_CLICKED:
            if self.on:
                self.turn_off()
            else:
                self.turn_on()
        elif event == lv.EVENT.LONG_PRESSED:
            ui.haptic(200)
            ui.change_entity_options(self)

    def clicked_toggle(self, source, event):
        if event == lv.EVENT.SHORT_CLICKED:
            if self.on:
                self.turn_off()
                source.set_state(0) # not toggled
            else:
                self.turn_on()
                source.set_state(3) # toggled
        elif event == lv.EVENT.LONG_PRESSED:
            ui.haptic(200)
            ui.change_entity_options(self)

class Blind():
    def __init__(self, entity):
        self.entity_id = entity['entity_id']
        self.name = entity['original_name']
        self.topic = 'home/cover/' + self.entity_id
        self.symbol = None
        self.open = 100
        self.on = self.open == 0
        ha.subscribe(self.topic + '/current_position', self._callback)
    
    def _callback(self, topic_data):
        self.open = int(float(topic_data))

    def turn_on(self):
        ha.publish(self.topic + '/current_position/set', 0)
        self.open = 100
        self.on = True

    def turn_off(self):
        ha.publish(self.topic + '/current_position/set', 100)
        self.open = 0
        self.on = False

    def set_position(self, position):
        ha.publish(self.topic + '/current_position/set', position)
        self.on = True
        self.open = position

    def clicked(self, source, event):
        if event == lv.EVENT.SHORT_CLICKED:
            if self.on:
                self.turn_off()
            else:
                self.turn_on()

    def clicked_toggle(self, source, event):
        if event == lv.EVENT.SHORT_CLICKED:
            if self.on:
                self.turn_off()
                source.set_state(0) # not toggled
            else:
                self.turn_on()
                source.set_state(3) # toggled
        elif event == lv.EVENT.LONG_PRESSED:
            ui.haptic(200)
            ui.change_entity_options(self)


### SETUP ###

ui = UI()

ui.loading(True) ###
ha = M5mqtt(c.mqtt_client_id, c.mqtt_server, 1883,
        c.mqtt_user, c.mqtt_password, 300)

lights = getEntities(c.entity_registry, 'light')
blinds = getEntities(c.entity_registry, 'cover')

ui.loading(False) ###

### CONFIG ###

hugo_lights = [Light(lights['origami']),
               Light(lights['desklamp']),
               Blind(blinds['tradfri_blind'])]

living_room_lights = [Light(lights['corner_light']),
                      Light(lights['lounge_front']),
                      Light(lights['lounge_back'])]

ui.add_tile('Settings', (0, 1))

ui.add_tile('Living Room', (1, 0))
ui.add_tile('Living Room Lights', (1,1))
ui.fill_entities(living_room_lights, 'Living Room Lights')

ui.add_tile('Hugo', (2,0))
ui.add_tile('Hugo Lights', (2,1))
ui.fill_entities(hugo_lights, 'Hugo Lights')

ha.start()
### TESTING ###

screen = M5Screen()
screen.set_screen_brightness(c.brightness)

def change_brightness(source, event):
    if event == lv.EVENT.VALUE_CHANGED:
        screen.set_screen_brightness(source.get_value())
        slider_label.set_text(str(source.get_value()))

slider = lv.slider(ui.tiles['Settings']['tile'])
slider.set_event_cb(change_brightness)
slider.set_width(200)
slider.align(ui.tiles['Settings']['window'], lv.ALIGN.CENTER, 0, 0)
slider.set_range(30, 100)
slider.set_value(c.brightness, 0)

slider_label=lv.label(ui.tiles['Settings']['tile'])
slider_label.set_text(str(c.brightness))
slider_label.set_auto_realign(True)
slider_label.align(slider,lv.ALIGN.OUT_BOTTOM_MID,0,10)