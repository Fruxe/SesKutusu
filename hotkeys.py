from __future__ import annotations
from i18n import tr
import ctypes
import sys
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer, Qt, Signal
from PySide6.QtWidgets import QLineEdit

STOP_HOTKEY = 'Ctrl+Alt+F10'


NUMPAD_KEYS = {**{str(i): 0x60+i for i in range(10)},
               'ADD': 0x6B, 'SUBTRACT': 0x6D, 'MULTIPLY': 0x6A,
               'DIVIDE': 0x6F, 'DECIMAL': 0x6E}
NUMPAD_LABELS = {value: 'NumPad'+key.title() for key,value in NUMPAD_KEYS.items()}


def parse_hotkey(text):
    parts = text.upper().replace('CONTROL', 'CTRL').replace(' ', '').split('+')
    mods = 0x4000
    flags = {'ALT': 1, 'CTRL': 2, 'SHIFT': 4}
    keypad = False
    for part in parts[:-1]:
        if part == 'NUM':keypad = True;continue  # Qt portable keypad notation
        if part not in flags: raise ValueError('Use a single combination with Ctrl, Alt or Shift.')
        mods |= flags[part]
    key = parts[-1]
    if key.startswith('NUMPAD'):keypad=True;key=key[6:]
    elif key.startswith('NUM') and key[3:].isdigit():keypad=True;key=key[3:]
    if keypad:
        if key not in NUMPAD_KEYS:raise ValueError('Use NumPad 0–9, Add, Subtract, Multiply, Divide or Decimal.')
        return mods, NUMPAD_KEYS[key]
    function_key = key.startswith('F') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24
    if key == 'F12': raise ValueError('F12 is reserved for the Windows debugger. Choose another key.')
    if len(key) == 1 and key.isascii() and key.isalnum(): vk = ord(key)
    elif key == 'SPACE': vk = 0x20
    elif function_key: vk = 0x6f + int(key[1:])
    else: raise ValueError('Use a letter, digit, function key or numpad key.')
    if mods & 15 == 0 and not function_key:
        raise ValueError('Add Ctrl, Alt or Shift to letters and digits. Function and numpad keys can be used alone.')
    return mods, vk


def hotkey_from_event(event):
    key=event.key();modifiers=event.modifiers()
    if key in (Qt.Key.Key_Control,Qt.Key.Key_Alt,Qt.Key.Key_Shift,Qt.Key.Key_Meta):return None
    if key==Qt.Key.Key_Escape:return None
    prefixes=[]
    for modifier,name in [(Qt.KeyboardModifier.ControlModifier,'Ctrl'),(Qt.KeyboardModifier.AltModifier,'Alt'),(Qt.KeyboardModifier.ShiftModifier,'Shift')]:
        if modifiers & modifier:prefixes.append(name)
    native=event.nativeVirtualKey()
    keypad=bool(modifiers & Qt.KeyboardModifier.KeypadModifier) or native in NUMPAD_LABELS
    if keypad:
        if native in NUMPAD_LABELS:value=NUMPAD_LABELS[native]
        elif Qt.Key.Key_0<=key<=Qt.Key.Key_9:value='NumPad'+str(key-Qt.Key.Key_0)
        else:
            operators={Qt.Key.Key_Plus:'NumPadAdd',Qt.Key.Key_Minus:'NumPadSubtract',Qt.Key.Key_Asterisk:'NumPadMultiply',Qt.Key.Key_Slash:'NumPadDivide',Qt.Key.Key_Period:'NumPadDecimal',Qt.Key.Key_Comma:'NumPadDecimal'}
            if key not in operators:raise ValueError('This numpad key is unsupported. Enable NumLock for digits.')
            value=operators[key]
    elif Qt.Key.Key_A<=key<=Qt.Key.Key_Z or Qt.Key.Key_0<=key<=Qt.Key.Key_9:value=chr(key)
    elif Qt.Key.Key_F1<=key<=Qt.Key.Key_F24:value='F'+str(key-Qt.Key.Key_F1+1)
    elif key==Qt.Key.Key_Space:value='Space'
    else:raise ValueError('Choose a letter, digit, function key or numpad key.')
    return '+'.join(prefixes+[value])


class HotkeyEdit(QLineEdit):
    capture_error=Signal(str)
    def __init__(self,text='',parent=None):
        super().__init__(text,parent)
        self.setReadOnly(True)
        self.setPlaceholderText(tr('Press a key or combination…'))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            super().keyPressEvent(event);return
        if event.isAutoRepeat():event.accept();return
        if event.key() in (Qt.Key.Key_Backspace,Qt.Key.Key_Delete) and not event.modifiers():
            self.clear();self.capture_error.emit('');event.accept();return
        try:
            value=hotkey_from_event(event)
            if value is not None:self.setText(value);self.capture_error.emit('')
        except ValueError as error:self.capture_error.emit(str(error))
        event.accept()
    def keyReleaseEvent(self,event):event.accept()


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.bindings = {}
        self.registered = []
        self.errors = {}
        self.enabled = True
        self.next_id = 0x1000
        self.user32 = ctypes.WinDLL('user32', use_last_error=True) if sys.platform == 'win32' else None
        if self.user32:
            self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self.user32.RegisterHotKey.restype = wintypes.BOOL
            self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.UnregisterHotKey.restype = wintypes.BOOL

    def clear(self):
        if self.user32:
            for ident in self.registered: self.user32.UnregisterHotKey(None, ident)
        self.registered = []
        self.bindings = {}
        self.errors = {}

    def register(self, entries):
        self.clear()
        failures = []
        if not self.user32: return ['Global hotkeys are available on Windows only.']
        all_bindings = [('stop', STOP_HOTKEY)] + [(entry['id'], entry.get('hotkey', '')) for entry in entries]
        for action, text in all_bindings:
            if not text: continue
            ident = self.next_id
            self.next_id = self.next_id + 1 if self.next_id < 0xBFFF else 0x1000
            try:
                mods, key = parse_hotkey(text)
                if not self.user32.RegisterHotKey(None, ident, mods, key):
                    raise ValueError(tr('Another application uses this combination.'))
                self.bindings[ident] = action
                self.registered.append(ident)
            except ValueError as error:
                self.errors[action] = str(error)
                failures.append(f'{text}: {error}')
        return failures

    def nativeEventFilter(self, event_type, message):
        if self.user32 and self.enabled:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam in self.bindings:
                action = self.bindings[msg.wParam]
                QTimer.singleShot(0, lambda value=action: self.callback(value))
                return True, 0
        return False, 0
