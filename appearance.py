"""SesKutusu appearance and native sound cards. All drawing is code based."""
from __future__ import annotations
from i18n import tr
from PySide6.QtCore import Qt,Signal,QTimer,QPointF
from PySide6.QtGui import QColor,QPainter,QPainterPath
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,
    QGridLayout,QMenu,QSizePolicy,QApplication)

THEMES={
 'Night':dict(bg='#0c1018',side='#10151f',panel='#151b27',raised='#1c2433',text='#edf1fa',muted='#929eb4',line='#293448',hover='#232f43'),
 'Graphite':dict(bg='#18191d',side='#1e2025',panel='#25272e',raised='#2e313a',text='#f1f1f5',muted='#a0a3b1',line='#3a3e49',hover='#363b47'),
 'AMOLED':dict(bg='#030405',side='#07090c',panel='#0d1117',raised='#151b24',text='#f2f5fa',muted='#8d9aaf',line='#202b3b',hover='#1b2739'),
 'Light':dict(bg='#f0f3f9',side='#ffffff',panel='#ffffff',raised='#e9eef7',text='#1c2940',muted='#66758d',line='#d4ddeb',hover='#e3eaf6')
}
ACCENTS={'Lavender':'#ab9bff','Coral':'#ff8f81','Mint':'#6ed9b4','Blue':'#7cbcff'}

def palette(theme='Night',accent='Lavender'):
 colors=dict(THEMES.get(theme,THEMES['Night']))
 colors['accent']=({'Lavender':'#6954c9','Coral':'#bc4f41','Mint':'#147b5a','Blue':'#2868bf'}.get(accent,'#6954c9') if theme=='Light' else ACCENTS.get(accent,ACCENTS['Lavender']))
 colors['on_accent']='#ffffff' if theme=='Light' else '#111622'
 base=QColor(colors['panel']);tone=QColor(colors['accent'])
 colors['tint']=QColor(round(base.red()*.83+tone.red()*.17),round(base.green()*.83+tone.green()*.17),round(base.blue()*.83+tone.blue()*.17)).name()
 colors['danger']='#b8314a' if theme=='Light' else '#ff96a1'
 return colors

TEMPLATE='''
QWidget { background:@bg; color:@text; font-family:"Segoe UI"; font-size:13px; }
QMainWindow { background:@bg; }
QLabel { background:transparent; border:0; }
QFrame#sidebar { background:@side; border-right:1px solid @line; }
QFrame#panel,QFrame#player { background:@panel; border:1px solid @line; border-radius:15px; }
QFrame#metric { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 @raised,stop:1 @panel); border:1px solid @line; border-radius:12px; }
QFrame#card { background:@panel; border:1px solid @line; border-radius:16px; }
QFrame#card:hover { background:@raised; border-color:@accent; }
QFrame#card[selected="true"] { background:@tint; border:1px solid @accent; }
QFrame#card[playing="true"] { border:2px solid @accent; }
QLabel#brand { color:@text; font-size:22px; font-weight:700; }
QLabel#title { font-size:30px; font-weight:700; }
QLabel#muted,QLabel#eyebrow { color:@muted; }
QLabel#eyebrow { font-size:10px; font-weight:700; letter-spacing:1px; }
QLabel#sectionTitle { font-size:15px; font-weight:600; }
QLabel#metricValue { font-size:25px; font-weight:700; }
QLabel#badge { background:@tint; color:@accent; border:1px solid @line; border-radius:10px; padding:5px 10px; font-size:11px; }
QLabel#chip { background:@raised; color:@muted; border-radius:7px; padding:4px 8px; font-size:11px; }
QLabel#cardTitle { font-size:14px; font-weight:600; }
QLabel#cardGlyph { background:@tint; color:@accent; border-radius:10px; font-size:23px; }
QPushButton { background:@raised; color:@text; border:1px solid @line; border-radius:8px; padding:8px 12px; min-height:18px; }
QPushButton:hover { background:@hover; border-color:@muted; }
QPushButton:pressed { background:@tint; }
QPushButton:disabled { color:@muted; background:@panel; }
QPushButton#accent { background:@accent; color:@on_accent; border:0; font-weight:700; padding:10px 16px; }
QPushButton#accent:hover { background:@text; color:@bg; }
QPushButton#iconAction { background:transparent; border:0; padding:0; min-height:0; min-width:0; border-radius:8px; color:@muted; }
QPushButton#iconAction:hover { background:@tint; color:@accent; }
QPushButton#ghost { background:transparent; border:1px solid transparent; color:@muted; padding:4px 8px; }
QPushButton#ghost:hover { color:@text; background:@raised; }
QPushButton#stop { color:@danger; border:1px solid @line; }
QPushButton#keyBadge { background:@tint; color:@accent; padding:4px 9px; font-size:11px; border-color:@line; }
QPushButton#segment { padding:7px 12px; border-radius:7px; background:transparent; color:@muted; }
QPushButton#segment:checked { background:@tint; color:@accent; border-color:@accent; }
QPushButton#cardPlay { background:@accent; color:@on_accent; border:0; border-radius:17px; padding:0; font-size:15px; }
QLineEdit,QComboBox,QDoubleSpinBox,QKeySequenceEdit { background:@raised; color:@text; border:1px solid @line; border-radius:8px; padding:9px 10px; selection-background-color:@tint; }
QLineEdit:focus,QComboBox:focus { border-color:@accent; }
QComboBox::drop-down { border:0; width:23px; }
QComboBox QAbstractItemView { background:@raised; color:@text; border:1px solid @line; selection-background-color:@tint; selection-color:@text; padding:4px; }
QListWidget { background:transparent; border:0; outline:0; }
QListWidget::item { padding:11px 10px; border-radius:8px; margin:3px 0; color:@muted; }
QListWidget::item:hover { background:@raised; color:@text; }
QListWidget::item:selected { background:@tint; color:@accent; }
QTableWidget { background:@panel; alternate-background-color:@raised; gridline-color:@line; border:1px solid @line; border-radius:10px; outline:0; }
QTableWidget::item { padding:10px; border-bottom:1px solid @line; }
QTableWidget::item:selected { background:@tint; color:@text; }
QHeaderView::section { background:@panel; color:@muted; border:0; padding:12px 8px; font-size:11px; font-weight:600; }
QSlider::groove:horizontal { background:@line; height:5px; border-radius:2px; }
QSlider::sub-page:horizontal { background:@accent; border-radius:2px; }
QSlider::handle:horizontal { background:@accent; width:13px; margin:-4px 0; border-radius:6px; }
QProgressBar { border:0; background:@line; border-radius:3px; }
QProgressBar::chunk { background:@accent; border-radius:3px; }
QCheckBox { background:transparent; spacing:8px; color:@text; font-size:12px; }
QCheckBox::indicator { width:17px; height:17px; border:1px solid @muted; border-radius:5px; background:@raised; }
QCheckBox::indicator:checked { background:@accent; border:1px solid @accent; }
QCheckBox::indicator:unchecked:hover { border-color:@accent; }
QScrollArea { border:0; background:transparent; }
QScrollArea>QWidget>QWidget { background:transparent; }
QScrollBar:vertical { background:transparent; width:7px; margin:1px; }
QScrollBar::handle:vertical { background:@line; min-height:28px; border-radius:3px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QStatusBar { color:@muted; border-top:1px solid @line; background:@bg; font-size:11px; }
QMenu { background:@panel; border:1px solid @line; padding:5px; }
QMenu::item { padding:8px 22px; }
QMenu::item:selected { background:@tint; }
QToolTip { background:@raised; color:@text; border:1px solid @line; padding:5px; }
'''

def stylesheet(theme,accent):
 result=TEMPLATE
 for name,color in palette(theme,accent).items():result=result.replace('@'+name,color)
 return result

class PlayButton(QPushButton):
 def __init__(self,parent=None):
  super().__init__(parent);self.setAccessibleName(tr('Play sound'));self.setCursor(Qt.CursorShape.PointingHandCursor)
 def paintEvent(self,event):
  app=QApplication.instance();color=QColor(app.property('soundboardAccent') or '#ab9bff')
  if self.underMouse():color=color.lighter(112)
  if self.isDown():color=color.darker(112)
  p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(Qt.PenStyle.NoPen);p.setBrush(color);p.drawEllipse(self.rect().adjusted(1,1,-1,-1))
  w,h=self.width(),self.height();path=QPainterPath();path.moveTo(w*.42,h*.33);path.lineTo(w*.69,h*.5);path.lineTo(w*.42,h*.67);path.closeSubpath()
  p.setBrush(QColor(app.property('soundboardAccentText') or '#111622'));p.drawPath(path)
  if self.hasFocus():
   from PySide6.QtGui import QPen
   p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(color.lighter(145),1));p.drawEllipse(self.rect().adjusted(0,0,-1,-1))

class SoundCard(QFrame):
 selected=Signal(str);play=Signal(str);favorite=Signal(str);hotkey=Signal(str);edit=Signal(str);remove=Signal(str)
 def __init__(self,entry,compact=False,parent=None):
  super().__init__(parent);self.entry=entry;self.setObjectName('card');self.setFixedHeight(150 if compact else 174)
  self.setCursor(Qt.CursorShape.PointingHandCursor)
  layout=QVBoxLayout(self);layout.setContentsMargins(16,12 if compact else 14,16,12 if compact else 14);layout.setSpacing(6 if compact else 8)
  top=QHBoxLayout();glyph=QLabel('♪');glyph.setObjectName('cardGlyph');glyph.setAlignment(Qt.AlignmentFlag.AlignCenter);glyph.setFixedSize(30 if compact else 36,30 if compact else 36);top.addWidget(glyph)
  top.addStretch();fav=QPushButton('★' if entry.get('favorite') else '☆');fav.setObjectName('iconAction');fav.setToolTip(tr('Favorite'));fav.setFixedSize(30,30);fav.clicked.connect(lambda:self.favorite.emit(entry['id']));top.addWidget(fav)
  menu=QPushButton('⋯');menu.setObjectName('iconAction');menu.setFixedSize(27,30);menu.clicked.connect(self.menu);top.addWidget(menu);layout.addLayout(top)
  title=QLabel(entry['name']);title.setObjectName('cardTitle');title.setWordWrap(False);title.setMaximumHeight(20);title.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);title.setToolTip(entry['name']+'\n'+entry['path']);layout.addWidget(title)
  meta=QHBoxLayout();category=QLabel(entry['category']);category.setObjectName('muted');meta.addWidget(category,1)
  duration=entry.get('duration');duration_text='—' if duration is None else (f'{duration:.1f} '+tr('s') if duration<1 else f'{int(duration)//60}:{int(duration)%60:02}')
  time=QLabel(duration_text);time.setObjectName('muted');meta.addWidget(time);layout.addLayout(meta)
  footer=QHBoxLayout();key=QPushButton(entry.get('hotkey') or tr('+ Hotkey'));key.setObjectName('keyBadge');key.setToolTip(tr('Assign or change hotkey'));key.clicked.connect(lambda:self.hotkey.emit(entry['id']));footer.addWidget(key)
  footer.addStretch();play=PlayButton();play.setFixedSize(32 if compact else 36,32 if compact else 36);play.setToolTip(tr('Play sound'));play.clicked.connect(lambda:self.play.emit(entry['id']));footer.addWidget(play);layout.addLayout(footer)
 def set_state(self,selected,playing):
  if bool(self.property('selected'))==selected and bool(self.property('playing'))==playing:return
  self.setProperty('selected',selected);self.setProperty('playing',playing);self.style().unpolish(self);self.style().polish(self);self.update()
 def mousePressEvent(self,event):
  if event.button()==Qt.MouseButton.LeftButton:self.selected.emit(self.entry['id'])
  super().mousePressEvent(event)
 def mouseDoubleClickEvent(self,event):
  if event.button()==Qt.MouseButton.LeftButton:self.play.emit(self.entry['id'])
  super().mouseDoubleClickEvent(event)
 def menu(self):
  popup=QMenu(self)
  for text,signal in [(tr('Assign hotkey'),self.hotkey),(tr('Edit details'),self.edit),(tr('Remove from library'),self.remove)]:
   action=popup.addAction(text);action.triggered.connect(lambda checked=False,s=signal:s.emit(self.entry['id']))
  popup.exec(self.mapToGlobal(self.rect().topRight()))

class CardBoard(QWidget):
 selected=Signal(str);play=Signal(str);favorite=Signal(str);hotkey=Signal(str);edit=Signal(str);remove=Signal(str)
 def __init__(self,parent=None):
  super().__init__(parent);self.layout_grid=QGridLayout(self);self.layout_grid.setContentsMargins(0,0,8,0);self.layout_grid.setSpacing(12);self.cards=[];self.columns=0;self.compact=False
  self.empty=QLabel(tr('No sounds yet.\nAdd sounds or drop files here.'));self.empty.setObjectName('muted');self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter);self.empty.setWordWrap(True)
 def render(self,entries,selected=None,playing=None,compact=False):
  while self.layout_grid.count():self.layout_grid.takeAt(0)
  for card in self.cards:card.hide();card.deleteLater()
  self.cards=[];self.empty.hide();self.compact=compact
  if not entries:
   self.layout_grid.addWidget(self.empty,0,0);self.empty.show();self.layout_grid.setRowStretch(1,1);return
  for entry in entries:
   card=SoundCard(entry,compact,self)
   for name in ['selected','play','favorite','hotkey','edit','remove']:getattr(card,name).connect(getattr(self,name).emit)
   card.set_state(entry['id']==selected,entry['id']==playing);self.cards.append(card)
  self.columns=0;self.reflow()
 def reflow(self):
  columns=3 if self.width()>=735 else (2 if self.width()>=455 else 1)
  if columns==self.columns:return
  self.columns=columns
  while self.layout_grid.count():self.layout_grid.takeAt(0)
  for row in range(self.layout_grid.rowCount()):self.layout_grid.setRowStretch(row,0)
  for i,card in enumerate(self.cards):self.layout_grid.addWidget(card,i//columns,i%columns)
  self.layout_grid.setRowStretch((len(self.cards)+columns-1)//columns,1)
  for col in range(4):self.layout_grid.setColumnStretch(col,1 if col<columns else 0)
 def resizeEvent(self,event):
  super().resizeEvent(event)
  if self.cards:self.reflow()
 def set_states(self,selected=None,playing=None):
  for card in self.cards:card.set_state(card.entry['id']==selected,card.entry['id']==playing)
