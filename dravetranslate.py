#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DraveTranslate - offline vertaler (Dravenlock-huisstijl).

Vertaalt tekst tussen vele talen, volledig op je eigen pc. Primair via Argos
(echte offline vertaalmodellen); valt terug op een lokaal taalmodel als een
talenpaar nog niet beschikbaar is. Grote, leesbare tekst (toegankelijk),
donker thema, NL/EN, Snelgids + Donatie.
"""
import os
import sys
import json
import threading

from PyQt6.QtCore import Qt, QLocale, QUrl, QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import (QPixmap, QIcon, QDesktopServices, QKeySequence,
                         QShortcut, QPainter, QColor, QFont)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QPlainTextEdit, QMessageBox, QDialog, QFrame,
    QStatusBar, QToolButton, QSplitter, QTextBrowser, QLineEdit, QFileDialog,
    QSplashScreen)

import engine
import speak
from engine import LANGUAGES, lang_name

APP_NAME = "DraveTranslate"
APP_VERSION = "0.1.3"
DONATE_URL = "https://paypal.me/roger076"
SUPPORT_MAIL = "service@dravenlock.nl"
# Betrouwbaar woordenboek Nederlands <-> Papiamentu (Antilliaans)
PALABRICKS_URL = "https://palabricks.nl/woordenboek-nederlands-papiamentu"

# ---- Dravenlock-huisstijl ----
BG = "#0e0e11"
PANEL = "#16161b"
SILVER = "#d4d4d4"
MUTE = "#8a8a94"
ACCENT = "#6fa3d6"
WARN = "#e0a23a"


# ---------------------------------------------------------------------------
# Pad / config
# ---------------------------------------------------------------------------
def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _config_path():
    return os.path.join(_app_dir(), "dravetranslate_config.json")


DEFAULT_CONFIG = {"lang": "", "from": "auto", "to": "en", "llm_model_path": "",
                  "voice_name": "", "voice_speed": 1.0}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Taal van de interface (NL/EN)
# ---------------------------------------------------------------------------
_LANG = "nl"

TRANSLATIONS = {
    "en": {
        "Vertaal": "Translate", "Wissel": "Swap", "Kopieer": "Copy",
        "Wis": "Clear", "Spreek uit": "Speak", "Van:": "From:", "Naar:": "To:",
        "Automatisch": "Automatic", "Instellingen…": "Settings…",
        "Snelgids": "Quick guide", "Over": "About", "Sluiten": "Close",
        "Taal:": "Language:", "Automatisch (OS)": "Automatic (OS)",
        "Nederlands": "Dutch", "Engels": "English", "Donatie": "Donate",
        "Opslaan": "Save", "Annuleren": "Cancel",
        "Typ of plak hier je tekst…": "Type or paste your text here…",
        "De vertaling verschijnt hier.": "The translation appears here.",
        "Bezig met vertalen…": "Translating…",
        "Talenpaar downloaden (eenmalig)…":
            "Downloading language pack (one-time)…",
        "Model downloaden (~1 GB, eenmalig)…":
            "Downloading model (~1 GB, one-time)…",
        "Klaar": "Done", "Gekopieerd": "Copied",
        "Lokaal model (GGUF) voor terugval:": "Local model (GGUF) for fallback:",
        "Bladeren…": "Browse…", "Stem:": "Voice:", "Snelheid:": "Speed:",
        "Langzaam": "Slow", "Normaal": "Normal", "Snel": "Fast",
        "(standaardstem)": "(default voice)", "Test stem": "Test voice",
        "Woordenboek Papiamentu": "Papiamentu dictionary",
    }
}


def t(s, lang=None):
    lg = lang or _LANG
    if lg == "nl":
        return s
    return TRANSLATIONS.get(lg, {}).get(s, s)


def detect_ui_lang(cfg):
    forced = (cfg.get("lang") or "").strip().lower()
    if forced in ("nl", "en"):
        return forced
    try:
        return "nl" if QLocale.system().name().lower().startswith("nl") else "en"
    except Exception:
        return "nl"


# ---------------------------------------------------------------------------
# Logo / icoon
# ---------------------------------------------------------------------------
def _logo_path(name):
    for base in (_app_dir(), os.path.join(_app_dir(), "assets"),
                 os.path.join(_app_dir(), "..", "assets")):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return None


def logo_pixmap(size=34):
    for n in ("logo_t.png", "logo.png"):
        p = _logo_path(n)
        if p:
            pm = QPixmap(p)
            if not pm.isNull():
                return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def app_icon():
    for n in ("app.ico", "logo.ico", "logo.png"):
        p = _logo_path(n)
        if p:
            ic = QIcon(p)
            if not ic.isNull():
                return ic
    return QIcon()


# ---------------------------------------------------------------------------
# Vertaal-worker (op een aparte thread, zodat de UI niet bevriest)
# ---------------------------------------------------------------------------
class Worker(QObject):
    done = pyqtSignal(str, str, str)     # vertaling, motor, gebruikte brontaal
    failed = pyqtSignal(str)
    status = pyqtSignal(str)
    need_model = pyqtSignal()            # lokaal model nodig (vraag toestemming)

    def __init__(self, translator, text, frm, to, allow_download=False):
        super().__init__()
        self.translator = translator
        self.text = text
        self.frm = frm
        self.to = to
        self.allow_download = allow_download

    def run(self):
        try:
            res, eng, used = self.translator.translate(
                self.text, self.frm, self.to,
                on_status=lambda s: self.status.emit(s),
                allow_download=self.allow_download)
            self.done.emit(res, eng, used)
        except engine.ModelNeeded:
            self.need_model.emit()
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------------------
# Spraak: neuvoice (Dravenlock-standaard). De voorleesstem is instelbaar.
# ---------------------------------------------------------------------------
def tts_lang(to_code):
    """neuvoice spreekt nl/en; map de doeltaal daarop (anders Engels)."""
    return "nl" if to_code == "nl" else "en"


# ---------------------------------------------------------------------------
# Snelgids
# ---------------------------------------------------------------------------
GUIDE_NL = """DraveTranslate - Snelgids

DraveTranslate vertaalt tekst tussen veel talen, helemaal op je eigen pc.

Aan de slag
- Typ of plak je tekst in het linkervak.
- Kies links de brontaal (of laat 'Automatisch' staan) en rechts de doeltaal.
- Klik 'Vertaal' (of Ctrl+Enter). De vertaling komt in het rechtervak.
- 'Wissel' draait de talen EN de teksten om. 'Kopieer' zet de vertaling op
  het klembord. 'Wis' maakt de vakken leeg. 'Spreek uit' leest de vertaling
  voor met de Dravenlock-stem (instelbaar bij Instellingen: kies stem en
  snelheid; de stem wordt de eerste keer gedownload).

Offline
- DraveTranslate gebruikt Argos: echte offline vertaalmodellen. De eerste keer
  dat je een talenpaar gebruikt, wordt daar eenmalig een klein modelletje voor
  gedownload (internet nodig). Daarna werkt dat paar zonder internet.
- Lukt een talenpaar niet, dan valt DraveTranslate terug op een lokaal
  taalmodel (een GGUF-model, zoals bij DraveAI) als dat aanwezig is.

Tip
- Voor de offline terugval kun je in Instellingen een GGUF-model kiezen, of er
  eentje in de map DraveTranslate-data\\model zetten.

Vragen of een tip? service@dravenlock.nl
"""

GUIDE_EN = """DraveTranslate - Quick guide

DraveTranslate translates text between many languages, entirely on your own pc.

Getting started
- Type or paste your text in the left box.
- Pick the source language on the left (or leave 'Automatic') and the target
  language on the right.
- Click 'Translate' (or Ctrl+Enter). The translation appears on the right.
- 'Swap' flips the languages AND the texts. 'Copy' puts the translation on the
  clipboard. 'Clear' empties the boxes. 'Speak' reads the translation aloud with
  the Dravenlock voice (configurable under Settings: voice and speed; the voice
  is downloaded the first time).

Offline
- DraveTranslate uses Argos: real offline translation models. The first time you
  use a language pair, a small model is downloaded once (internet needed). After
  that, that pair works without internet.
- If a pair is unavailable, DraveTranslate falls back to a local language model
  (a GGUF model, like DraveAI) if one is present.

Questions or a tip? service@dravenlock.nl
"""


class GuideDialog(QDialog):
    def __init__(self, parent, lang):
        super().__init__(parent)
        self.setWindowTitle(t("Snelgids", lang))
        self.resize(640, 560)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setObjectName("guide")
        tb.setPlainText(GUIDE_NL if lang == "nl" else GUIDE_EN)
        lay.addWidget(tb)
        b = QPushButton(t("Sluiten", lang))
        b.clicked.connect(self.accept)
        lay.addWidget(b, alignment=Qt.AlignmentFlag.AlignRight)


class SettingsDialog(QDialog):
    def __init__(self, parent, cfg, lang, voicebox=None):
        super().__init__(parent)
        self.cfg = cfg
        self.voicebox = voicebox
        self.setWindowTitle(t("Instellingen…", lang))
        self.resize(580, 300)
        lay = QVBoxLayout(self)
        # interface-taal
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(t("Taal:", lang)))
        self.cmb = QComboBox()
        self.cmb.addItem(t("Automatisch (OS)", lang), "")
        self.cmb.addItem(t("Nederlands", lang), "nl")
        self.cmb.addItem(t("Engels", lang), "en")
        idx = {"": 0, "nl": 1, "en": 2}.get(cfg.get("lang", ""), 0)
        self.cmb.setCurrentIndex(idx)
        row1.addWidget(self.cmb, 1)
        lay.addLayout(row1)
        # stem (voorleesstem) - keuze uit de neuvoice-stemmen
        rowv = QHBoxLayout()
        rowv.addWidget(QLabel(t("Stem:", lang)))
        self.voice = QComboBox()
        self.voice.addItem(t("(standaardstem)", lang), "")
        try:
            namen = self.voicebox.list_voices() if self.voicebox else []
        except Exception:
            namen = []
        for naam in namen:
            self.voice.addItem(naam, naam)
        cur = cfg.get("voice_name", "")
        for i in range(self.voice.count()):
            if self.voice.itemData(i) == cur:
                self.voice.setCurrentIndex(i)
                break
        rowv.addWidget(self.voice, 1)
        test = QPushButton(t("Test stem", lang))
        test.clicked.connect(self._test_voice)
        rowv.addWidget(test)
        lay.addLayout(rowv)
        # snelheid (neuvoice: multiplier)
        rows = QHBoxLayout()
        rows.addWidget(QLabel(t("Snelheid:", lang)))
        self.rate = QComboBox()
        self.rate.addItem(t("Langzaam", lang), 0.8)
        self.rate.addItem(t("Normaal", lang), 1.0)
        self.rate.addItem(t("Snel", lang), 1.3)
        ridx = {0.8: 0, 1.0: 1, 1.3: 2}.get(float(cfg.get("voice_speed", 1.0) or 1.0), 1)
        self.rate.setCurrentIndex(ridx)
        rows.addWidget(self.rate, 1)
        lay.addLayout(rows)
        # lokaal model (terugval)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(t("Lokaal model (GGUF) voor terugval:", lang)))
        self.path = QLineEdit(cfg.get("llm_model_path", ""))
        row2.addWidget(self.path, 1)
        br = QPushButton(t("Bladeren…", lang))
        br.clicked.connect(self._browse)
        row2.addWidget(br)
        lay.addLayout(row2)
        lay.addStretch(1)
        # knoppen
        row3 = QHBoxLayout()
        row3.addStretch(1)
        ok = QPushButton(t("Opslaan", lang))
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        ca = QPushButton(t("Annuleren", lang))
        ca.clicked.connect(self.reject)
        row3.addWidget(ca)
        row3.addWidget(ok)
        lay.addLayout(row3)

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "GGUF", "", "GGUF (*.gguf)")
        if p:
            self.path.setText(p)

    def _test_voice(self):
        if not self.voicebox:
            return
        self.voicebox.set_voice(self.voice.currentData())
        self.voicebox.speed = self.rate.currentData()
        self.voicebox.speak("Hallo, dit is de gekozen stem.", "nl")

    def result_cfg(self):
        self.cfg["lang"] = self.cmb.currentData()
        self.cfg["llm_model_path"] = self.path.text().strip()
        self.cfg["voice_name"] = self.voice.currentData()
        self.cfg["voice_speed"] = self.rate.currentData()
        return self.cfg


# ---------------------------------------------------------------------------
# Hoofdvenster
# ---------------------------------------------------------------------------
class DraveTranslate(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.lang = detect_ui_lang(cfg)
        self.translator = engine.Translator(cfg)
        self.voicebox = speak.Voice(cfg.get("voice_name", ""),
                                    float(cfg.get("voice_speed", 1.0) or 1.0))
        self.thread = None
        self.worker = None
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1000, 680)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_header())
        outer.addWidget(self._build_langbar())

        # tekstvakken
        split = QSplitter(Qt.Orientation.Horizontal)
        self.src = QPlainTextEdit()
        self.src.setObjectName("box")
        self.src.setPlaceholderText(t("Typ of plak hier je tekst…", self.lang))
        self.dst = QPlainTextEdit()
        self.dst.setObjectName("box")
        self.dst.setReadOnly(True)
        self.dst.setPlaceholderText(t("De vertaling verschijnt hier.", self.lang))
        split.addWidget(self.src)
        split.addWidget(self.dst)
        split.setSizes([500, 500])
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(12, 10, 12, 6)
        wl.addWidget(split)
        outer.addWidget(wrap, 1)

        outer.addWidget(self._build_buttons())

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("DraveTranslate")
        # de check of Argos/terugval aanwezig zijn doet zware imports; pas NA het
        # tonen van het venster uitvoeren, zodat de app meteen opent
        QTimer.singleShot(80, self._refresh_status_hint)

        # woordenboek-knop tonen/verbergen bij taalkeuze
        self.cmb_from.currentIndexChanged.connect(self._update_dict_button)
        self.cmb_to.currentIndexChanged.connect(self._update_dict_button)
        self._update_dict_button()

        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._translate)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self._translate)
        QShortcut(QKeySequence("F1"), self).activated.connect(self._guide)

    # ---- opbouw ----
    def _build_header(self):
        h = QWidget()
        h.setObjectName("header")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(14, 8, 14, 8)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(34))
        lay.addWidget(logo)
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        lay.addWidget(title)
        ver = QLabel("v" + APP_VERSION)
        ver.setObjectName("ver")
        lay.addWidget(ver)
        lay.addStretch(1)
        for label, cb in ((t("Instellingen…", self.lang), self._settings),
                          (t("Snelgids", self.lang), self._guide),
                          (t("Over", self.lang), self._about)):
            b = QPushButton(label)
            b.setObjectName("headerbtn")
            b.clicked.connect(cb)
            lay.addWidget(b)
        dn = QToolButton()
        dn.setObjectName("donate")
        dn.setText("♥ " + t("Donatie", self.lang))
        dn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DONATE_URL)))
        lay.addWidget(dn)
        return h

    def _build_langbar(self):
        bar = QWidget()
        bar.setObjectName("toolbar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.addWidget(QLabel(t("Van:", self.lang)))
        self.cmb_from = QComboBox()
        self.cmb_from.addItem(t("Automatisch", self.lang), "auto")
        for code, nl, en in LANGUAGES:
            self.cmb_from.addItem(lang_name(code, self.lang), code)
        self._select(self.cmb_from, self.cfg.get("from", "auto"))
        lay.addWidget(self.cmb_from, 1)

        swap = QPushButton("⇄")
        swap.setToolTip(t("Wissel", self.lang))
        swap.clicked.connect(self._swap)
        lay.addWidget(swap)

        lay.addWidget(QLabel(t("Naar:", self.lang)))
        self.cmb_to = QComboBox()
        for code, nl, en in LANGUAGES:
            self.cmb_to.addItem(lang_name(code, self.lang), code)
        self._select(self.cmb_to, self.cfg.get("to", "en"))
        lay.addWidget(self.cmb_to, 1)
        return bar

    def _build_buttons(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 4, 12, 12)
        self.btn_tr = QPushButton(t("Vertaal", self.lang))
        self.btn_tr.setObjectName("primary")
        self.btn_tr.clicked.connect(self._translate)
        lay.addWidget(self.btn_tr)
        for label, cb in ((t("Wissel", self.lang), self._swap),
                          (t("Kopieer", self.lang), self._copy),
                          (t("Wis", self.lang), self._clear)):
            b = QPushButton(label)
            b.clicked.connect(cb)
            lay.addWidget(b)
        self.btn_speak = QPushButton(t("Spreek uit", self.lang))
        self.btn_speak.clicked.connect(self._speak)
        self.btn_speak.setEnabled(self.voicebox.available())
        lay.addWidget(self.btn_speak)
        # woordenboek-knop voor Papiaments (verschijnt alleen bij die taal)
        self.btn_dict = QPushButton("📖 " + t("Woordenboek Papiamentu", self.lang))
        self.btn_dict.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(PALABRICKS_URL)))
        self.btn_dict.setVisible(False)
        lay.addWidget(self.btn_dict)
        lay.addStretch(1)
        return bar

    def _update_dict_button(self):
        pap = "pap" in (self.cmb_from.currentData(), self.cmb_to.currentData())
        self.btn_dict.setVisible(pap)

    # ---- helpers ----
    def _select(self, combo, code):
        for i in range(combo.count()):
            if combo.itemData(i) == code:
                combo.setCurrentIndex(i)
                return

    def _refresh_status_hint(self):
        st = self.translator.status()
        parts = []
        parts.append("Argos: " + ("aan" if st["argos"] else "niet geinstalleerd"))
        parts.append("terugval-model: " + ("aanwezig" if st["llm"] else "geen"))
        self.status.showMessage("  |  ".join(parts))

    # ---- acties ----
    def _swap(self):
        frm = self.cmb_from.currentData()
        to = self.cmb_to.currentData()
        a = self.src.toPlainText()
        b = self.dst.toPlainText()
        # talen omdraaien
        self._select(self.cmb_from, to)
        if frm != "auto":
            self._select(self.cmb_to, frm)
        # teksten omdraaien (alleen als er een vertaling staat)
        if b.strip():
            self.src.setPlainText(b)
            self.dst.setPlainText(a)

    def _copy(self):
        QApplication.clipboard().setText(self.dst.toPlainText())
        self.status.showMessage(t("Gekopieerd", self.lang), 2000)

    def _clear(self):
        self.src.clear()
        self.dst.clear()

    def _speak(self):
        txt = self.dst.toPlainText().strip()
        if txt:
            self.voicebox.speak(txt, tts_lang(self.cmb_to.currentData()))

    def _translate(self, allow_download=False):
        if self.thread is not None:
            return
        text = self.src.toPlainText().strip()
        if not text:
            return
        frm = self.cmb_from.currentData()
        to = self.cmb_to.currentData()
        self.cfg["from"] = frm
        self.cfg["to"] = to
        save_config(self.cfg)
        self.btn_tr.setEnabled(False)
        self.dst.setPlainText("")
        self.status.showMessage(t("Bezig met vertalen…", self.lang))
        self.thread = QThread()
        self.worker = Worker(self.translator, text, frm, to,
                             allow_download=allow_download)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self._on_status)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.need_model.connect(self._on_need_model)
        self.thread.start()

    def _on_need_model(self):
        # eerst toestemming vragen voor de eenmalige download (transparant)
        self._end_thread()
        vraag = (
            "Voor deze taal (bijv. Papiaments) is een los onderdeel nodig: een "
            "lokaal taalmodel van ongeveer 1 GB. Dat wordt eenmalig gedownload "
            "naar DraveTranslate-data\\model.\n\nNu downloaden en vertalen?"
            if self.lang == "nl" else
            "This language (e.g. Papiamento) needs an extra component: a local "
            "model of about 1 GB, downloaded once to DraveTranslate-data\\model."
            "\n\nDownload now and translate?")
        r = QMessageBox.question(self, APP_NAME, vraag,
                                 QMessageBox.StandardButton.Yes
                                 | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._translate(allow_download=True)
        else:
            self.status.showMessage(t("Klaar", self.lang), 2000)

    def _on_status(self, s):
        if s == "downloading":
            self.status.showMessage(t("Talenpaar downloaden (eenmalig)…", self.lang))
        elif s == "model_download":
            self.status.showMessage(t("Model downloaden (~1 GB, eenmalig)…", self.lang))
        elif s == "llm":
            self.status.showMessage(t("Bezig met vertalen…", self.lang))

    def _on_done(self, res, eng, used):
        self.dst.setPlainText(res)
        self._end_thread()
        naam = {"argos": "Argos", "llm": "lokaal model", "gelijk": "-"}.get(eng, eng)
        extra = ""
        if self.cmb_from.currentData() == "auto" and used:
            extra = "  |  herkend: " + lang_name(used, self.lang)
        self.status.showMessage("%s (%s)%s" % (t("Klaar", self.lang), naam, extra),
                                6000)

    def _on_failed(self, msg):
        self._end_thread()
        self.status.showMessage("Fout", 4000)
        QMessageBox.warning(self, APP_NAME, msg)

    def _end_thread(self):
        try:
            self.thread.quit()
            self.thread.wait(2000)
        except Exception:
            pass
        self.thread = None
        self.worker = None
        self.btn_tr.setEnabled(True)

    def _settings(self):
        dlg = SettingsDialog(self, dict(self.cfg), self.lang, self.voicebox)
        if dlg.exec():
            self.cfg = dlg.result_cfg()
            save_config(self.cfg)
            self.translator = engine.Translator(self.cfg)
            self.voicebox.set_voice(self.cfg.get("voice_name", ""))
            self.voicebox.speed = float(self.cfg.get("voice_speed", 1.0) or 1.0)
            self._refresh_status_hint()
            QMessageBox.information(
                self, APP_NAME,
                "Opgeslagen. Sommige wijzigingen (interface-taal) zijn na een "
                "herstart zichtbaar." if self.lang == "nl" else
                "Saved. Some changes (interface language) apply after a restart.")

    def _guide(self):
        GuideDialog(self, self.lang).exec()

    def _about(self):
        QMessageBox.information(
            self, t("Over", self.lang),
            "%s v%s\n\nOffline vertaler (Argos + lokaal model).\nDravenlock\n%s\n%s"
            % (APP_NAME, APP_VERSION, SUPPORT_MAIL, DONATE_URL))


QSS = """
* { font-family: 'Segoe UI', sans-serif; font-size: 15px; color: %(silver)s; }
QMainWindow, QWidget { background: %(bg)s; }
#header { background: %(panel)s; border-bottom: 1px solid #23232b; }
#title { font-size: 20px; font-weight: 700; }
#ver { color: %(mute)s; font-size: 12px; }
#toolbar { background: %(bg)s; border-bottom: 1px solid #23232b; }
QPushButton { background: %(panel)s; border: 1px solid #2c2c36; border-radius: 8px;
              padding: 9px 15px; color: %(silver)s; }
QPushButton:hover { border-color: %(accent)s; }
QPushButton:disabled { color: #5a5a63; border-color: #23232b; }
QPushButton#primary { background: %(accent)s; color: #08131f; font-weight: 700;
                      border: none; padding: 10px 22px; font-size: 16px; }
QPushButton#primary:hover { background: #87b6e3; }
QPushButton#headerbtn { padding: 6px 11px; }
QToolButton#donate { border: none; background: transparent; color: %(accent)s; }
QComboBox, QLineEdit { background: #1a1a20; border: 1px solid #2c2c36;
    border-radius: 8px; padding: 8px; color: %(silver)s;
    selection-background-color: %(accent)s; selection-color: #08131f; }
QComboBox:focus, QLineEdit:focus { border-color: %(accent)s; }
QComboBox QAbstractItemView { background: #1a1a20; color: %(silver)s;
    selection-background-color: %(accent)s; selection-color: #08131f; }
QPlainTextEdit#box, QTextBrowser#guide {
    background: #1a1a20; border: 1px solid #2c2c36; border-radius: 10px;
    padding: 10px; color: %(silver)s; font-size: 18px;
    selection-background-color: %(accent)s; selection-color: #08131f; }
QPlainTextEdit#box:focus { border-color: %(accent)s; }
QStatusBar { background: %(panel)s; color: %(mute)s; }
QSplitter::handle { background: #23232b; width: 6px; }
QDialog { background: %(bg)s; }
""" % {"bg": BG, "panel": PANEL, "silver": SILVER, "mute": MUTE,
       "accent": ACCENT, "warn": WARN}


def _install_excepthook():
    import traceback

    def hook(exctype, value, tb):
        msg = "".join(traceback.format_exception(exctype, value, tb))
        try:
            with open(os.path.join(_app_dir(), "dravetranslate-fout.txt"),
                      "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        try:
            if QApplication.instance():
                QMessageBox.critical(None, APP_NAME + " - fout",
                                     "Er ging iets mis:\n\n" + msg[-1500:]
                                     + "\n\n(Ook opgeslagen in dravetranslate-fout.txt)")
        except Exception:
            pass
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = hook


def _make_splash():
    """Een eenvoudig splashscherm met het drakenlogo + naam."""
    try:
        pm = QPixmap(520, 440)
        pm.fill(QColor("#0e0e11"))
        p = QPainter(pm)
        logo = None
        for n in ("logo_t.png", "logo.png"):
            path = _logo_path(n)
            if path:
                img = QPixmap(path)
                if not img.isNull():
                    logo = img.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                    break
        if logo is not None:
            p.drawPixmap((pm.width() - logo.width()) // 2, 40, logo)
        p.setPen(QColor("#eaeaf0"))
        p.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        p.drawText(pm.rect().adjusted(0, 350, 0, 0),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "DraveTranslate")
        p.setPen(QColor("#9a9aa4"))
        p.setFont(QFont("Segoe UI", 12))
        p.drawText(pm.rect().adjusted(0, 398, 0, 0),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   "laden…")
        p.end()
        return QSplashScreen(pm)
    except Exception:
        return None


def main():
    global _LANG
    _install_excepthook()
    app = QApplication(sys.argv)
    try:
        cfg = load_config()
        _LANG = detect_ui_lang(cfg)
        app.setStyleSheet(QSS)
        app.setWindowIcon(app_icon())
        splash = _make_splash()
        if splash is not None:
            splash.show()
            app.processEvents()
        win = DraveTranslate(cfg)
        win.show()
        if splash is not None:
            splash.finish(win)
    except Exception:
        sys.excepthook(*sys.exc_info())
        return
    try:  # Dravenlock: stille update-check (uit te zetten; Ctrl+Shift+U = met de hand)
        import drave_update
        drave_update.start(win, 'DraveTranslate', APP_VERSION)
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
