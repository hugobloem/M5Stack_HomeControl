import m5stack
from m5stack_ui import M5Screen
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

# Initiate screen
lv.init()
scr = lv.obj()
scr.clean()

lv.scr_load(scr)

class UI():
    """
    The UI class holds all the functions and variables relating to the User Interface (UI).
    """
    def __init__(self):
        """Initiate class"""
        # Screen variables
        self.disp = lv.disp_get_default()
        self.hor_res = c.hor_res
        self.ver_res = c.ver_res
        self.brightness = c.brightness
        self.standby = False
        self.standby_delay = c.standby_delay
        self.tiles = {}

        # Loading spinner
        self.spinner = lv.spinner(scr)
        self.spinner.align(scr, lv.ALIGN.CENTER, 0, 0)
        self.spinner.set_hidden(True)

        # WiFi status light (on-screen)
        self.wifi_led = lv.led(scr, None)
        self.wifi_led.set_size(12, 12)
        self.wifi_led.align(None, lv.ALIGN.IN_TOP_LEFT, 9, 9)
        self.wifi_led.move_foreground()
        self.wifi_led.off()

        # Battery status
        self.bat_pct = map_value(m5stack.power.getBatVoltage(), 3.7, 4.1, 0, 100)
        self.battery = lv.label(scr, None)
        self.battery.set_text(str(self.bat_pct) + '%')
        self.battery.align(scr, lv.ALIGN.IN_TOP_RIGHT, -7, 7)
        # update battery status every 10 min (6e5 ms).
        @m5stack.timerSch.event('battery_timer')
        def update_battery():
            self.bat_pct = map_value(m5stack.power.getBatVoltage(), 3.7, 4.1, 0, 100)
            self.battery.set_text(str(self.bat_pct) + '%')
        m5stack.timerSch.run('battery_timer', 60000, 0x00)

        # Standby after set time
        # Check if active time has been exceeded every minute
        @m5stack.timerSch.event('standby_timer')
        def standby_timer():
            if time.ticks_ms() > self.disp.last_activity_time + self.standby_delay:
                self.set_standby()
        m5stack.timerSch.run('standby_timer', 60000, 0x00)

        # Tileview variables
        self.valid_pos = []
        self.tileview = lv.tileview(lv.scr_act())
        self.tileview.set_edge_flash(True)
        self.tileview.move_background()

        # Add default main tile
        self.add_tile('Main', (0, 0))
        self.btns = {}

    def haptic(self, duration):
        """Provide haptic feedback for a certain duration (ms)"""
        name = 'haptic' + str(duration)
        if name not in m5stack.timerSch.timerList:
            m5stack.power.setVibrationIntensity(c.vibrationIntensity)
            @m5stack.timerSch.event(name)
            def haptictimer():
                m5stack.power.setVibrationEnable(False)
        m5stack.power.setVibrationEnable(True)
        m5stack.timerSch.run(name, duration, 0x01)
    
    def loading(self, state):
        """Display spinner when the software is loading"""
        self.spinner.move_foreground()
        self.spinner.set_hidden(not state)
    
    def add_tile(self, name, loc):
        """Add a display tile in the specified location.
        Each tile consists of a status bar containing the 
        tile's name and a main window where buttons can be
        placed.
        """
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
        """Fill a tile with entities (i.e. lights). Each entity 
        is displayed as a button, clicking the button will trigger
        the entity's callback function."""
        # Compute the button layout
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
        else:
            print("Please don't add too many buttons to a page.")

        # Place buttons
        for n, entity in enumerate(entities):
            btn = lv.btn(self.tiles[parent]['tile'])
            label = lv.label(btn)
            label.set_text(entity.name)
            btn.set_event_cb(entity.clicked)
            btn.set_pos(locs[n][0]-(btn.get_width()//2), locs[n][1]-(btn.get_height()//2) + c.status_bar_width)
            self.btns[entity.entity_id] = btn

    def add_list(self, entities, parent):
        """Add a list to the current tile.
        Not in use at the moment/not tested recently."""
        lst = lv.list(self.tiles[parent]['tile'])
        lst.set_size(self.hor_res, self.ver_res - 40)
        lst.align(None, lv.ALIGN.IN_BOTTOM_MID, 0, 0)
        lst.set_scroll_propagation(True)
        lst.set_scrollbar_mode(lv.SCROLLBAR_MODE.OFF)

        # Fill list with buttons
        for entity in entities:
            btn = lst.add_btn(entity.symbol, entity.name)
            btn.set_event_cb(entity.clicked)
        self.tiles[parent]['list'] = lst

    def add_btnmatrix(self, entities, parent, width=2):
        """Add a buttonmatrix to the current tile.
        Not in use at the moment/not tested recently."""
        btnm = lv.btnmatrix(self.tiles[parent]['tile'])
        lst.set_size(self.hor_res, self.ver_res - 40)
        lst.align(None, lv.ALIGN.IN_BOTTOM_MID, 0, 0)

        # Fill matrix with buttons
        for entity in entities:
            btn = lst.add_btn(entity.symbol, entity.name)
        self.tiles[parent]['list'] = lst
        
        btn.set_event_cb(entity.clicked)

    def change_entity_options(self, entity):
        """Displays a pop-up window with extra attributes for 
        an entity. Currently supported attributes are: brightness,
        colour temperature, and cover position."""
        # Initiate pop-up window
        cont = lv.cont(lv.scr_act(), None)
        cont.set_auto_realign(True)
        cont.align_mid(None,lv.ALIGN.CENTER,0,0)
        cont.set_fit(lv.FIT.TIGHT)
        cont.set_layout(lv.LAYOUT.COLUMN_MID)
        
        title = lv.label(cont)
        title.set_text(entity.name)

        # Brightness callback
        def update_bright(source, event):
            if event == lv.EVENT.VALUE_CHANGED:
                entity.set_brightness(source.get_value())
                bright_label.set_text('Brightness: ' + str(source.get_value()) + '%')

        # Colour temperature callback
        def update_ct(source, event):
            if event == lv.EVENT.VALUE_CHANGED:
                entity.set_ct(source.get_value())
                ct_label.set_text('Colour temperature: ' + str(source.get_value()) + 'K')

        # Cover position callback
        def update_position(source, event):
            if event == lv.EVENT.VALUE_CHANGED:
                entity.set_position(source.get_value())
                pos_label.set_text('Position: ' + str(source.get_value()) + '%')

        # Exit button callback
        def exit_popup(source, event):
            if event == lv.EVENT.CLICKED:
                cont.fade_out(750, 0)
                sleep_ms(750)
                cont.delete()

        # Add brightness slider if entity supports it
        try:
            if entity.brightness_pct:
                bright_label = lv.label(cont)
                bright_label.set_text('Brightness: ' + str(entity.brightness_pct) + '%')
                
                bright_slider = lv.slider(cont)
                bright_slider.set_range(0, 100)
                bright_slider.set_value(entity.brightness_pct, 0)
                bright_slider.set_event_cb(update_bright)
        except: pass

        # Add colour temperature slider if entity supports it
        try:
            if entity.kelvin:
                ct_label = lv.label(cont)
                ct_label.set_text('Color temperature: ' + str(entity.kelvin) + 'K')
                
                ct_slider = lv.slider(cont)
                ct_slider.set_range(entity.kelvin_min, entity.kelvin_max)
                ct_slider.set_value(entity.kelvin, 0)
                ct_slider.set_event_cb(update_ct)
        except: pass

        # Add cover position slider if entity supports it
        try:
            if entity.open:
                pos_label = lv.label(cont)
                pos_label.set_text('Position: ' + str(entity.open) + '%')
                
                pos_slider = lv.slider(cont)
                pos_slider.set_range(0, 100)
                pos_slider.set_value(entity.open, 0)
                pos_slider.set_event_cb(update_position)
        except: pass

        # Add exit button
        exitbtn = lv.btn(cont)
        exitbtn.set_event_cb(exit_popup)
        exitbtn_label = lv.label(exitbtn)
        exitbtn_label.set_text('Close')

    def set_standby(self):
        """Turn off the display."""
        def standby_cb(source, event):
            if event == lv.EVENT.CLICKED:
                source.delete()
                m5stack.power.setLCDBrightness(self.brightness)
                self.standby = False

        if self.standby == False:
            standbybtn = lv.btn(scr)
            standbybtn.set_size(self.hor_res, self.ver_res)
            standbybtn.set_event_cb(standby_cb)
            m5stack.power.setLCDBrightness(0)
            self.standby = True



def getEntities(entity_registry_path, type):
    """Get the entities from the entity registry belonging to a single group"""
    with open(entity_registry_path, 'r') as f:
        entities = json.load(f)['data'][type]
    ent_dict = {}
    for entity in entities:
        ent_dict[entity['entity_id']] = entity
    return ent_dict

class Light():
    """The Light class stores the parameters, controls, and syncs a single 
    light entity."""
    def __init__(self, entity):
        # Light parameters
        self.entity_id = entity['entity_id']
        self.name = entity['original_name']
        self.topic = 'home/light/' + self.entity_id
        self.symbol = None
        self.on = False
        ha.subscribe(self.topic + '/state', self._state_callback)

        # Add brightness if supported
        try:
            self.brightness_pct = int(entity['brightness_pct'])
            ha.subscribe(self.topic + '/brightness', self._bright_callback)
        except:
            self.brightness_pct = None

        # Add colour temperature if supported
        try:
            self.kelvin = int(entity['kelvin'])
            self.kelvin_max = int(entity['kelvin_max'])
            self.kelvin_min = int(entity['kelvin_min'])
            ha.subscribe(self.topic + '/color_temp', self._ct_callback)
        except:
            self.kelvin = None

    def _state_callback(self, topic_data):
        """Callback to update light state from Home Assistant"""
        self.on = topic_data == 'on'
        if self.on:
            ui.btns[self.entity_id].set_state(3)
        else:
            ui.btns[self.entity_id].set_state(0)

    def _bright_callback(self, topic_data):
        """Callback to update light brightness from Home Assistant"""
        brightness_pct = int(topic_data)*100//255
        self.brightness_pct = brightness_pct

    def _ct_callback(self, topic_data):
        """Callback to update light colour temperature from Home Assistant"""
        mired = int(topic_data)
        self.kelvin = int(1e6//mired)

    def turn_on(self):
        """Turn on the light"""
        ha.publish(self.topic + '/state/set', "on")
        self.on = True

    def turn_off(self):
        """Turn off the light"""
        ha.publish(self.topic + '/state/set', "off")
        self.on = False

    def set_brightness(self, brightness_pct):
        """Set the brightness of the light"""
        brightness = brightness_pct*255//100
        ha.publish(self.topic + '/brightness/set', str(brightness))
        self.on = True
        self.brightness_pct = brightness_pct

    def set_ct(self, kelvin):
        """Set the colour temperature of the light"""
        mired = 1e6//kelvin
        ha.publish(self.topic + '/color_temp/set', str(mired))
        self.on = True
        self.kelvin = kelvin

    def clicked(self, source, event):
        """Callback for when button is clicked"""
        if event == lv.EVENT.SHORT_CLICKED:
            # Short press changes state
            if self.on:
                self.turn_off()
            else:
                self.turn_on()
        elif event == lv.EVENT.LONG_PRESSED:
            # Long press opens pop-up with attributes
            ui.haptic(200)
            ui.change_entity_options(self)

    def clicked_toggle(self, source, event):
        """Callback for when button is clicked and instantly
        updates the button appearance."""
        if event == lv.EVENT.SHORT_CLICKED:
            # Short press changes state
            if self.on:
                self.turn_off()
                source.set_state(0) # not toggled
            else:
                self.turn_on()
                source.set_state(3) # toggled
        elif event == lv.EVENT.LONG_PRESSED:
            # Long press opens pop-up with attributes
            ui.haptic(200)
            ui.change_entity_options(self)

class Blind():
    """The Blind class stores the parameters, controls, and syncs a single 
    cover entity."""
    def __init__(self, entity):
        # Blind parameters
        self.entity_id = entity['entity_id']
        self.name = entity['original_name']
        self.topic = 'home/cover/' + self.entity_id
        self.symbol = None
        self.open = 100
        self.on = self.open == 0
        ha.subscribe(self.topic + '/current_position', self._callback)
    
    def _callback(self, topic_data):
        """Callback to update blind position from Home Assistant"""
        self.open = int(float(topic_data))

    def turn_on(self):
        """Opens the blind. 'turn_on' name is kept for consistency purposes"""
        ha.publish(self.topic + '/current_position/set', 0)
        self.open = 100
        self.on = True

    def turn_off(self):
        """Closes the blind. 'turn_on' name is kept for consistency purposes"""
        ha.publish(self.topic + '/current_position/set', 100)
        self.open = 0
        self.on = False

    def set_position(self, position):
        """Sets blinds to chosen position"""
        ha.publish(self.topic + '/current_position/set', position)
        self.on = True
        self.open = position

    def clicked(self, source, event):
        """Callback for button press"""
        if event == lv.EVENT.SHORT_CLICKED:
            # Short press opens or closes blinds
            if self.on:
                self.turn_off()
            else:
                self.turn_on()
        elif event == lv.EVENT.LONG_PRESSED:
            # Long press opens attributes pop-up
            ui.haptic(200)
            ui.change_entity_options(self)

    def clicked_toggle(self, source, event):
        """Callback for button press. Instantly changes the colour of the 
        button, no verification whether update is sent and received by Home
        Assistant."""
        if event == lv.EVENT.SHORT_CLICKED:
            # Short press opens or closes blinds
            if self.on:
                self.turn_off()
                source.set_state(0) # not toggled
            else:
                self.turn_on()
                source.set_state(3) # toggled
        elif event == lv.EVENT.LONG_PRESSED:
            # Long press opens attributes pop-up
            ui.haptic(200)
            ui.change_entity_options(self)


### SETUP ###

ui = UI()
ui.loading(True) # Start spinner

# Establish MQTT connection with Home Assistant
ha = M5mqtt(c.mqtt_client_id, c.mqtt_server, 1883,
        c.mqtt_user, c.mqtt_password, 300)

# Load entity lists
lights = getEntities(c.entity_registry, 'light')
blinds = getEntities(c.entity_registry, 'cover')


### CONFIG ###
# Load lights per room
hugo_lights = [Light(lights['origami']),
               Light(lights['desklamp']),
               Blind(blinds['tradfri_blind'])]

living_room_lights = [Light(lights['corner_light']),
                      Light(lights['lounge_front']),
                      Light(lights['lounge_back'])]

ui.add_tile('Settings', (0, 1)) # Add settings tile

# Tiles for various rooms, main tile with scenes, lights below 
ui.add_tile('Living Room', (1, 0))
ui.add_tile('Living Room Lights', (1,1))
ui.fill_entities(living_room_lights, 'Living Room Lights')

ui.add_tile('Hugo', (2,0))
ui.add_tile('Hugo Lights', (2,1))
ui.fill_entities(hugo_lights, 'Hugo Lights')

ha.start()

### TESTING ###

# Screen brightness slider on settings page.
screen = M5Screen()
screen.set_screen_brightness(ui.brightness)

def change_brightness(source, event):
    """Change screen brightness callback"""
    if event == lv.EVENT.VALUE_CHANGED:
        ui.brightness = source.get_value()
        screen.set_screen_brightness(source.get_value())
        slider_label.set_text(str(source.get_value()))

slider = lv.slider(ui.tiles['Settings']['tile'])
slider.set_event_cb(change_brightness)
slider.set_width(200)
slider.align(ui.tiles['Settings']['window'], lv.ALIGN.CENTER, 0, 0)
slider.set_range(30, 100)
slider.set_value(ui.brightness, 0)

slider_label=lv.label(ui.tiles['Settings']['tile'])
slider_label.set_text(str(c.brightness))
slider_label.set_auto_realign(True)
slider_label.align(slider,lv.ALIGN.OUT_BOTTOM_MID,0,10)

ui.loading(False) # Stop spinner