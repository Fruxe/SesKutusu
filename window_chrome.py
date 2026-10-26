"""Match the native Windows frame to the app theme, retaining system controls."""
import ctypes
import sys
from ctypes import wintypes
from PySide6.QtCore import QObject,QEvent,QTimer
from PySide6.QtWidgets import QApplication,QWidget
from shiboken6 import isValid

def colorref(hex_color):
    value=hex_color.lstrip('#')
    r,g,b=(int(value[i:i+2],16) for i in (0,2,4))
    return r | g<<8 | b<<16

def apply_frame(hwnd,colors):
    if sys.platform!='win32':return {}
    setter=ctypes.windll.dwmapi.DwmSetWindowAttribute
    setter.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
    setter.restype=ctypes.c_long
    dark=int(sum(int(colors['bg'][i:i+2],16) for i in (1,3,5))<384)
    values={20:dark,33:2,34:colorref(colors['line']),35:colorref(colors['side']),36:colorref(colors['text'])}
    results={}
    for attribute,value in values.items():
        data=wintypes.DWORD(value)
        results[attribute]=setter(hwnd,attribute,ctypes.byref(data),ctypes.sizeof(data))
    return results

class WindowChrome(QObject):
    def __init__(self,app):
        super().__init__(app);self.colors=None;app.installEventFilter(self)
    def apply(self,widget):
        if self.colors and isValid(widget) and widget.isWindow() and QApplication.platformName()=='windows':
            apply_frame(int(widget.winId()),self.colors)
    def update(self,colors):
        self.colors=dict(colors)
        for widget in QApplication.topLevelWidgets():
            if widget.isVisible():self.apply(widget)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Show and isinstance(obj,QWidget) and obj.isWindow():
            QTimer.singleShot(0,lambda widget=obj:self.apply(widget))
        return False

def update_chrome(colors):
    app=QApplication.instance()
    if not hasattr(app,'soundboard_chrome'):app.soundboard_chrome=WindowChrome(app)
    app.soundboard_chrome.update(colors)
