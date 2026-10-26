import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from app import Window
from hotkeys import parse_hotkey
app=QApplication.instance() or QApplication([])
class FakeUser32:
 def __init__(self,fail_key=None):self.fail_key=fail_key;self.calls=[]
 def RegisterHotKey(self,hwnd,ident,mods,key):self.calls.append((mods,key));return key!=self.fail_key
 def UnregisterHotKey(self,*args):return True
class HotkeyGuiTests(unittest.TestCase):
 def make(self,root):
  window=Window(root);window.hotkeys.clear();window.hotkeys.user32=FakeUser32();return window
 def test_function_key_and_semantic_duplicate(self):
  with tempfile.TemporaryDirectory() as root:
   w=self.make(root)
   try:
    first,second=w.library.sounds[:2];w.assign_hotkey(first,'F8');self.assertEqual(first['hotkey'],'F8')
    w.assign_hotkey(first,'Ctrl+Alt+1')
    with self.assertRaisesRegex(ValueError,'already'):w.assign_hotkey(second,'Alt+Ctrl+1')
    self.assertEqual(second['hotkey'],'');self.assertIn((0x4003,49),w.hotkeys.user32.calls)
    w.assign_hotkey(first,'');self.assertEqual(first['hotkey'],'')
   finally:w.close()
 def test_os_conflict_preserves_previous_assignment(self):
  with tempfile.TemporaryDirectory() as root:
   w=self.make(root)
   try:
    entry=w.library.sounds[0];w.assign_hotkey(entry,'Ctrl+Alt+2');w.hotkeys.user32.fail_key=49
    with self.assertRaises(ValueError):w.assign_hotkey(entry,'Ctrl+Alt+1')
    self.assertEqual(entry['hotkey'],'Ctrl+Alt+2');self.assertIn(entry['id'],w.hotkeys.bindings.values())
   finally:w.close()
 def test_game_hotkey_routes_to_microphone_from_preview(self):
  with tempfile.TemporaryDirectory() as root:
   w=self.make(root)
   try:
    w.broadcast_device.clear();w.broadcast_device.addItem('Yok',None);w.broadcast_device.addItem('CABLE Input (test)',123)
    w.mode.setCurrentIndex(w.mode.findData('preview'));entry=w.library.sounds[0]
    with patch.object(w,'play_entry') as play:w.on_hotkey(entry['id']);play.assert_called_once_with(entry,background=True)
    self.assertEqual(w.mode.currentData(),'both');self.assertEqual(w.broadcast_device.currentData(),123)
   finally:w.close()
 def test_missing_cable_does_not_interrupt_game_with_dialog(self):
  with tempfile.TemporaryDirectory() as root:
   w=self.make(root)
   try:
    w.broadcast_device.clear();w.broadcast_device.addItem('Yok',None)
    with patch.object(w,'play_entry') as play,patch.object(w,'error') as dialog:
     w.on_hotkey(w.library.sounds[0]['id']);play.assert_not_called();dialog.assert_not_called()
    self.assertIn('CABLE Input was not found',w.statusBar().currentMessage())
   finally:w.close()
if __name__=='__main__':unittest.main(verbosity=2)
