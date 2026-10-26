import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog,QComboBox,QCheckBox
from app import Window
app=QApplication.instance() or QApplication([])
class AppearanceTests(unittest.TestCase):
 def test_theme_accent_density_view_and_sort_persist(self):
  with tempfile.TemporaryDirectory() as root:
   window=Window(root)
   window.theme_name='AMOLED';window.accent_name='Mint';window.compact=True;window.apply_appearance();window.set_view('list');window.sort_combo.setCurrentIndex(window.sort_combo.findData('name'));window.save_appearance();window.close()
   reopened=Window(root)
   try:
    self.assertEqual((reopened.theme_name,reopened.accent_name,reopened.compact,reopened.view_mode),('AMOLED','Mint',True,'list'))
    self.assertEqual(reopened.sort_combo.currentData(),'name');self.assertIs(reopened.view_stack.currentWidget(),reopened.table)
   finally:reopened.close()
 def test_cards_keep_sound_identity_for_shortcut_and_play(self):
  with tempfile.TemporaryDirectory() as root:
   window=Window(root)
   try:
    window.sort_combo.setCurrentIndex(window.sort_combo.findData('name'))
    card=window.cards.cards[0];ident=card.entry['id']
    with patch.object(window,'play_entry') as play:
     card.play.emit(ident);self.assertEqual(window.selected_id,ident);self.assertEqual(play.call_args.args[0]['id'],ident)
    with patch.object(window,'edit_hotkey') as edit:
     card.hotkey.emit(ident);edit.assert_called_once();self.assertEqual(window.selected_id,ident)
   finally:window.close()
 def test_recent_favorites_and_empty_results(self):
  with tempfile.TemporaryDirectory() as root:
   window=Window(root)
   try:
    entry=window.library.sounds[1];entry.update(plays=3,last_played=123,favorite=True)
    window.current_filter='recent';window.refresh_table();self.assertEqual([card.entry['id'] for card in window.cards.cards],[entry['id']])
    window.current_filter='favorites';window.refresh_table();self.assertEqual(window.table.rowCount(),1)
    window.search.setText('no-match');self.assertEqual(len(window.cards.cards),0);self.assertFalse(window.cards.empty.isHidden())
   finally:window.close()
 def test_cancel_live_theme_preview_restores_preferences(self):
  with tempfile.TemporaryDirectory() as root:
   window=Window(root)
   try:
    original=(window.theme_name,window.accent_name,window.compact)
    def reject(dialog):
     combos=dialog.findChildren(QComboBox);combos[0].setCurrentText('Light');combos[1].setCurrentText('Coral');dialog.findChildren(QCheckBox)[0].setChecked(True)
     return QDialog.DialogCode.Rejected
    with patch.object(QDialog,'exec',reject):window.show_appearance()
    self.assertEqual((window.theme_name,window.accent_name,window.compact),original)
   finally:window.close()
if __name__=='__main__':unittest.main(verbosity=2)
