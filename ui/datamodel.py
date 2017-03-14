from random import randint

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

from utils.backgroundJob import BackgroundJob

Builder.load_file("templates/datamodel.kv")

integers_dict = {}


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

        super(NumericTextInput, self).__init__(**kwargs)
        try:
            self.val = int(self.text)
        except ValueError:
            error = "Only numeric value in range {0}-{1} to be used".format(minval, maxval)
            self.hint_text = error
        self.padding_x = self.width
        self.disabled = True
        self.data_model = data_model

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
            int(self.text)

            if not(self.minval <= int(self.text) <= self.maxval):
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
        _parent.sync_data_callback(blockname, data)


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
        kwargs['cols'] = 2
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

    def arg_converter(self, index, data):
        """
        arg converter to convert data to list view
        :param index:
        :param data:
        :return:
        """
        _id = self.list_view.adapter.sorted_keys[index]
        return {
            'text': str(_id),
            'size_hint_y': None,
            'height': 30,
            'cls_dicts': [
                {
                    'cls': ListItemButton,
                    'kwargs': {'text': str(_id)}
                },
                {
                    'cls': NumericTextInput,
                    'kwargs': {
                        'data_model': self,
                        'minval': self.minval,
                        'maxval': self.maxval,
                        'text': str(data),
                        'multiline': False,
                        'is_representing_cls': True,

                        
                    }
                },
            ]
        }

    def add_data(self, data, item_strings):
        """
        Adds data to the Data model
        :param data:
        :param item_strings:
        :return:
        """
        self.update_view()
        last_index = len(item_strings)
        if last_index in item_strings:
            last_index = int(item_strings[-1]) + 1
        item_strings.append(last_index)
        self.list_view.adapter.data.update({last_index: data})
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
            data_popped = self.list_view.adapter.data.pop(int(item.text), None)
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
        self.list_view.adapter.data.update({index: data})
        self.list_view._trigger_reset_populate()
        self.dispatcher.dispatch('on_update', self._parent, self.blockname,
                                 self.list_view.adapter.data)

    def refresh(self, data={}):
        """
        Data model refresh function to update when the view when slave is
        selected
        :param data:
        :return:
        """
        self.update_view()
        self.list_view.adapter.data = data
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
                    data[index] = randint(self.minval, self.maxval)
                    # print self.minval, self.maxval, data[index]
                self.refresh(data)
                self.dispatcher.dispatch('on_update',
                                         self._parent,
                                         self.blockname,
                                         self.list_view.adapter.data)

    def reset_block_values(self):
        if not self.simulate:
            data = self.list_view.adapter.data
            if data:
                for index, value in data.items():
                    data[index] = 1
                self.list_view.adapter.data = data
                self.list_view.disabled = False
                self.list_view._trigger_reset_populate()
                self._parent.sync_data_callback(self.blockname, self.list_view.adapter.data)
