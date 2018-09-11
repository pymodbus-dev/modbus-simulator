from random import randint, uniform
from copy import deepcopy
from kivy.adapters.dictadapter import DictAdapter
from kivy.event import EventDispatcher
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.listview import ListItemButton, CompositeListItem, ListView, SelectableView
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown
from modbus_simulator.utils.backgroundJob import BackgroundJob
from pkg_resources import resource_filename

datamodel_template = resource_filename(__name__, "../templates/datamodel.kv")
Builder.load_file(datamodel_template)

integers_dict = {}


class DropBut(SelectableView, Button):
    # drop_list = None
    types = ['int16', 'int32', 'int64', 'uint16', 'uint32', 'uint64',
             'float32', 'float64']
    drop_down = None

    def __init__(self, data_model, **kwargs):
        super(DropBut, self).__init__(**kwargs)
        self.data_model = data_model
        self.drop_down = DropDown()
        for i in self.types:
            btn = Button(text=i, size_hint_y=None, height=45,
                         background_color=(0.0, 0.5, 1.0, 1.0))
            btn.bind(on_release=lambda b: self.drop_down.select(b.text))
            self.drop_down.add_widget(btn)

        self.bind(on_release=self.drop_down.open)
        self.drop_down.bind(on_select=self.on_formatter_select)

    def select_from_composite(self, *args):
        # self.bold = True
        pass

    def deselect_from_composite(self, *args):
        # self.bold = False
        pass

    def on_formatter_select(self, instance, value):
        self.data_model.on_formatter_update(self.index, self.text, value)
        self.text = value


class ErrorPopup(Popup):
    """
    Popup class to display error messages
    """
    def __init__(self, **kwargs):
        # print kwargs
        super(ErrorPopup, self).__init__(**kwargs)
        content = BoxLayout(orientation="vertical")
        content.add_widget(Label(text=kwargs['text'], font_size=20))
        mybutton = Button(text="Dismiss", size_hint=(1,.20), font_size=20)
        content.add_widget(mybutton)
        self.content = content
        self.title = kwargs["title"]
        self.auto_dismiss = False
        self.size_hint = .7, .5
        self.font_size = 20
        mybutton.bind(on_release=self.exit_popup)
        self.open()

    def exit_popup(self, *args):
        self.dismiss()


class ListItemReprMixin(Label):
    """
    repr class for ListItem Composite class
    """
    def __repr__(self):
        text = self.text.encode('utf-8') if isinstance(self.text, unicode) \
            else self.text
        return '<%s text=%s>' % (self.__class__.__name__, text)


class NumericTextInput(SelectableView, TextInput):
    """
    :class:`~kivy.uix.listview.NumericTextInput` mixes
    :class:`~kivy.uix.listview.SelectableView` with
    :class:`~kivy.uix.label.TextInput` to produce a label suitable for use in
    :class:`~kivy.uix.listview.ListView`.
    """
    edit = BooleanProperty(False)

    def __init__(self, data_model, minval, maxval, **kwargs):
        self.minval = minval
        self.maxval = maxval
        self.data_model = data_model
        super(NumericTextInput, self).__init__(**kwargs)
        try:
            self.val = int(self.text)
        except ValueError:
            error = "Only numeric value in range {0}-{1} to be used".format(minval, maxval)
            self.hint_text = error

        self._update_width()
        self.disabled = True

    def _update_width(self):
        if self.data_model.blockname not in ['input_registers',
                                         'holding_registers']:
            self.padding_x = self.width

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and not self.edit:
            self.edit = True
            self.select()
        return super(NumericTextInput, self).on_touch_down(touch)

    def select(self, *args):
        self.disabled = False
        self.bold = True
        if isinstance(self.parent, CompositeListItem):
            for child in self.parent.children:
                # print child.children
                pass
            self.parent.select_from_child(self, *args)

    def deselect(self, *args):
        self.bold = False
        self.disabled = True
        if isinstance(self.parent, CompositeListItem):
            self.parent.deselect_from_child(self, *args)

    def select_from_composite(self, *args):
        self.bold = True

    def deselect_from_composite(self, *args):
        self.bold = False

    def on_text_validate(self, *args):

        try:
            float(self.text)

            if not(self.minval <= float(self.text) <= self.maxval):
                raise ValueError
            self.edit = False
            self.data_model.on_data_update(self.index, self.text)
            self.deselect()
        except ValueError:
            error_text = ("Only numeric value "
                          "in range {0}-{1} to be used".format(self.minval,
                                                               self.maxval))
            ErrorPopup(title="Error", text=error_text)
            self.text = ""
            self.hint_text = error_text
            return

    def on_text_focus(self, instance, focus):
        if focus is False:
            self.text = instance.text
            self.edit = False
            self.deselect()


class UpdateEventDispatcher(EventDispatcher):
    '''
    Event dispatcher for updates in Data Model
    '''
    def __init__(self, **kwargs):
        self.register_event_type('on_update')
        super(UpdateEventDispatcher, self).__init__(**kwargs)

    def on_update(self, _parent, blockname, data):
        Logger.debug("In UpdateEventDispatcher "
                     "on_update {parent:%s,"
                     " blockname: %s, data:%s,}" % (_parent, blockname, data))
        event = data.pop('event', None)
        if event == 'sync_data':
            _parent.sync_data_callback(blockname, data.get('data', {}))
        else:
            old_formatter = data.pop("old_formatter", None)
            _parent.sync_formatter_callback(blockname, data.get('data', {}),
                                            old_formatter)


class DataModel(GridLayout):
    """
    Uses :class:`CompositeListItem` for list item views comprised by two
    :class:`ListItemButton`s and one :class:`ListItemLabel`. Illustrates how
    to construct the fairly involved args_converter used with
    :class:`CompositeListItem`.
    """
    minval = NumericProperty(0)
    maxval = NumericProperty(0)
    simulate = False
    time_interval = 1
    dirty_thread = False
    dirty_model = False
    simulate_timer = None
    simulate = False
    dispatcher = None
    list_view = None
    _parent = None
    is_simulating = False
    blockname = "<BLOCK_NAME_NOT_SET>"

    def __init__(self, **kwargs):
        kwargs['cols'] = 3
        kwargs['size_hint'] = (1.0, 1.0)
        super(DataModel, self).__init__(**kwargs)
        self.init()

    def init(self, simulate=False, time_interval=1, **kwargs):
        """
        Initializes Datamodel

        """
        self.minval = kwargs.get("minval", self.minval)
        self.maxval = kwargs.get("maxval", self.maxval)
        self.blockname = kwargs.get("blockname", self.blockname)
        self.clear_widgets()
        self.simulate = simulate
        self.time_interval = time_interval
        dict_adapter = DictAdapter(data={},
                                   args_converter=self.arg_converter,
                                   selection_mode='single',
                                   allow_empty_selection=True,
                                   cls=CompositeListItem
                                   )

        # Use the adapter in our ListView:
        self.list_view = ListView(adapter=dict_adapter)
        self.add_widget(self.list_view)
        self.dispatcher = UpdateEventDispatcher()
        self._parent = kwargs.get('_parent', None)
        self.simulate_timer = BackgroundJob(
            "simulation",
            self.time_interval,
            self._simulate_block_values
        )

    def clear_widgets(self, make_dirty=False, **kwargs):
        """
        Overidden Clear widget function used while deselecting/deleting slave
        :param make_dirty:
        :param kwargs:
        :return:
        """
        if make_dirty:
            self.dirty_model = True
        super(DataModel, self).clear_widgets(**kwargs)

    def reinit(self, **kwargs):
        """
        Re-initializes Datamodel on change in model configuration from settings
        :param kwargs:
        :return:
        """
        self.minval = kwargs.get("minval", self.minval)
        self.maxval = kwargs.get("maxval", self.maxval)
        time_interval = kwargs.get("time_interval", None)
        try:
            if time_interval and int(time_interval) != self.time_interval:
                self.time_interval = time_interval
                if self.is_simulating:
                    self.simulate_timer.cancel()
                self.simulate_timer = BackgroundJob("simulation", self.time_interval,
                                                     self._simulate_block_values)
                self.dirty_thread = False
                self.start_stop_simulation(self.simulate)
        except ValueError:
            Logger.debug("Error while reinitializing DataModel %s" % kwargs)

    def update_view(self):
        """
        Updates view with listview again
        :return:
        """
        if self.dirty_model:
            self.add_widget(self.list_view)
            self.dirty_model = False

    def get_address(self, offset):
        offset = int(offset)
        if self.blockname == "coils":
            return offset
        elif self.blockname == "discrete_inputs":
            return 10001 + offset if offset < 10001 else offset
        elif self.blockname == "input_registers":
            return 30001 + offset if offset < 30001 else offset
        else:
            return 40001 + offset if offset < 40001 else offset

    def arg_converter(self, index, data):
        """
        arg converter to convert data to list view
        :param index:
        :param data:
        :return:
        """
        _id = self.get_address(self.list_view.adapter.sorted_keys[index])

        payload = {
            'text': str(_id),
            'size_hint_y': None,
            'height': 30,
            'cls_dicts': [
                {
                    'cls': ListItemButton,
                    'kwargs': {'text': str(_id)}
                }
            ]
        }
        if self.blockname in ['input_registers', 'holding_registers']:
            payload['cls_dicts'].extend([
                {
                    'cls': NumericTextInput,
                    'kwargs': {
                        'data_model': self,
                        'minval': self.minval,
                        'maxval': self.maxval,
                        'text': str(data['value']),
                        'multiline': False,
                        'is_representing_cls': True,

                    }
                },
                {
                    'cls': DropBut,
                    'kwargs': {
                        'data_model': self,
                        'text': data.get('formatter', 'uint16')
                    }
                }
            ]
            )
        else:
            payload['cls_dicts'].append(
                {
                    'cls': NumericTextInput,
                    'kwargs': {
                        'data_model': self,
                        'minval': self.minval,
                        'maxval': self.maxval,
                        'text': str(data['value']),
                        'multiline': False,
                        'is_representing_cls': True,

                    }
                }
            )

        return payload

    def add_data(self, data):
        """
        Adds data to the Data model
        :param data:
        :param item_strings:
        :return:
        """
        item_strings = []
        self.update_view()
        current_keys = self.list_view.adapter.sorted_keys
        next_index = 0
        if current_keys:
            next_index = int(max(current_keys)) + 1
        data = {self.get_address(int(offset) + next_index): v
                for offset, v in data.items()}
        for offset, d in data.items():
            # offset = self.get_address(offset)
            item_strings.append(offset)
            if offset >= 30001:
                if not d.get('formatter'):
                    d['formatter'] = 'uint16'

        self.list_view.adapter.data.update(data)
        self.list_view._trigger_reset_populate()
        return self.list_view.adapter.data, item_strings

    def delete_data(self, item_strings):
        """
        Delete data from data model
        :param item_strings:
        :return:
        """
        selections = self.list_view.adapter.selection
        items_popped = []
        for item in selections:
            index_popped = item_strings.pop(item_strings.index(int(item.text)))
            self.list_view.adapter.data.pop(int(item.text), None)
            self.list_view.adapter.update_for_new_data()
            self.list_view._trigger_reset_populate()
            items_popped.append(index_popped)
        return items_popped,  self.list_view.adapter.data

    def on_selection_change(self, item):
        pass

    def on_data_update(self, index, data):
        """
        Call back function to update data when data is changed in the list view
        :param index:
        :param data:
        :return:
        """
        index = self.get_address(self.list_view.adapter.sorted_keys[index])
        try:
            self.list_view.adapter.data[index]
        except KeyError:
            index = str(index)
        if self.blockname in ['input_registers', 'holding_registers']:
            self.list_view.adapter.data[index]['value'] = float(data)
        else:
            self.list_view.adapter.data.update({index: float(data)})
        self.list_view._trigger_reset_populate()
        data = {'event': 'sync_data',
                'data': {index: self.list_view.adapter.data[index]}}
        self.dispatcher.dispatch('on_update',
                                 self._parent,
                                 self.blockname,
                                 data)

    def on_formatter_update(self, index, old, new):
        """
        Callback function to use the formatter selected in the list view
        Args:
            index:
            data:

        Returns:

        """
        index = self.get_address(self.list_view.adapter.sorted_keys[index])
        # index = self.get_address(int(index))
        try:
            self.list_view.adapter.data[index]['formatter'] = new
        except KeyError:
            index = str(index)
            self.list_view.adapter.data[index]['formatter'] = new
        _data = {'event': 'sync_formatter',
                 'old_formatter': old,
                 'data': {index: self.list_view.adapter.data[index]}}
        self.dispatcher.dispatch('on_update', self._parent,
                                 self.blockname, _data)
        self.list_view._trigger_reset_populate()

    def update_registers(self, new_values, update_info):
        # new_values = deepcopy(new_values)
        offset = update_info.get('offset')
        count = update_info.get('count')
        to_remove = None
        if count > 1:
            offset = int(offset)
            to_remove = [str(o) for o in list(xrange(offset+1, offset+count))]

        self.list_view.adapter.update_for_new_data()
        self.refresh(new_values, to_remove)
        return self.list_view.adapter.data

    def refresh(self, data={}, to_remove=None):
        """
        Data model refresh function to update when the view when slave is
        selected
        :param data:
        :param to_remove:
        :return:
        """
        self.update_view()
        self.list_view.adapter.data.update(data)
        if to_remove:
            for entry in to_remove:
                removed = self.list_view.adapter.data.pop(entry, None)
                if not removed:
                    self.list_view.adapter.data.pop(int(entry), None)
        self.list_view.disabled = False
        self.list_view._trigger_reset_populate()

    def start_stop_simulation(self, simulate):
        """
        Starts or stops simulating data
        :param simulate:
        :return:
        """
        self.simulate = simulate

        if self.simulate:
            if self.dirty_thread:
                self.simulate_timer = BackgroundJob(
                    "simulation",
                    self.time_interval,
                    self._simulate_block_values
                )
            self.simulate_timer.start()
            self.dirty_thread = False
            self.is_simulating = True
        else:
            self.simulate_timer.cancel()
            self.dirty_thread = True
            self.is_simulating = False

    def _simulate_block_values(self):
        if self.simulate:
            data = self.list_view.adapter.data
            if data:
                for index, value in data.items():
                    if self.blockname in ['input_registers',
                                          'holding_registers']:
                        if 'float' in data[index]['formatter']:
                            value = round(uniform(self.minval, self.maxval), 2)
                        else:
                            value = randint(self.minval, self.maxval)
                            if 'uint' in data[index]['formatter']:
                                value = abs(value)
                    else:
                        value = randint(self.minval, self.maxval)

                    data[index]['value'] = value
                self.refresh(data)
                data = {'event': 'sync_data',
                        'data': data}
                self.dispatcher.dispatch('on_update',
                                         self._parent,
                                         self.blockname,
                                         data)

    def reset_block_values(self):
        if not self.simulate:
            data = self.list_view.adapter.data
            if data:
                for index, value in data.items():
                    data[index]['value'] = 1
                self.list_view.adapter.data.update(data)
                self.list_view.disabled = False
                self.list_view._trigger_reset_populate()
                self._parent.sync_data_callback(self.blockname,
                                                self.list_view.adapter.data)
