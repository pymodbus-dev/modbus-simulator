from kivy.uix.settings import SettingItem
from kivy.properties import (ListProperty,
                             ObjectProperty)
from kivy.compat import text_type
from kivy.lang import Builder

kv = '''<SettingIntegerWithRange>:
    textinput: textinput

    ToggleButton:
        id: override
        text: 'Override'
        pos: root.pos
        on_release: root.override(*args)
        size_hint: (1, .5)
        pos_hint:{'center_x': .5, 'y': 0.25}
    TextInput:
        id:textinput
        text: root.value or ''
        pos: root.pos
        font_size: "15sp"
        multiline: False
        on_text_validate: root._validate(*args)
        size_hint: (1, .5)
        pos_hint:{'center_x': .5, 'y': 0.25}


'''
Builder.load_string(kv)


class SettingIntegerWithRange(SettingItem):
    '''Implementation of a numeric setting with range on top of a
    :class:`SettingNumeric`. It is visualized with a
    :class:`~kivy.uix.label.Label` widget that, when
    clicked, will open a :class:`~kivy.uix.popup.Popup` with a
    :class:`~kivy.uix.textinput.Textinput` so the user can enter a custom
    value.
    '''
    override_values = ListProperty(['0', '1'])
    # override = ObjectProperty(None)
    _override = False

    textinput = ObjectProperty(None)
    default = {}

    def __init__(self, **kwargs):
        self._range = kwargs.get("range", None)
        self.default_key = kwargs.get("default_key", "min")

        if self._range:
            if not isinstance(self._range, (list, tuple)):
                self._range = None
            else:
                if len(self._range) > 1:

                    self.minval = min(self._range)
                    self.maxval = max(self._range)
                    if self.default_key == "min":
                        self.default[self.default_key] = self.minval
                    else:
                        self.default[self.default_key] = self.maxval
                else:
                    self._range = None
                    self.default[self.default_key] = 0
        kwargs.pop("range", None)
        kwargs.pop("default", None)
        super(SettingIntegerWithRange, self).__init__(**kwargs)

    def _dismiss(self, *largs):
        if self.textinput:
            self.textinput.focus = False

    def override(self, btn):
        if btn.state == "down":
            self._override = True
        else:
            self._override = False

    def _validate(self, instance):
        if self._range:
            self._dismiss()
            try:
                value = self.textinput.text.strip()
                value = text_type(int(value))
            except ValueError:
                self.textinput.text = self.value
                return
            if not self._override:
                if self.minval <= int(value) <= self.maxval:
                    self.value = value
                else:
                    self.value = str(self.default[self.default_key])
            else:
                self.value = str(value)

            self.textinput.text = self.value


