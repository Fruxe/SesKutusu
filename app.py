from __future__ import annotations
import argparse
import concurrent.futures
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
import soundfile as sf
from PySide6.QtCore import Qt, QTimer, QSize, QLockFile
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QKeySequence, QIcon, QFontDatabase
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox, QComboBox, QSlider, QCheckBox,
    QFrame, QDialog, QFormLayout, QDialogButtonBox, QKeySequenceEdit, QInputDialog,
    QDoubleSpinBox, QProgressBar, QStackedWidget, QScrollArea)
from i18n import tr, set_language, LANGUAGES
from audio_engine import AudioEngine, load_clip, output_devices
from broadcast import input_devices
from library import Library
from window_chrome import update_chrome
from appearance import THEMES, ACCENTS, palette, stylesheet, CardBoard
from hotkeys import HotkeyFilter, HotkeyEdit, parse_hotkey, STOP_HOTKEY

VERSION = '0.6.0'
SUPPORTED = {'.wav', '.mp3', '.flac', '.ogg', '.aiff', '.aif', '.opus'}
STYLE = stylesheet('Night','Lavender')


def fmt_time(seconds):
    if seconds is None: return '—'
    if 0<seconds<1:return f'{seconds:.1f} '+tr('s')
    return f'{int(seconds)//60}:{int(seconds)%60:02}'


def label(text, obj=None):
    w = QLabel(text)
    if obj: w.setObjectName(obj)
    return w


def button(text, callback, obj=None):
    w = QPushButton(text)
    if obj: w.setObjectName(obj)
    w.clicked.connect(callback)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    return w


class WaveView(QWidget):
    def __init__(self):
        super().__init__()
        self.values = None
        self.progress = 0
        self.setMinimumHeight(40)
        self.active_color='#ab9bff';self.inactive_color='#344056';self.text_color='#929eb4'
    def set_audio(self, samples):
        mono = np.max(np.abs(samples), axis=1)
        self.values = np.array([np.max(part) if len(part) else 0 for part in np.array_split(mono, 320)])
        self.update()
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        middle = self.height()/2
        if self.values is None:
            p.setPen(QColor(self.text_color))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr('Select a sound and press Play to see its waveform.'))
            return
        width = self.width()/len(self.values)
        for i, value in enumerate(self.values):
            p.setPen(QPen(QColor(self.active_color if i/len(self.values) <= self.progress else self.inactive_color), max(1, width*.58)))
            x = (i+.5)*width
            height = max(1.2, float(value)*(middle-7))
            p.drawLine(int(x), int(middle-height), int(x), int(middle+height))


class Window(QMainWindow):
    def __init__(self, root):
        super().__init__()
        self.setWindowTitle(f'SesKutusu • {VERSION}')
        icon_path=Path(__file__).resolve().parent/'app-icon.ico'
        if icon_path.exists():self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1360, 900)
        self.setMinimumSize(1100, 800)
        self.library = Library(root)
        preferences=self.library.data['settings']
        self.language_code=set_language(preferences.get('language','en'))
        self.theme_name=preferences.get('theme','Night') if preferences.get('theme','Night') in THEMES else 'Night'
        self.accent_name=preferences.get('accent','Lavender') if preferences.get('accent','Lavender') in ACCENTS else 'Lavender'
        self.compact=bool(preferences.get('compact',False));self.always_on_top=bool(preferences.get('always_on_top',False))
        self.view_mode=preferences.get('view_mode','cards')
        self.engine = AudioEngine()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.pending_background = False
        self.generation = 0
        self.selected_id = None
        self.loaded_id = None
        self.loaded_clip = None
        self.drag_seek = False
        self.current_filter = 'all'
        self.devices = []
        self.closing = False
        self.initializing = True
        self.setAcceptDrops(True)
        self.hotkeys = HotkeyFilter(self.on_hotkey)
        QApplication.instance().installNativeEventFilter(self.hotkeys)
        self.build()
        self.seed_examples()
        self.refresh_categories()
        self.refresh_devices()
        self.restore_settings()
        self.apply_appearance()
        self.initializing = False
        self.refresh_table()
        self.bind_hotkeys()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(70)
        if self.library.warning: QTimer.singleShot(300, lambda: self.notice(self.library.warning))

    def build(self):
        host=QWidget();outer=QHBoxLayout(host);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0);self.setCentralWidget(host)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(208)
        sl=QVBoxLayout(side);sl.setContentsMargins(20,26,20,20);sl.setSpacing(11)
        sl.addWidget(label('◉  SesKutusu','brand'));sl.addWidget(label(tr('YOUR SOUND STAGE'),'eyebrow'));sl.addSpacing(26)
        sl.addWidget(label(tr('LIBRARY'),'eyebrow'))
        self.categories=QListWidget();self.categories.currentItemChanged.connect(self.filter_changed);sl.addWidget(self.categories,1)
        sl.addWidget(button(tr('+  New category'),self.add_category,'ghost'));sl.addSpacing(12)
        self.count_label=label('0 sounds','muted');sl.addWidget(self.count_label)
        sl.addSpacing(8);sl.addWidget(label(tr('GAME HOTKEYS'),'eyebrow'))
        self.hotkey_enabled=QCheckBox(tr('Global hotkeys'));self.hotkey_enabled.setChecked(True);self.hotkey_enabled.toggled.connect(self.toggle_hotkeys);sl.addWidget(self.hotkey_enabled)
        self.game_hotkeys=QCheckBox(tr('Send audio to game'));self.game_hotkeys.setChecked(True);self.game_hotkeys.setToolTip(tr('Send global hotkeys through CABLE Input to the game microphone.'));self.game_hotkeys.toggled.connect(self.settings_changed);sl.addWidget(self.game_hotkeys)
        sl.addWidget(button(tr('Language'),self.show_language));sl.addWidget(button(tr('Appearance and theme'),self.show_appearance));sl.addWidget(button(tr('Routing guide'),self.show_routing,'ghost'))
        sl.addSpacing(10);sl.addWidget(label(tr('STOP ALL'),'eyebrow'));sl.addWidget(label('Ctrl + Alt + F10','badge'));sl.addWidget(label('v'+VERSION,'muted'));outer.addWidget(side)
        workspace=QVBoxLayout();workspace.setContentsMargins(24,22,24,14);workspace.setSpacing(18);outer.addLayout(workspace,1)
        head=QHBoxLayout();titles=QVBoxLayout();titles.setSpacing(5);titles.addWidget(label(tr('Soundboard'),'title'));titles.addWidget(label(tr('Pick a sound. Press a hotkey. Send it to your game.'),'muted'));head.addLayout(titles,1)
        self.connection_badge=label('○ Checking audio routing','badge');self.connection_badge.setFixedHeight(32);head.addWidget(self.connection_badge);workspace.addLayout(head)
        body=QHBoxLayout();body.setSpacing(20);workspace.addLayout(body,1)
        center=QVBoxLayout();center.setSpacing(14);body.addLayout(center,1)
        metrics=QHBoxLayout();metrics.setSpacing(10)
        self.metric_labels={}
        for key,title in [('sounds',tr('TOTAL SOUNDS')),('hotkeys',tr('HOTKEY')),('favorites',tr('FAVORITES'))]:
            frame=QFrame();frame.setObjectName('metric');box=QVBoxLayout(frame);box.setContentsMargins(14,10,14,10);box.setSpacing(3)
            box.addWidget(label(title,'eyebrow'));value=label('0','metricValue');self.metric_labels[key]=value;box.addWidget(value);metrics.addWidget(frame,1)
        center.addLayout(metrics)
        searchrow=QHBoxLayout();searchrow.setSpacing(10)
        self.search=QLineEdit();self.search.setPlaceholderText(tr('Search sounds or categories…'));self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self.refresh_table);searchrow.addWidget(self.search,1)
        self.add_button=button(tr('+  Add sounds'),self.add_files,'accent');searchrow.addWidget(self.add_button);center.addLayout(searchrow)
        toolbar=QHBoxLayout();toolbar.setSpacing(6)
        self.cards_button=button(tr('▦  Cards'),lambda:self.set_view('cards'),'segment');self.cards_button.setCheckable(True)
        self.list_button=button(tr('☷  List'),lambda:self.set_view('list'),'segment');self.list_button.setCheckable(True)
        toolbar.addWidget(self.cards_button);toolbar.addWidget(self.list_button);toolbar.addStretch()
        self.sort_combo=QComboBox()
        for title,key in [(tr('Date added'),'added'),(tr('Name'),'name'),(tr('Most played'),'plays'),(tr('Hotkey'),'hotkey')]:self.sort_combo.addItem(title,key)
        self.sort_combo.setToolTip(tr('Sort sounds'));self.sort_combo.currentIndexChanged.connect(self.sort_changed);toolbar.addWidget(self.sort_combo);center.addLayout(toolbar)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['★',tr('SOUND NAME'),tr('CATEGORY'),tr('DURATION'),tr('HOTKEY')])
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0,40);self.table.setColumnWidth(3,64);self.table.setColumnWidth(4,144)
        self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.selection_changed);self.table.cellDoubleClicked.connect(self.table_double_clicked);self.table.cellClicked.connect(self.cell_clicked)
        self.cards=CardBoard();self.cards.selected.connect(self.select_sound);self.cards.play.connect(self.play_card);self.cards.favorite.connect(self.favorite_card)
        self.cards.hotkey.connect(lambda ident:self.card_action(ident,self.edit_hotkey));self.cards.edit.connect(lambda ident:self.card_action(ident,self.edit_selected));self.cards.remove.connect(lambda ident:self.card_action(ident,self.remove_selected))
        self.cards_scroll=QScrollArea();self.cards_scroll.setWidgetResizable(True);self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.cards_scroll.setWidget(self.cards)
        self.view_stack=QStackedWidget();self.view_stack.addWidget(self.cards_scroll);self.view_stack.addWidget(self.table);self.view_stack.setMinimumHeight(180);center.addWidget(self.view_stack,1)
        actions=QHBoxLayout();self.visible_count=label('0 sounds shown','muted');actions.addWidget(self.visible_count,1)
        actions.addWidget(button(tr('Assign hotkey'),self.edit_hotkey,'ghost'));actions.addWidget(button(tr('Edit'),self.edit_selected,'ghost'));actions.addWidget(button(tr('Remove'),self.remove_selected,'ghost'));center.addLayout(actions)
        route=QFrame();route.setObjectName('panel');route.setFixedWidth(300);rl=QVBoxLayout(route);rl.setContentsMargins(18,18,18,18);rl.setSpacing(7)
        rl.addWidget(label(tr('BROADCAST DESK'),'eyebrow'));rl.addWidget(label(tr('Audio routing'),'sectionTitle'))
        self.mode=QComboBox();self.mode.addItem(tr('Headphones + microphone'),'both');self.mode.addItem(tr('Microphone only'),'broadcast');self.mode.addItem(tr('Headphones only'),'preview');self.mode.setFixedHeight(36);rl.addWidget(self.mode)
        rl.addSpacing(4);rl.addWidget(label(tr('MONITOR DEVICE'),'eyebrow'));self.preview_device=QComboBox();self.preview_device.setMinimumWidth(0);self.preview_device.setFixedHeight(36);self.preview_device.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.preview_device.setMinimumContentsLength(10);rl.addWidget(self.preview_device)
        vrow=QHBoxLayout();vrow.addWidget(label(tr('Monitor level'),'muted'));vrow.addStretch();self.preview_level=label('%65','chip');vrow.addWidget(self.preview_level);rl.addLayout(vrow)
        self.volume=QSlider(Qt.Orientation.Horizontal);self.volume.setRange(0,100);self.volume.setValue(65);self.volume.valueChanged.connect(self.volumes_changed);rl.addWidget(self.volume)
        rl.addSpacing(8);rl.addWidget(label(tr('VIRTUAL MICROPHONE OUTPUT'),'eyebrow'));self.broadcast_device=QComboBox();self.broadcast_device.setMinimumWidth(0);self.broadcast_device.setFixedHeight(36);self.broadcast_device.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.broadcast_device.setMinimumContentsLength(10);rl.addWidget(self.broadcast_device)
        brow=QHBoxLayout();brow.addWidget(label(tr('Broadcast level'),'muted'));brow.addStretch();self.broadcast_level=label('%65','chip');brow.addWidget(self.broadcast_level);rl.addLayout(brow)
        self.broadcast_volume=QSlider(Qt.Orientation.Horizontal);self.broadcast_volume.setRange(0,100);self.broadcast_volume.setValue(65);self.broadcast_volume.valueChanged.connect(self.volumes_changed);rl.addWidget(self.broadcast_volume)
        self.route_hint=label('Game input device:\nCABLE Output','muted');self.route_hint.setWordWrap(True);self.route_hint.setMinimumHeight(42);rl.addWidget(self.route_hint)
        self.route_button=button(tr('Mix microphone…'),self.show_broadcast_dialog);rl.addWidget(self.route_button)
        self.broadcast_status=label(tr('Live microphone off'),'muted');self.broadcast_status.setWordWrap(True);self.broadcast_status.setMinimumHeight(32);rl.addWidget(self.broadcast_status)
        rl.addStretch();rl.addWidget(button(tr('Refresh devices'),self.refresh_devices,'ghost'));body.addWidget(route)
        player=QFrame();player.setObjectName('player');pl=QVBoxLayout(player);pl.setContentsMargins(18,12,18,12);pl.setSpacing(7)
        top=QHBoxLayout();self.player_state=label(tr('PLAYER'),'eyebrow');top.addWidget(self.player_state);self.now=label(tr('No sound selected'));self.now.setStyleSheet('font-size:14px;font-weight:600;');top.addWidget(self.now,1)
        self.clock=label('0:00 / 0:00','muted');self.clock.setMinimumWidth(125);self.clock.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter);top.addWidget(self.clock);pl.addLayout(top)
        self.wave=WaveView();self.wave.setMinimumHeight(40);self.wave.setMaximumHeight(48);pl.addWidget(self.wave)
        self.seek=QSlider(Qt.Orientation.Horizontal);self.seek.setRange(0,1000);self.seek.sliderPressed.connect(lambda:setattr(self,'drag_seek',True));self.seek.sliderReleased.connect(self.seek_released);pl.addWidget(self.seek)
        controls=QHBoxLayout();self.play_button=button(tr('▶  Play'),self.play_selected,'accent');controls.addWidget(self.play_button);self.pause_button=button(tr('Pause'),self.pause);controls.addWidget(self.pause_button);controls.addWidget(button(tr('■  Stop'),self.stop,'stop'))
        self.loop=QCheckBox(tr('Loop'));self.loop.toggled.connect(lambda value:setattr(self.engine,'loop',value));controls.addWidget(self.loop)
        self.normalize=QCheckBox(tr('Peak normalize'));self.normalize.setToolTip(tr('Peak normalization; does not normalize LUFS/EBU loudness.'));self.normalize.toggled.connect(self.settings_changed);controls.addWidget(self.normalize)
        controls.addStretch();controls.addWidget(label(tr('OUTPUT'),'eyebrow'));self.meter=QProgressBar();self.meter.setRange(0,100);self.meter.setValue(0);self.meter.setTextVisible(False);self.meter.setFixedSize(94,6);controls.addWidget(self.meter);pl.addLayout(controls);workspace.addWidget(player)
        for widget in [self.preview_device,self.broadcast_device,self.mode]:widget.currentIndexChanged.connect(self.settings_changed)
        self.set_view(self.view_mode,persist=False)
        self.statusBar().showMessage(tr('Ready • Drop audio files here or double-click a card.'))


    def set_view(self,mode,persist=True):
        self.view_mode=mode if mode in ('cards','list') else 'cards'
        self.view_stack.setCurrentWidget(self.cards_scroll if self.view_mode=='cards' else self.table)
        self.cards_button.setChecked(self.view_mode=='cards');self.list_button.setChecked(self.view_mode=='list')
        if persist and not self.initializing:self.save_appearance()

    def sort_changed(self,*args):
        self.refresh_table()
        if not self.initializing:self.save_appearance()

    def save_appearance(self):
        self.library.data['settings'].update(theme=self.theme_name,accent=self.accent_name,view_mode=self.view_mode,compact=self.compact,always_on_top=self.always_on_top,sort_order=self.sort_combo.currentData())
        self.save()

    def apply_appearance(self,apply_window_flags=True):
        desired=stylesheet(self.theme_name,self.accent_name)
        if QApplication.instance().styleSheet()!=desired:QApplication.instance().setStyleSheet(desired)
        colors=palette(self.theme_name,self.accent_name)
        QApplication.instance().setProperty('soundboardAccent',colors['accent']);QApplication.instance().setProperty('soundboardAccentText',colors['on_accent'])
        update_chrome(colors)
        self.wave.active_color=colors['accent'];self.wave.inactive_color=colors['line'];self.wave.text_color=colors['muted'];self.wave.update()
        self.table.verticalHeader().setDefaultSectionSize(42 if self.compact else 52)
        flag=Qt.WindowType.WindowStaysOnTopHint
        if apply_window_flags and bool(self.windowFlags() & flag)!=self.always_on_top:
            visible=self.isVisible();self.setWindowFlag(flag,self.always_on_top)
            if visible:self.show()
        update_chrome(colors)
        if hasattr(self,'cards'):self.refresh_table()

    def show_appearance(self):
        original=(self.theme_name,self.accent_name,self.compact,self.always_on_top)
        dialog=QDialog(self);dialog.setWindowTitle(tr('Appearance and theme'));dialog.setMinimumWidth(450);form=QFormLayout(dialog)
        form.addRow(label(tr('Make SesKutusu your own'),'sectionTitle'))
        theme=QComboBox();[theme.addItem(tr(key),key) for key in THEMES];theme.setCurrentIndex(theme.findData(self.theme_name))
        accent=QComboBox();[accent.addItem(tr(key),key) for key in ACCENTS];accent.setCurrentIndex(accent.findData(self.accent_name))
        compact=QCheckBox(tr('Compact cards and list rows'));compact.setChecked(self.compact)
        pinned=QCheckBox(tr('Always on top'));pinned.setChecked(self.always_on_top)
        form.addRow(tr('Theme'),theme);form.addRow(tr('Accent color'),accent);form.addRow(compact);form.addRow(pinned)
        hint=label(tr('Preview themes and colors live.\nWindow behavior applies when you save.'),'muted');hint.setWordWrap(True);form.addRow(hint)
        def preview(*args):
            self.theme_name=theme.currentData();self.accent_name=accent.currentData();self.compact=compact.isChecked();self.always_on_top=pinned.isChecked();self.apply_appearance(apply_window_flags=False)
        theme.currentTextChanged.connect(preview);accent.currentTextChanged.connect(preview);compact.toggled.connect(preview);pinned.toggled.connect(preview)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.apply_appearance();self.save_appearance()
        else:
            self.theme_name,self.accent_name,self.compact,self.always_on_top=original;self.apply_appearance()


    def show_language(self):
        dialog=QDialog(self);dialog.setWindowTitle(tr('Language'));form=QFormLayout(dialog)
        combo=QComboBox()
        for code,name in LANGUAGES.items():combo.addItem(name,code)
        combo.setCurrentIndex(combo.findData(self.library.data['settings'].get('language',self.language_code)))
        form.addRow(tr('Interface language'),combo)
        hint=QLabel(tr('Reopen SesKutusu to apply the language.'));hint.setWordWrap(True);form.addRow(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.library.data['settings']['language']=combo.currentData();self.save();self.notice(tr('Language preference saved.')+'\n'+tr('Reopen SesKutusu to apply the language.'))

    def select_sound(self,ident):
        self.selected_id=ident;self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item=self.table.item(row,0)
            if item and item.data(Qt.ItemDataRole.UserRole)==ident:self.table.selectRow(row);break
        self.table.blockSignals(False);self.cards.set_states(self.selected_id,self.loaded_id if self.engine.playing else None)

    def play_card(self,ident):
        self.select_sound(ident);entry=self.selected()
        if entry:self.play_entry(entry)

    def favorite_card(self,ident):
        self.select_sound(ident);entry=self.selected()
        if entry:entry['favorite']=not entry.get('favorite');self.save();self.refresh_table()

    def card_action(self,ident,action):
        self.select_sound(ident);action()

    def sync_dashboard(self):
        sounds=self.library.sounds
        for key,value in [('sounds',len(sounds)),('hotkeys',sum(bool(s.get('hotkey')) for s in sounds)),('favorites',sum(bool(s.get('favorite')) for s in sounds))]:self.metric_labels[key].setText(str(value))
        cable=self.broadcast_device.currentData() is not None and 'CABLE' in self.broadcast_device.currentText().upper()
        if cable and self.mode.currentData()!='preview':self.connection_badge.setText(tr('●  Game microphone ready'))
        elif self.mode.currentData()=='preview':self.connection_badge.setText(tr('○  Headphones only'))
        else:self.connection_badge.setText(tr('○  Select virtual microphone'))
        if self.engine.bus.active:
            self.broadcast_status.setText(tr('● Live microphone + file') if self.engine.bus.input_device is not None else tr('● File broadcast on'))
        else:self.broadcast_status.setText(tr('Live microphone off • file broadcast ready') if cable else tr('No virtual microphone selected'))
        self.preview_level.setText('%'+str(self.volume.value()));self.broadcast_level.setText('%'+str(self.broadcast_volume.value()))
        self.cards.set_states(self.selected_id,self.loaded_id if self.engine.playing else None)
        self.player_state.setText(tr('PAUSED') if self.engine.playing and self.engine.paused else (tr('NOW PLAYING') if self.engine.playing else tr('PLAYER')))

    def seed_examples(self):
        if self.library.sounds or (self.library.root/'initialized').exists():return
        folder=self.library.root/'sounds';folder.mkdir(exist_ok=True)
        rate=48000
        for title,notes in [('Soft notification',[523.25,659.25,783.99]),('Short transition',[220,440]),('Startup melody',[392,523.25,659.25,783.99])]:
            chunks=[]
            for freq in notes:
                t=np.arange(int(rate*.20))/rate
                envelope=np.sin(np.linspace(0,np.pi,len(t)))**2
                chunks.append((.18*np.sin(2*np.pi*freq*t)*envelope).astype(np.float32))
            data=np.concatenate(chunks);path=folder/(title+'.wav');sf.write(str(path),data,rate)
            entry=self.library.add(path,'Effects')
            if entry:entry['duration']=len(data)/rate;self.library.save()
        (self.library.root/'initialized').write_text(VERSION)

    def notice(self,text):QMessageBox.information(self,'SesKutusu',tr(str(text)))
    def error(self,text):QMessageBox.warning(self,tr('Action failed'),tr(str(text)))
    def save(self):
        try:self.library.save()
        except OSError as e:self.error(f'Could not save library: {e}')

    def refresh_categories(self):
        current=self.current_filter
        self.categories.blockSignals(True);self.categories.clear()
        for title,key in [(tr('▦  All sounds'),'all'),(tr('★  Favorites'),'favorites'),(tr('◷  Recently played'),'recent')]+[(c,'cat:'+c) for c in self.library.data['categories']]:
            item=QListWidgetItem(title);item.setData(Qt.ItemDataRole.UserRole,key);self.categories.addItem(item)
            if key==current:self.categories.setCurrentItem(item)
        self.categories.blockSignals(False)
        if self.categories.currentRow()<0:self.categories.setCurrentRow(0)

    def filter_changed(self,item,previous):
        if item:self.current_filter=item.data(Qt.ItemDataRole.UserRole);self.refresh_table()

    def refresh_table(self,*args):
        selected=self.selected_id
        query=self.search.text().casefold()
        rows=[s for s in self.library.sounds if (not query or query in (s['name']+' '+s['category']).casefold())
              and (self.current_filter=='all' or self.current_filter=='favorites' and s.get('favorite')
                   or self.current_filter=='recent' and s.get('plays',0)>0 or self.current_filter=='cat:'+s['category'])]
        order=self.sort_combo.currentData()
        if self.current_filter=='recent':rows.sort(key=lambda item:(item.get('last_played',0),item.get('plays',0)),reverse=True)
        elif order=='name':rows.sort(key=lambda item:item['name'].casefold())
        elif order=='plays':rows.sort(key=lambda item:item.get('plays',0),reverse=True)
        elif order=='hotkey':rows.sort(key=lambda item:(not bool(item.get('hotkey')),item.get('hotkey',''),item['name'].casefold()))
        self.table.blockSignals(True);self.table.setRowCount(len(rows))
        selected_row=-1
        for row,s in enumerate(rows):
            values=['★' if s.get('favorite') else '☆',s['name'],s['category'],fmt_time(s.get('duration')),s.get('hotkey') or tr('Double-click → assign')]
            for col,value in enumerate(values):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,s['id'])
                if col==0:item.setForeground(QColor('#ffb77b'))
                if col in (0,3):item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(s['path'] if col==1 else (tr('Double-click to assign or change a hotkey.') if col==4 else value))
                self.table.setItem(row,col,item)
            if s['id']==selected:selected_row=row
        if selected_row>=0:self.table.selectRow(selected_row)
        else:self.selected_id=None
        self.table.blockSignals(False)
        self.count_label.setText(tr('{count} sounds in library').format(count=len(self.library.sounds)))
        self.visible_count.setText(tr('{count} sounds shown').format(count=len(rows)))
        self.cards.render(rows,self.selected_id,self.loaded_id if self.engine.playing else None,self.compact)
        self.sync_dashboard()

    def selected(self):return next((s for s in self.library.sounds if s['id']==self.selected_id),None)
    def selection_changed(self):
        row=self.table.currentRow()
        if row>=0 and self.table.item(row,0):
            self.selected_id=self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
            self.cards.set_states(self.selected_id,self.loaded_id if self.engine.playing else None)
    def cell_clicked(self,row,col):
        if col==0:
            self.selection_changed();entry=self.selected()
            if entry:entry['favorite']=not entry.get('favorite');self.save();self.refresh_table()

    def add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,tr('Add audio files'),'','Audio files (*.wav *.mp3 *.flac *.ogg *.opus *.aiff *.aif)')
        self.import_paths(paths)
    def import_paths(self,paths):
        category=self.current_filter[4:] if self.current_filter.startswith('cat:') else 'General'
        added=0;errors=[]
        for path in paths[:500]:
            if Path(path).suffix.lower() not in SUPPORTED:errors.append(Path(path).name+': unsupported format');continue
            try:
                info=sf.info(path)
                if info.duration>600:raise ValueError('10-minute limit')
                entry=self.library.add(path,category)
                if entry:entry['duration']=info.duration;added+=1;self.selected_id=entry['id']
            except Exception as e:errors.append(Path(path).name+': '+str(e))
        self.save();self.refresh_table();self.bind_hotkeys()
        self.statusBar().showMessage(f'{added} sounds added. Duplicate files are skipped.')
        if errors:self.error('\n'.join(errors[:8]))
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()
    def dropEvent(self,event):
        self.import_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]);event.acceptProposedAction()
    def add_category(self):
        name,ok=QInputDialog.getText(self,tr('New category'),tr('Category name:'))
        name=name.strip()
        if ok and name and name not in self.library.data['categories']:
            self.library.data['categories'].append(name[:60]);self.save();self.refresh_categories()

    def edit_selected(self):
        entry=self.selected()
        if not entry:return self.notice(tr('Select a sound first.'))
        dialog=QDialog(self);dialog.setWindowTitle(tr('Edit sound details'));form=QFormLayout(dialog)
        title=QLineEdit(entry['name']);category=QComboBox();category.addItems(self.library.data['categories']);category.setCurrentText(entry['category'])
        form.addRow(tr('Name'),title);form.addRow(tr('Category'),category)
        trim=button(tr('Save a section as a new WAV…'),lambda:self.trim_selected(dialog));form.addRow(trim)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            entry['name']=title.text().strip()[:160] or entry['name'];entry['category']=category.currentText();self.save();self.refresh_table()
    def trim_selected(self,parent):
        entry=self.selected()
        if not entry:return
        try:info=sf.info(entry['path'])
        except Exception as e:return self.error(e)
        dialog=QDialog(parent);dialog.setWindowTitle(tr('Save a new sound section'));form=QFormLayout(dialog)
        start=QDoubleSpinBox();end=QDoubleSpinBox()
        for field in (start,end):field.setRange(0,info.duration);field.setDecimals(2);field.setSuffix(' s')
        end.setValue(info.duration);form.addRow(tr('Start'),start);form.addRow(tr('End'),end)
        form.addRow(label(tr('The original stays unchanged; the selection becomes a separate WAV.'),'muted'))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        if end.value()<=start.value():return self.error(tr('End must be after start.'))
        path,_=QFileDialog.getSaveFileName(self,tr('Save as WAV'),entry['name']+' - clip.wav','WAV (*.wav)')
        if not path:return
        if Path(path).resolve()==Path(entry['path']).resolve():return self.error(tr('Choose another name to preserve the original file.'))
        try:
            with sf.SoundFile(entry['path']) as src:
                src.seek(round(start.value()*src.samplerate));samples=src.read(round((end.value()-start.value())*src.samplerate),dtype='float32',always_2d=True);rate=src.samplerate
            sf.write(path,samples,rate,subtype='PCM_16');self.import_paths([path]);self.notice(tr('New sound saved and added to the library.'))
        except Exception as e:self.error(e)
    def remove_selected(self):
        entry=self.selected()
        if not entry:return self.notice(tr('Select a sound first.'))
        if QMessageBox.question(self,tr('Remove from library'),f'Remove “{entry["name"]}” from the library?\nThe audio file will remain on disk.')!=QMessageBox.StandardButton.Yes:return
        if self.loaded_id==entry['id']:self.stop()
        self.library.data['sounds']=[s for s in self.library.sounds if s['id']!=entry['id']];self.selected_id=None;self.save();self.refresh_table();self.bind_hotkeys()

    def table_double_clicked(self,row,col):
        self.selection_changed()
        if col==4:self.edit_hotkey()
        else:self.play_selected()

    def assign_hotkey(self,entry,text):
        text=text.strip()
        if text:
            identity=parse_hotkey(text)
            if identity==parse_hotkey(STOP_HOTKEY):raise ValueError(tr('This combination is reserved for Stop all.'))
            for other in self.library.sounds:
                if other['id']==entry['id'] or not other.get('hotkey'):continue
                try:other_identity=parse_hotkey(other['hotkey'])
                except ValueError:continue
                if identity==other_identity:raise ValueError('This hotkey is already assigned to '+other['name']+'.')
        previous=entry.get('hotkey','');entry['hotkey']=text
        if self.hotkey_enabled.isChecked():
            failures=self.hotkeys.register(self.library.sounds)
            if entry['id'] in self.hotkeys.errors:
                reason=self.hotkeys.errors[entry['id']];entry['hotkey']=previous;self.bind_hotkeys();raise ValueError(reason)
            if failures:self.statusBar().showMessage(tr('Other hotkey warnings: ')+'; '.join(failures))
        self.save();self.refresh_table()
        self.statusBar().showMessage((text+' → '+entry['name']+tr(' • Works while your game is focused.')) if text else tr('Hotkey removed.'))

    def edit_hotkey(self):
        entry=self.selected()
        if not entry:return self.notice(tr('Select a sound first.'))
        dialog=QDialog(self);dialog.setWindowTitle(tr('Assign a game hotkey'));dialog.setMinimumWidth(510);form=QFormLayout(dialog)
        edit=HotkeyEdit(entry.get('hotkey',''))
        form.addRow(tr('Sound'),label(entry['name']))
        form.addRow(tr('Press a key or combination'),edit)
        help_text=label(tr('Numpad digits are separate keys. Keep NumLock on.\nGame microphone: CABLE Output.'),'muted');help_text.setWordWrap(True);form.addRow(help_text)
        capture_error=label('','muted');capture_error.setWordWrap(True);edit.capture_error.connect(capture_error.setText);form.addRow(capture_error)
        clear=button(tr('Clear assignment'),edit.clear);form.addRow(clear)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        self.hotkeys.enabled=False;self.hotkeys.clear()
        try:accepted=dialog.exec()==QDialog.DialogCode.Accepted
        finally:self.hotkeys.enabled=self.hotkey_enabled.isChecked()
        if not accepted:self.bind_hotkeys();return
        text=edit.text()
        try:self.assign_hotkey(entry,text)
        except ValueError as error:self.bind_hotkeys();self.error(error)
    def bind_hotkeys(self):
        if self.hotkey_enabled.isChecked():
            errors=self.hotkeys.register(self.library.sounds)
            if errors:self.statusBar().showMessage(tr('Some global hotkeys are unavailable: ')+'; '.join(errors))
    def toggle_hotkeys(self,enabled):
        self.hotkeys.enabled=enabled
        if enabled:self.bind_hotkeys()
        else:self.hotkeys.clear()
    def on_hotkey(self,action):
        if action=='stop':self.stop();return
        entry=next((sound for sound in self.library.sounds if sound['id']==action),None)
        if not entry:return
        if self.game_hotkeys.isChecked():
            current=self.broadcast_device.currentIndex()
            if current<0 or 'CABLE' not in self.broadcast_device.currentText().upper():
                found=next((i for i in range(self.broadcast_device.count()) if 'CABLE Input' in self.broadcast_device.itemText(i)),None)
                if found is None:
                    self.statusBar().showMessage('Hotkey audio could not be sent: CABLE Input was not found. Connect a virtual microphone device.');return
                self.broadcast_device.setCurrentIndex(found)
            if self.mode.currentData()=='preview':self.mode.setCurrentIndex(self.mode.findData('both'))
        self.selected_id=entry['id'];self.refresh_table();self.play_entry(entry,background=True)

    def refresh_devices(self):
        old_preview=self.preview_device.currentText();old_broadcast=self.broadcast_device.currentText()
        self.preview_device.blockSignals(True);self.broadcast_device.blockSignals(True)
        self.preview_device.clear();self.broadcast_device.clear()
        self.preview_device.addItem(tr('Windows default output'),None);self.broadcast_device.addItem(tr('No broadcast output selected'),None)
        try:
            self.devices=output_devices()
            # Prefer WASAPI. Other host APIs remain visible when WASAPI is unavailable.
            wasapi=[d for d in self.devices if 'WASAPI' in d['api']]
            shown=wasapi or self.devices
            for d in shown:
                name=f'{d["name"]} · {d["api"]}'
                self.preview_device.addItem(name,d['index']);self.broadcast_device.addItem(name,d['index'])
            self.route_hint.setText(tr('Select CABLE Output as your game microphone. Select CABLE Input here.'))
        except Exception as e:self.statusBar().showMessage(tr('Could not read devices: ')+str(e))
        for combo,text in [(self.preview_device,old_preview),(self.broadcast_device,old_broadcast)]:
            index=combo.findText(text)
            if index>=0:combo.setCurrentIndex(index)
            combo.blockSignals(False)
        if self.broadcast_device.currentData() is None:
            for index in range(1,self.broadcast_device.count()):
                if 'CABLE Input' in self.broadcast_device.itemText(index):
                    self.broadcast_device.setCurrentIndex(index);break
    def restore_settings(self):
        settings=dict(self.library.data['settings'])
        sort_index=self.sort_combo.findData(settings.get('sort_order','added'));self.sort_combo.setCurrentIndex(max(0,sort_index))
        for combo,key in [(self.preview_device,'preview'),(self.broadcast_device,'broadcast')]:
            index=combo.findText(settings.get(key,''))
            if index>=0:combo.setCurrentIndex(index)
        index=self.mode.findData(settings.get('mode','preview'));self.mode.setCurrentIndex(max(0,index))
        self.volume.setValue(int(settings.get('volume',65)));self.broadcast_volume.setValue(int(settings.get('broadcast_volume',65)));self.normalize.setChecked(bool(settings.get('normalize',False)));self.game_hotkeys.setChecked(bool(settings.get('hotkeys_to_mic',True)));self.volumes_changed()
    def volumes_changed(self,*args):
        if not hasattr(self,'broadcast_volume'):return
        self.engine.preview_gain=self.volume.value()/100;self.engine.broadcast_gain=self.broadcast_volume.value()/100
        self.volume.setToolTip(tr('Monitor: %')+str(self.volume.value()));self.broadcast_volume.setToolTip(tr('Broadcast: %')+str(self.broadcast_volume.value()))
        self.settings_changed()
    def settings_changed(self,*args):
        if self.initializing or not hasattr(self,'route_hint'):return
        self.library.data['settings'].update(preview=self.preview_device.currentText(),broadcast=self.broadcast_device.currentText(),mode=self.mode.currentData(),volume=self.volume.value(),broadcast_volume=self.broadcast_volume.value(),normalize=self.normalize.isChecked(),hotkeys_to_mic=self.game_hotkeys.isChecked())
        self.save()

    def play_selected(self):
        entry=self.selected()
        if not entry:return self.notice(tr('Select a sound first. Double-click to play.'))
        self.play_entry(entry)
    def play_entry(self,entry,background=False):
        def report(message):
            if background:self.statusBar().showMessage(tr('Hotkey: ')+str(message))
            else:self.error(message)
        if not Path(entry['path']).is_file():return report(tr('Audio file moved or deleted. Add it again.'))
        if self.mode.currentData()!='preview' and self.broadcast_device.currentData() is None:return report(tr('Select an output device before broadcasting.'))
        self.stop();self.generation+=1
        self.pending_background=background
        self.pending=(self.generation,entry,self.executor.submit(load_clip,entry['path'],self.normalize.isChecked()))
        self.now.setText(tr('Loading: ')+entry['name']);self.statusBar().showMessage(tr('Preparing audio…'))
    def stop(self):
        self.generation+=1
        if self.pending:self.pending[2].cancel();self.pending=None
        self.engine.stop();self.pause_button.setText(tr('Pause'));self.seek.setValue(0);self.wave.progress=0;self.wave.update();self.meter.setValue(0)
        self.statusBar().showMessage(tr('Stopped'))
    def pause(self):
        if not self.engine.tracks:return
        self.engine.paused=not self.engine.paused
        self.pause_button.setText(tr('▶  Resume') if self.engine.paused else tr('Pause'))
    def seek_released(self):
        self.drag_seek=False
        if self.loaded_clip:self.engine.seek(self.seek.value()/1000*self.loaded_clip.duration)
    def tick(self):
        if self.pending and self.pending[2].done():
            generation,entry,future=self.pending;self.pending=None
            if generation==self.generation:
                try:
                    clip=future.result();self.engine.play(clip,self.preview_device.currentData(),self.broadcast_device.currentData(),self.mode.currentData())
                    self.loaded_clip=clip;self.loaded_id=entry['id'];self.wave.set_audio(clip.samples);self.now.setText(entry['name']);entry['duration']=clip.duration;entry['plays']=entry.get('plays',0)+1;entry['last_played']=time.time();self.save();self.refresh_table();self.statusBar().showMessage(tr('Playing • ')+self.mode.currentText())
                except Exception as e:
                    self.now.setText(tr('Could not play sound'))
                    if self.pending_background:self.statusBar().showMessage(tr('Hotkey playback failed: ')+str(e))
                    else:self.error(e)
        if self.loaded_clip:
            duration=self.loaded_clip.duration;position=self.engine.position
            self.clock.setText(fmt_time(position)+' / '+fmt_time(duration))
            progress=min(1,position/duration) if duration else 0
            if not self.drag_seek:self.seek.setValue(round(progress*1000))
            self.wave.progress=progress;self.wave.update()
            self.meter.setValue(round(self.engine.peak*100))
            if self.engine.tracks and not self.engine.playing and not self.engine.paused:
                self.engine.stop();self.statusBar().showMessage(tr('Finished'));self.meter.setValue(0)
        self.sync_dashboard()
        if self.engine.bus.warning:
            self.statusBar().showMessage(tr('Broadcast device: ')+self.engine.bus.warning);self.engine.bus.warning=''
        if self.engine.warning:self.statusBar().showMessage(tr('Audio device: ')+self.engine.warning);self.engine.warning=''
    def show_broadcast_dialog(self):
        output=self.broadcast_device.currentData()
        if output is None:
            return self.notice('Install a virtual audio driver such as VB-CABLE first. Reopen SesKutusu, select CABLE Input as the broadcast output and CABLE Output as the microphone in the receiving app.')
        if 'CABLE' not in self.broadcast_device.currentText().upper():
            return self.notice('Sending the microphone to speakers may cause feedback. Select a virtual audio device such as CABLE Input for broadcast.')
        dialog=QDialog(self);dialog.setWindowTitle(tr('Send microphone audio to other apps'));dialog.setMinimumWidth(560)
        form=QFormLayout(dialog)
        info=label('SesKutusu → CABLE Input → CABLE Output → Discord / oyun mikrofonu','muted');info.setWordWrap(True);form.addRow(info)
        use_mic=QCheckBox(tr('Include my microphone with file audio'))
        settings=self.library.data['settings'];use_mic.setChecked(bool(settings.get('include_mic',False)));form.addRow(use_mic)
        mic=QComboBox()
        try:
            output_info=next(d for d in self.devices if d['index']==output)
            microphones=[d for d in input_devices() if d['api']==output_info['api'] and 'CABLE' not in d['name'].upper()]
            for device in microphones:mic.addItem(device['name']+' · '+device['api'],device['index'])
        except Exception as err:return self.error(err)
        previous=mic.findText(settings.get('mic_device',''))
        if previous>=0:mic.setCurrentIndex(previous)
        form.addRow(tr('Physical microphone'),mic)
        gain=QSlider(Qt.Orientation.Horizontal);gain.setRange(0,200);gain.setValue(int(settings.get('mic_volume',100)));form.addRow(tr('Microphone level (0–200%)'),gain)
        block=QCheckBox(tr('Mute my voice while a file is playing'));block.setChecked(bool(settings.get('block_voice',False)));form.addRow(block)
        note=label('Broadcast stays active after this dialog closes. Stop broadcast also stops the microphone.\nMicrophone audio is not recorded to disk.','muted');note.setWordWrap(True);form.addRow(note)
        controls=QHBoxLayout();start=button(tr('Start broadcast'),lambda:None,'accent');end=button(tr('Stop broadcast'),lambda:None,'stop');cancel=button(tr('Close'),dialog.reject)
        controls.addWidget(start);controls.addWidget(end);controls.addWidget(cancel);form.addRow(controls)
        def disconnect():
            self.stop();self.engine.bus.stop();self.broadcast_status.setText(tr('Microphone broadcast off'));dialog.accept()
        def connect():
            if use_mic.isChecked() and mic.currentData() is None:return self.error(tr('No physical microphone available.'))
            self.stop()
            try:
                self.engine.bus.mic_gain=gain.value()/100;self.engine.bus.block_voice=block.isChecked()
                self.engine.bus.start(output,mic.currentData() if use_mic.isChecked() else None)
            except Exception as err:return self.error(tr('Could not start broadcast: ')+str(err))
            settings.update(include_mic=use_mic.isChecked(),mic_device=mic.currentText(),mic_volume=gain.value(),block_voice=block.isChecked())
            self.mode.setCurrentIndex(self.mode.findData('both'));self.save()
            self.broadcast_status.setText(('Microphone + file' if use_mic.isChecked() else 'File only')+' → CABLE Output (select as the microphone in the receiving app)')
            self.statusBar().showMessage(tr('Broadcast on. Play a sound from your library.'));dialog.accept()
        start.clicked.disconnect();start.clicked.connect(connect);end.clicked.disconnect();end.clicked.connect(disconnect)
        dialog.exec()

    def show_routing(self):
        self.notice(tr('Broadcast output: CABLE Input.\nGame microphone: CABLE Output.\nUse Mix microphone to include your voice.\nCtrl+Alt+F10 stops the file. Stop broadcast to mute the live microphone.')+str(self.library.root))
    def closeEvent(self,event):
        self.timer.stop();self.hotkeys.clear();QApplication.instance().removeNativeEventFilter(self.hotkeys);self.engine.close();self.executor.shutdown(wait=True,cancel_futures=True);self.save();event.accept()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--screenshot');parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args()
    app=QApplication(sys.argv[:1])
    system_font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'segoeui.ttf'
    if system_font.exists():QFontDatabase.addApplicationFont(str(system_font))
    symbol_font=system_font.parent/'seguisym.ttf'
    if symbol_font.exists():QFontDatabase.addApplicationFont(str(symbol_font))
    app.setApplicationName('SesKutusu');app.setStyle('Fusion');app.setStyleSheet(STYLE)
    icon_path=Path(__file__).resolve().parent/'app-icon.ico'
    if icon_path.exists():app.setWindowIcon(QIcon(str(icon_path)))
    root=Path(args.data_dir) if args.data_dir else (Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent)/'data'
    root.mkdir(parents=True,exist_ok=True)
    instance_lock=QLockFile(str(root/'instance.lock'))
    if not instance_lock.tryLock(100):
        QMessageBox.information(None,'SesKutusu',tr('SesKutusu is already using this library.'));return 0
    try:window=Window(root)
    except Exception as e:QMessageBox.critical(None,'Could not open SesKutusu',str(e));return 1
    window.show()
    if args.screenshot:QTimer.singleShot(1500,lambda:window.grab().save(args.screenshot))
    if args.smoke_test:QTimer.singleShot(2200,window.close)
    return app.exec()

if __name__=='__main__':raise SystemExit(main())







