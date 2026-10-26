"""Small, portable UI catalogue; user sound names and device IDs stay unchanged."""
from pathlib import Path
from PySide6.QtCore import Qt, QLocale, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication

LANGUAGES={'tr':'Turkish','en':'English','de':'German','es':'Spanish','fr':'French','pt':'Portuguese','ru':'Russian','ar':'Arabic'}
_language='en'
_translator=None
CATALOG={}
for line in Path(__file__).with_name('translations.tsv').read_text(encoding='utf-8-sig').splitlines():
    cells=line.split('|')
    if len(cells)==9:CATALOG[cells[0].replace('\\n','\n')]=dict(zip(LANGUAGES,[c.replace('\\n','\n') for c in cells[1:]]))

def tr(text):
    text=str(text)
    return CATALOG.get(text,{}).get(_language,text)

def set_language(code):
    global _language,_translator
    _language=code if code in LANGUAGES else 'en'
    app=QApplication.instance()
    QLocale.setDefault(QLocale(_language))
    if app:
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if _language=='ar' else Qt.LayoutDirection.LeftToRight)
        if _translator:app.removeTranslator(_translator)
        _translator=QTranslator(app)
        if _translator.load('qtbase_'+_language,QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):app.installTranslator(_translator)
    return _language
