import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,unittest
from PySide6.QtWidgets import QApplication
from app import Window
app=QApplication.instance() or QApplication([])
class GuiTests(unittest.TestCase):
 def test_settings_survive_restart(self):
  with tempfile.TemporaryDirectory() as root:
   window=Window(root);window.volume.setValue(23);window.broadcast_volume.setValue(41);window.normalize.setChecked(True);window.close();app.processEvents()
   reopened=Window(root)
   self.assertEqual(reopened.volume.value(),23);self.assertEqual(reopened.broadcast_volume.value(),41);self.assertTrue(reopened.normalize.isChecked());reopened.close();app.processEvents()
 def test_filter_clears_hidden_selection_and_stop_cancels_load(self):
  with tempfile.TemporaryDirectory() as root:
   window=Window(root);window.table.selectRow(0);window.selection_changed();self.assertIsNotNone(window.selected());entry=window.selected();window.search.setText('no-such-sound');self.assertIsNone(window.selected())
   window.search.clear();window.play_entry(entry);window.stop();app.processEvents();self.assertIsNone(window.pending);self.assertFalse(window.engine.playing);window.close();app.processEvents()
if __name__=='__main__':unittest.main(verbosity=2)

