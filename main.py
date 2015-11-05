'''
Modbus Simu App
===============
'''
import kivy
kivy.require('1.4.2')
from kivy.app import App
from kivy.properties import ObjectProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.settings import (Settings, SettingsWithSidebar)
import DataModel
from modbus import ModBusSimu, BLOCK_TYPES, configure_modbus_logger
from settings import SettingIntegerWithRange
from backgroundJob import BackgroundJob
import re
import os

MAP = {
    "coils": "coils",
    'discrete inputs': 'discrete_inputs',
    'input registers': 'input_registers',
    'holding registers': 'holding_registers'
}


class FloatInput(TextInput):
    pat2 = re.compile(r'\d+(?:,\d+)?')
    pat = re.compile('[^0-9]')
    def insert_text(self, substring, from_undo=False):
        pat = self.pat
        if '.' in self.text:
            s = re.sub(pat, '', substring)
        else:
            s = '.'.join([re.sub(pat, '', s) for s in substring.split('.', 1)])
        return super(FloatInput, self).insert_text(s, from_undo=from_undo)


class Gui(BoxLayout):
    '''
    Gui of widgets. This is the root widget of the app.
    '''

    # ---------------------GUI------------------------ #
    # Checkbox to select between tcp/serial
    interfaces = ObjectProperty()

    # Boxlayout to hold interface settings
    interface_settings = ObjectProperty()

    # TCP port
    port = ObjectProperty()

    # Toggle button to start/stop modbus server
    start_stop_server = ObjectProperty()

    # Container for slave list
    slave_pane = ObjectProperty()
    # slave start address textbox
    slave_start_add = ObjectProperty()
    # slave end address textbox
    slave_end_add = ObjectProperty()
    # Slave device count text box
    slave_count = ObjectProperty()
    # Slave list
    slave_list = ObjectProperty()

    # Container for modbus data models
    data_model_loc = ObjectProperty()
    # Tabbed panel to hold various modbus datamodels
    data_models = ObjectProperty()

    # Data models
    data_model_coil = ObjectProperty()
    data_model_discrete_inputs = ObjectProperty()
    data_model_input_registers = ObjectProperty()
    data_model_holding_registers = ObjectProperty()

    # Helpers
    slaves = ["%s" %i for i in xrange(1, 248)]
    data_map = {}
    active_slave = None
    server_running = False
    simulating = False
    simu_time_interval = None
    anim = None
    restart_simu = False
    sync_modbus_thread = None
    sync_modbus_time_interval = 5

    def __init__(self, cfg, **kwargs):
        super(Gui, self).__init__(**kwargs)
        time_interval = kwargs.get("time_interval", 1)

        self.slave_list.adapter.bind(on_selection_change=self.select_slave)
        self.data_model_loc.disabled = True
        self.slave_pane.disabled = True
        minval = kwargs.get("bin_min_val", 0)
        maxval = kwargs.get("bin_max_val", 1)
        self.data_model_coil.init(
            blockname="coils",
            simulate=self.simulating,
            time_interval=time_interval,
            minval=minval,
            maxval=maxval,
            _parent=self
        )
        self.data_model_discrete_inputs.init(
            blockname="discrete_inputs",
            simulate=self.simulating,
            time_interval=time_interval,
            minval=minval,
            maxval=maxval,
            _parent=self
        )
        minval = kwargs.get("reg_min_val", 0)
        maxval = kwargs.get("reg_max_val", 65535)
        self.block_start = kwargs.get("block_start", 0)
        self.block_size = kwargs.get("block_size", 100)
        self.data_model_input_registers.init(
            blockname="input_registers",
            simulate=self.simulating,
            time_interval=time_interval,
            minval=minval,
            maxval=maxval,
            _parent=self
        )
        self.data_model_holding_registers.init(
            blockname="holding_registers",
            simulate=self.simulating,
            time_interval=time_interval,
            minval=minval,
            maxval=maxval,
            _parent=self
        )
        self.data_model_loc.disabled = True
        configure_modbus_logger(cfg)
        self.modbus_device = ModBusSimu(port=int(self.port.text))
        self.simu_time_interval = time_interval
        self.sync_modbus_thread = BackgroundJob(
            "modbus_sync",
            self.sync_modbus_time_interval,
            self._sync_modbus_block_values
        )
        self.sync_modbus_thread.start()

    def start_server(self, btn):       
        if btn.state == "down":
            self.modbus_device.start()
            self.server_running = True
            self.interface_settings.disabled = True
            self.interfaces.disabled = True
            self.slave_pane.disabled = False
            if len(self.slave_list.adapter.selection):
                self.data_model_loc.disabled = False
                if self.simulating:
                    self._simulate()

            btn.text = "Stop"

        else:
            self.simulating = False
            self._simulate()
            self.modbus_device.stop()
            self.server_running = False
            self.interface_settings.disabled = False
            self.interfaces.disabled = False
            self.slave_pane.disabled = True
            self.data_model_loc.disabled = True
            btn.text = "Start"

    def update_tcp_connection_info(self, checkbox, value):
        if value:
            self.interface_settings.current = checkbox
            tcp_label = Label(text="Port")
            tcp_input = TextInput(text="5440", multiline=False)
            self.interface_settings.add_widget(tcp_label)
            self.interface_settings.add_widget(tcp_input)
        else:
            self.interface_settings.clear_widgets()

    def update_serial_connection_info(self, checkbox, value):
        if value:
            self.interface_settings.current = checkbox
            serial_label = Label(text="Serial Settings not supported !!")
            self.interface_settings.add_widget(serial_label)
        else:
            self.interface_settings.clear_widgets()

    def show_error(self, e):
        self.info_label.text = str(e)
        self.anim = Animation(top=190.0, opacity=1, d=2, t='in_back') +\
            Animation(top=190.0, d=3) +\
            Animation(top=0, opacity=0, d=2)
        self.anim.start(self.info_label)

    def add_slaves(self, *args):
        selected = self.slave_list.adapter.selection
        data = self.slave_list.adapter.data
        ret = self._process_slave_data(data)
        if ret[0]:
            start_slave_add, slave_count = ret[1:]
        else:
            return
        for slave_to_add in xrange(start_slave_add,
                                   start_slave_add + slave_count):
            if str(slave_to_add) in self.data_map:
                return
            self.data_map[str(slave_to_add)] = {
                "coils": {
                    'data': {},
                    'item_strings': [],
                    "instance": self.data_model_coil,
                    "dirty": False
                },
                "discrete_inputs": {
                    'data': {},
                    'item_strings': [],
                    "instance": self.data_model_discrete_inputs,
                    "dirty": False
                },
                "input_registers": {
                    'data': {},
                    'item_strings': [],
                    "instance": self.data_model_input_registers,
                    "dirty": False
                },
                "holding_registers": {
                    'data': {},
                    'item_strings': [],
                    "instance": self.data_model_holding_registers,
                    "dirty": False
                }
            }

            self.modbus_device.add_slave(slave_to_add)
            for block_name, block_type in BLOCK_TYPES.items():
                self.modbus_device.add_block(slave_to_add,
                    block_name, block_type, self.block_start, self.block_size)

            data.append(str(slave_to_add))
        self.slave_list.adapter.data = data
        self.slave_list._trigger_reset_populate()
        for item in selected:
            index = self.slave_list.adapter.data.index(item.text)
            if not self.slave_list.adapter.get_view(index).is_selected:
                self.slave_list.adapter.get_view(index).trigger_action(
                    duration=0
                )
        self.slave_start_add.text = str(start_slave_add + slave_count)
        self.slave_end_add.text = self.slave_start_add.text
        self.slave_count.text = "1"

    def _process_slave_data(self, data):
        success = True
        data = sorted(data, key=int)
        # last_slave = 1 if not len(data) else data[-1]
        starting_address = int(self.slave_start_add.text)
        end_address = int(self.slave_end_add.text)
        if end_address < starting_address:
            end_address = starting_address
        try:
            slave_count = int(self.slave_count.text)
        except ValueError:
            slave_count = 1

        if str(starting_address) in data:
            self.show_error("slave already present (%s)" % starting_address)
            success = False
            return [success]
        if starting_address < 1:
            self.show_error("slave address (%s)"
                            " should be greater than 0 "% starting_address)
            success = False
            return [success]
        if starting_address > 247:
            self.show_error("slave address (%s)"
                            " beyond supported modbus slave "
                            "device address (247)" % starting_address)
            success = False
            return [success]

        size = (end_address - starting_address) + 1
        size = slave_count if slave_count > size else size

        if (size + starting_address) > 247:
            self.show_error("address range (%s) beyond "
                            "allowed modbus slave "
                            "devices(247)" % (size + starting_address))
            success = False
            return [success]
        self.slave_end_add.text = str(starting_address + size - 1)
        self.slave_count.text = str(size)
        return success, starting_address, size

    def delete_slaves(self, *args):
        selected = self.slave_list.adapter.selection
        slave = self.active_slave
        ct = self.data_models.current_tab
        for item in selected:
            self.modbus_device.remove_slave(int(item.text))
            self.slave_list.adapter.data.remove(item.text)
            self.slave_list._trigger_reset_populate()
            ct.content.clear_widgets(make_dirty=True)
            if self.simulating:
                self.simulating = False
                self.restart_simu = True
                self._simulate()
            self.data_map.pop(slave)

    def update_data_models(self, *args):
        ct = self.data_models.current_tab
        current_tab = MAP[ct.text]

        ct.content.update_view()
        # self.data_map[self.active_slave][current_tab]['dirty'] = False
        _data = self.data_map[self.active_slave][current_tab]
        item_strings = _data['item_strings']
        if len(item_strings) < self.block_size:
            updated_data, item_strings = ct.content.add_data(1, item_strings)
            _data['data'].update(updated_data)
            _data['item_strings'] = item_strings
            for k, v in updated_data.iteritems():
                self.modbus_device.set_values(int(self.active_slave),
                                              current_tab, k, v)
        else:
            msg = ("OutOfModbusBlockError: address %s"
                   " is out of block size %s" %(len(item_strings),
                                                self.block_size))
            self.show_error(msg)

    def sync_data_callback(self, blockname, data):
        ct = self.data_models.current_tab
        current_tab = MAP[ct.text]
        if blockname != current_tab:
            current_tab = blockname
        try:
            _data = self.data_map[self.active_slave][current_tab]
            _data['data'].update(data)
            for k, v in data.iteritems():
                self.modbus_device.set_values(int(self.active_slave),
                                              current_tab, k, int(v))
        except KeyError:
            pass

    def delete_data_entry(self, *args):
        ct = self.data_models.current_tab
        current_tab = MAP[ct.text]
        _data = self.data_map[self.active_slave][current_tab]
        item_strings = _data['item_strings']
        deleted, data = ct.content.delete_data(item_strings)
        dm = _data['data']
        for index in deleted:
            dm.pop(index, None)

        if deleted:
            self.update_backend(int(self.active_slave), current_tab, data)
            msg = ("modbus-tk do not support deleting "
               "individual modbus register/discrete_inputs/coils"
               "The data is removed from GUI and the corresponding value is"
               "updated to '0' in backend . ")
            self.show_error(msg)

    def select_slave(self, adapter):
        ct = self.data_models.current_tab
        if len(adapter.selection) != 1:
            # Multiple selection - No Data Update
            ct.content.clear_widgets(make_dirty=True)
            if self.simulating:
                self.simulating = False
                self.restart_simu = True
                self._simulate()
            self.data_model_loc.disabled = True
            self.active_slave = None

        else:
            self.data_model_loc.disabled = False
            if self.restart_simu:
                self.simulating = True
                self.restart_simu = False
                self._simulate()
            self.active_slave = self.slave_list.adapter.selection[0].text
            self.refresh()

    def refresh(self):
        for child in self.data_models.tab_list:
            dm = self.data_map[self.active_slave][MAP[child.text]]['data']
            child.content.refresh(dm)

    def update_backend(self, slave_id, blockname, new_data, ):
        self.modbus_device.remove_block(slave_id, blockname)
        self.modbus_device.add_block(slave_id, blockname,
                                     BLOCK_TYPES[blockname], 0, 100)
        for k, v in new_data.iteritems():
            self.modbus_device.set_values(slave_id, blockname, k, int(v))

    def change_simulation_settings(self, **kwargs):
        self.data_model_coil.reinit(**kwargs)
        self.data_model_discrete_inputs.reinit(**kwargs)
        self.data_model_input_registers.reinit(**kwargs)
        self.data_model_holding_registers.reinit(**kwargs)

    def change_datamodel_settings(self, key, value):
        if "max" in key:
            data = {"maxval": int(value)}
        else:
            data = {"minval": int(value)}

        if "bin" in key:
            self.data_model_coil.reinit(**data)
            self.data_model_discrete_inputs.reinit(**data)
        else:
            self.data_model_input_registers.reinit(**data)
            self.data_model_holding_registers.reinit(**data)

    def start_stop_simulation(self, btn):
        if btn.state == "down":
            self.simulating = True
        else:
            self.simulating = False
            if self.restart_simu:
                self.restart_simu = False
        self._simulate()

    def _simulate(self):
        self.data_model_coil.start_stop_simulation(self.simulating)
        self.data_model_discrete_inputs.start_stop_simulation(self.simulating)
        self.data_model_input_registers.start_stop_simulation(self.simulating)
        self.data_model_holding_registers.start_stop_simulation(
            self.simulating)

    def _sync_modbus_block_values(self):
        """
        track external changes in modbus block values and sync GUI
        ToDo:
        A better way to update GUI when simulation is on going  !!
        """
        if not self.simulating:
            if self.active_slave:
                _data_map = self.data_map[self.active_slave]
                for block_name, value in _data_map.items():
                    updated = {}
                    for k, v in value['data'].items():
                        actual_data = self.modbus_device.get_values(
                            int(self.active_slave),
                            block_name,
                            int(k),
                            1
                        )
                        if actual_data[0] != int(v):
                            updated[k] = actual_data[0]
                    if updated:
                        value['data'].update(updated)
                        self.refresh()


setting_panel = """
[
  {
    "type": "title",
    "title": "Modbus Settings"
  },
  {
    "type": "string",
    "title": "IP",
    "desc": "Modbus Server IP address",
    "section": "Modbus", "key": "IP"
  },
  {
    "type": "numeric",
    "title": "Block Start",
    "desc": "Modbus Block Start index",
    "section": "Modbus", "key": "Block Start"
  },
  { "type": "numeric",
    "title": "Block Size",
    "desc": "Modbus Block Size for various registers/coils/inputs",
    "section": "Modbus", "key": "Block Size"
  },
  {
    "type": "numeric_range",
    "title": "Coil/Discrete Input MinValue",
    "desc": "Minimum value a coil/discrete input can hold (0).An invalid value will be discarded unless Override flag is set",
    "section": "Modbus",
    "key": "bin min",
    "range": [0,0]
  },
  {
    "type": "numeric_range",
    "title": "Coil/Discrete Input MaxValue",
    "desc": "Maximum value a coil/discrete input can hold (1). An invalid value will be discarded unless Override flag is set",
    "section": "Modbus",
    "key": "bin max",
    "range": [1,1]

  },
  {
    "type": "numeric_range",
    "title": "Holding/Input register MinValue",
    "desc": "Minimum value a registers can hold (0).An invalid value will be discarded unless Override flag is set",
    "section": "Modbus",
    "key": "reg min",
    "range": [0,65535]
  },
  {
    "type": "numeric_range",
    "title": "Holding/Input register MaxValue",
    "desc": "Maximum value a register input can hold (65535). An invalid value will be discarded unless Override flag is set",
    "section": "Modbus",
    "key": "reg max",
    "range": [0,65535]
  },
  {
    "type": "title",
    "title": "Logging"
  },
  { "type": "bool",
    "title": "Modbus Master Logging Control",
    "desc": " Enable/Disable Modbus Logging (console/file)",
    "section": "Logging",
    "key": "logging"
  },
  { "type": "bool",
    "title": "Modbus Console Logging",
    "desc": " Enable/Disable Modbus Console Logging",
    "section": "Logging",
    "key": "console logging"
  },
  {
    "type": "options",
    "title": "Modbus console log levels",
    "desc": "Log levels for modbus_tk",
    "section": "Logging",
    "key": "console log level",
    "options": ["INFO", "WARNING", "DEBUG", "CRITICAL"]
  },
  { "type": "bool",
    "title": "Modbus File Logging",
    "desc": " Enable/Disable Modbus File Logging",
    "section": "Logging",
    "key": "file logging"
  },
  {
    "type": "options",
    "title": "Modbus file log levels",
    "desc": "file Log levels for modbus_tk",
    "section": "Logging",
    "key": "file log level",
    "options": ["INFO", "WARNING", "DEBUG", "CRITICAL"]
  },

  {
    "type": "path",
    "title": "Modbus log file",
    "desc": "Modbus log file (changes takes place only after next start of app)",
    "section": "Logging",
    "key": "log file"
  },
  {
    "type": "title",
    "title": "Simulation"
  },
  {
    "type": "numeric",
    "title": "Time interval",
    "desc": "When simulation is enabled, data is changed for eveery 'n' seconds defined here",
    "section": "Simulation",
    "key": "time interval"
  }


]
"""


class ModbusSimuApp(App):
    '''The kivy App that runs the main root. All we do is build a Gui
    widget into the root.'''
    gui = None
    title = "Modbus Simulator"
    settings_cls = None
    use_kivy_settings = True
    settings_cls = SettingsWithSidebar

    def build(self):
        cfg = {
            'no_modbus_log': not bool(eval(
                self.config.get("Logging", "logging"))),
            'no_modbus_console_log': not bool(
                eval(self.config.get("Logging", "console logging"))),
            'modbus_console_log_level': self.config.get("Logging",
                                                        "console log level"),
            'modbus_file_log_level': self.config.get("Logging",
                                                        "file log level"),
            'no_modbus_file_log': not bool(eval(
                self.config.get("Logging", "file logging"))),

            'modbus_log': os.path.join(self.user_data_dir, 'modbus.log')
        }
        time_interval = int(eval(self.config.get("Simulation",
                                                  "time interval")))
        bin_min_val = int(eval(self.config.get("Modbus",
                                                  "bin min")))
        bin_max_val = int(eval(self.config.get("Modbus",
                                                  "bin max")))
        reg_min_val = int(eval(self.config.get("Modbus",
                                                  "reg min")))
        reg_max_val = int(eval(self.config.get("Modbus",
                                                  "reg max")))
        block_start = int(eval(self.config.get("Modbus",
                                               "block start")))
        block_size = int(eval(self.config.get("Modbus",
                                              "block size")))
        self.gui = Gui(
            cfg,
            time_interval=time_interval,
            bin_min_val=bin_min_val,
            bin_max_val=bin_max_val,
            reg_min_val=reg_min_val,
            reg_max_val=reg_max_val,
            block_start=block_start,
            block_size=block_size
        )
        return self.gui

    def on_pause(self):
        return True

    def on_stop(self):
        if self.gui.server_running:
            if self.gui.simulating:
                self.gui.simulating = False
                self.gui._simulate()
            self.gui.modbus_device.stop()
        self.gui.sync_modbus_thread.cancel()

    def show_settings(self, btn):
        self.open_settings()

    def build_config(self, config):
        config.add_section('Modbus')
        config.set('Modbus', "ip", '127.0.0.1')
        config.set('Modbus', "block start", 0)
        config.set('Modbus', "block size", 100)
        config.set('Modbus', "bin min", 0)
        config.set('Modbus', "bin max", 1)
        config.set('Modbus', "reg min", 0)
        config.set('Modbus', "reg max", 65535)

        config.add_section('Logging')
        config.set('Logging', "log file",  os.path.join(self.user_data_dir,
                                                        'modbus.log'))

        config.set('Logging', "logging", 1)
        config.set('Logging', "console logging", 1)
        config.set('Logging', "console log level", "DEBUG")
        config.set('Logging', "file log level", "DEBUG")
        config.set('Logging', "file logging", 1)

        config.add_section('Simulation')
        config.set('Simulation', 'time interval', 1)

    def build_settings(self, settings):
        settings.register_type("numeric_range", SettingIntegerWithRange)
        settings.add_json_panel('Modbus Settings', self.config,
                                data=setting_panel
                                )

    def on_config_change(self, config, section, key, value):
        if config is not self.config:
            return
        token = section, key
        if token == ("Simulation", "time interval"):
            self.gui.change_simulation_settings(time_interval=eval(value))
        if section == "Modbus" and key in ("bin max",
                                           "bin min", "reg max",
                                           "reg min", "override"):
            self.gui.change_datamodel_settings(key, value)
        if section == "Modbus" and key == "block start":
            self.gui.block_start = int(value)
        if section == "Modbus" and key == "block size":
            self.gui.block_size = int(value)

    def close_settings(self, *args):
        super(ModbusSimuApp, self).close_settings()


if __name__ == "__main__":
    ModbusSimuApp().run()
