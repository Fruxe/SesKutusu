import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,unittest
from PySide6.QtCore import QEvent,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from hotkeys import HotkeyEdit,parse_hotkey
import test_hotkeys_gui as hotkey_helpers
app=QApplication.instance() or QApplication([])
class NumpadTests(unittest.TestCase):
 def press(self,edit,key,mods,native,text=''):
  event=QKeyEvent(QEvent.Type.KeyPress,key,mods,0,native,0,text)
  QApplication.sendEvent(edit,event)
 def test_numpad_digits_capture_distinct_virtual_keys(self):
  for digit in range(10):
   edit=HotkeyEdit()
   self.press(edit,int(Qt.Key.Key_0)+digit,Qt.KeyboardModifier.KeypadModifier,0x60+digit,str(digit))
   self.assertEqual(edit.text(),'NumPad'+str(digit));self.assertEqual(parse_hotkey(edit.text()),(0x4000,0x60+digit))
   self.assertNotEqual(parse_hotkey('Ctrl+'+edit.text()),parse_hotkey('Ctrl+'+str(digit)))
 def test_keypad_modifier_and_native_fallback_preserved(self):
  edit=HotkeyEdit()
  self.press(edit,Qt.Key.Key_1,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.KeypadModifier,0,'1')
  self.assertEqual(edit.text(),'Ctrl+NumPad1')
  self.press(edit,Qt.Key.Key_1,Qt.KeyboardModifier.ControlModifier,0x61,'1')
  self.assertEqual(edit.text(),'Ctrl+NumPad1')
  self.press(edit,Qt.Key.Key_1,Qt.KeyboardModifier.ControlModifier,0x31,'1')
  self.assertEqual(edit.text(),'Ctrl+1')
 def test_numpad_operators_and_qt_legacy_notation(self):
  for token,vk in [('Add',0x6b),('Subtract',0x6d),('Multiply',0x6a),('Divide',0x6f),('Decimal',0x6e)]:
   self.assertEqual(parse_hotkey('NumPad'+token),(0x4000,vk))
  self.assertEqual(parse_hotkey('Ctrl+Num+1'),parse_hotkey('Ctrl+NumPad1'))
 def test_assign_top_row_and_numpad_separately(self):
  helper=hotkey_helpers.HotkeyGuiTests()
  with tempfile.TemporaryDirectory() as root:
   w=helper.make(root)
   try:
    first,second=w.library.sounds[:2]
    w.assign_hotkey(first,'Ctrl+1');w.assign_hotkey(second,'Ctrl+NumPad1')
    self.assertEqual(first['hotkey'],'Ctrl+1');self.assertEqual(second['hotkey'],'Ctrl+NumPad1')
    self.assertIn((0x4002,0x31),w.hotkeys.user32.calls);self.assertIn((0x4002,0x61),w.hotkeys.user32.calls)
   finally:w.close()
if __name__=='__main__':unittest.main(verbosity=2)

