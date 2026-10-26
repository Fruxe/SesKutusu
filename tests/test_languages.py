import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile,unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from i18n import set_language,tr,LANGUAGES,CATALOG
from app import Window
app=QApplication.instance() or QApplication([])
class LanguageTests(unittest.TestCase):
    def tearDown(self):set_language('en')
    def test_fresh_library_defaults_to_english(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(folder)
            try:
                self.assertEqual(window.language_code,'en')
                self.assertEqual(window.library.data['categories'],['General','Effects','Music'])
                self.assertEqual(window.library.sounds[0]['name'],'Soft notification')
                self.assertEqual(tr('Soundboard'),'Soundboard')
            finally:window.close()
    def test_catalog_has_eight_languages_and_english(self):
        self.assertEqual(len(LANGUAGES),8)
        for row in CATALOG.values():self.assertEqual(set(row),set(LANGUAGES));self.assertTrue(all(row.values()))
        set_language('en');self.assertEqual(tr('Soundboard'),'Soundboard')
    def test_saved_language_rtl_and_user_names(self):
        from library import Library
        for code in ['en','ar']:
            with self.subTest(code=code),tempfile.TemporaryDirectory() as folder:
                library=Library(folder);library.data['settings']['language']=code;library.save();window=Window(folder)
                try:
                    self.assertEqual(window.language_code,code)
                    self.assertEqual(window.layoutDirection(),Qt.LayoutDirection.RightToLeft if code=='ar' else Qt.LayoutDirection.LeftToRight)
                    self.assertEqual(window.mode.currentData(),'preview');self.assertEqual(window.theme_name,'Night')
                    entry=window.library.sounds[0];entry['name']='Soundboard';window.refresh_table()
                    self.assertEqual(window.cards.cards[0].entry['name'],'Soundboard')
                finally:window.close()
