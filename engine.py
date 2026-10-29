# -*- coding: utf-8 -*-
"""engine.py - vertaalmotor voor DraveTranslate.

Volgorde:
  1) Argos Translate  -> echte OFFLINE vertaalmodellen (beste kwaliteit, geen
     internet nodig na de eenmalige download van een talenpaar).
  2) Lokaal taalmodel -> als terugval (zelfde soort GGUF-model als DraveAI),
     handig als een Argos-talenpaar (nog) niet beschikbaar is.

Taaldetectie via 'langdetect' (klein, offline). Alles faalt netjes: ontbreekt
een onderdeel, dan meldt de motor dat duidelijk i.p.v. te crashen.
"""
from __future__ import annotations

import os
import sys


class ModelNeeded(Exception):
    """Voor deze taal is een lokaal model nodig dat nog gedownload moet worden.
    We gooien dit i.p.v. stilletjes te downloaden, zodat de app het eerst vraagt."""


# (code, Nederlandse naam, Engelse naam)
# De meeste hiervan kan Argos OFFLINE. Talen met een '*' (zoals Papiaments)
# kent Argos niet; die lopen via de lokale-model-terugval (wisselende kwaliteit).
LANGUAGES = [
    ("en", "Engels", "English"),
    ("nl", "Nederlands", "Dutch"),
    ("pap", "Papiaments (Antilliaans)*", "Papiamento"),
    ("af", "Afrikaans", "Afrikaans"),
    ("sq", "Albanees", "Albanian"),
    ("ar", "Arabisch", "Arabic"),
    ("az", "Azerbeidzjaans", "Azerbaijani"),
    ("bn", "Bengaals", "Bengali"),
    ("bg", "Bulgaars", "Bulgarian"),
    ("ca", "Catalaans", "Catalan"),
    ("zh", "Chinees", "Chinese"),
    ("da", "Deens", "Danish"),
    ("de", "Duits", "German"),
    ("et", "Estisch", "Estonian"),
    ("fi", "Fins", "Finnish"),
    ("fr", "Frans", "French"),
    ("el", "Grieks", "Greek"),
    ("he", "Hebreeuws", "Hebrew"),
    ("hi", "Hindi", "Hindi"),
    ("hu", "Hongaars", "Hungarian"),
    ("ga", "Iers", "Irish"),
    ("id", "Indonesisch", "Indonesian"),
    ("it", "Italiaans", "Italian"),
    ("ja", "Japans", "Japanese"),
    ("ko", "Koreaans", "Korean"),
    ("lv", "Lets", "Latvian"),
    ("lt", "Litouws", "Lithuanian"),
    ("nb", "Noors", "Norwegian"),
    ("uk", "Oekraiens", "Ukrainian"),
    ("fa", "Perzisch", "Persian"),
    ("pl", "Pools", "Polish"),
    ("pt", "Portugees", "Portuguese"),
    ("ro", "Roemeens", "Romanian"),
    ("ru", "Russisch", "Russian"),
    ("sk", "Slowaaks", "Slovak"),
    ("sl", "Sloveens", "Slovenian"),
    ("es", "Spaans", "Spanish"),
    ("cs", "Tsjechisch", "Czech"),
    ("tl", "Tagalog", "Tagalog"),
    ("th", "Thais", "Thai"),
    ("tr", "Turks", "Turkish"),
    ("ur", "Urdu", "Urdu"),
    ("sv", "Zweeds", "Swedish"),
]

_NL = {c: nl for c, nl, en in LANGUAGES}
_EN = {c: en for c, nl, en in LANGUAGES}


def lang_name(code, ui="nl"):
    if code in ("auto", ""):
        return "Automatisch" if ui == "nl" else "Automatic"
    return (_NL if ui == "nl" else _EN).get(code, code)


def lang_name_en(code):
    return _EN.get(code, code)


# ---------------------------------------------------------------------------
# Pad-helpers (frozen-bewust)
# ---------------------------------------------------------------------------
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    d = os.path.join(app_dir(), "DraveTranslate-data")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


# ---------------------------------------------------------------------------
# Taaldetectie
# ---------------------------------------------------------------------------
def detect_lang(text):
    """Raad de brontaal (ISO-code) of geef None bij twijfel/ontbreken."""
    text = (text or "").strip()
    if len(text) < 2:
        return None
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        code = detect(text)
        if code:
            code = code.lower()
            if code.startswith("zh"):
                code = "zh"
            return code.split("-")[0]
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 1) Argos Translate (offline)
# ---------------------------------------------------------------------------
class Argos:
    def available(self):
        try:
            import argostranslate.translate  # noqa: F401
            return True
        except Exception:
            return False

    def _installed(self):
        import argostranslate.translate as tr
        return {lg.code: lg for lg in tr.get_installed_languages()}

    def can_translate(self, frm, to):
        """True als een (eventueel via-Engels) vertaling al lokaal kan."""
        try:
            langs = self._installed()
            if frm in langs and to in langs:
                return langs[frm].get_translation(langs[to]) is not None
        except Exception:
            pass
        return False

    def _install_one(self, avail, frm, to):
        import argostranslate.package as pkg
        for p in avail:
            if p.from_code == frm and p.to_code == to:
                pkg.install_from_path(p.download())
                return True
        return False

    def ensure(self, frm, to, on_status=None):
        """Zorg dat het talenpaar geinstalleerd is (downloadt eenmalig)."""
        if frm == to:
            return True
        if self.can_translate(frm, to):
            return True
        try:
            import argostranslate.package as pkg
            if on_status:
                on_status("downloading")
            pkg.update_package_index()
            avail = pkg.get_available_packages()
            if not self._install_one(avail, frm, to):
                # geen direct paar -> via Engels als pivot
                if frm != "en":
                    self._install_one(avail, frm, "en")
                if to != "en":
                    self._install_one(avail, "en", to)
        except Exception:
            return False
        return self.can_translate(frm, to)

    def translate(self, text, frm, to):
        import argostranslate.translate as tr
        return tr.translate(text, frm, to)


# ---------------------------------------------------------------------------
# 2) Lokaal taalmodel (terugval) - zelfde soort GGUF als DraveAI
# ---------------------------------------------------------------------------
class LocalLLM:
    # klein model voor de terugval; wordt zo nodig zelf gedownload
    REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

    def __init__(self, model_path=None):
        self.model_path = model_path
        self.llm = None

    @staticmethod
    def _is_chat_gguf(name):
        n = name.lower()
        # mmproj/clip/projector zijn GEEN chatmodellen -> overslaan
        return n.endswith(".gguf") and not any(
            k in n for k in ("mmproj", "clip", "projector", "vision"))

    def find_model(self):
        cands = []
        if self.model_path:
            cands.append(self.model_path)
        cands.append(os.path.join(data_dir(), "model"))
        # naast een eventuele DraveAI/DraveMind-installatie
        cands.append(os.path.join(app_dir(), "..", "DraveMind", "DraveMind-data", "model"))
        cands.append(os.path.join(app_dir(), "..", "DraveAI", "DraveMind-data", "model"))
        for c in cands:
            if not c:
                continue
            if os.path.isfile(c) and self._is_chat_gguf(c):
                return c
            if os.path.isdir(c):
                try:
                    ggufs = [f for f in sorted(os.listdir(c)) if self._is_chat_gguf(f)]
                    # liefst een 'instruct'-model
                    instr = [f for f in ggufs if "instruct" in f.lower()]
                    pick = (instr or ggufs)
                    if pick:
                        return os.path.join(c, pick[0])
                except Exception:
                    pass
        return None

    def have_llama(self):
        try:
            import llama_cpp  # noqa: F401
            return True
        except Exception:
            return False

    def available(self):
        """Terugval mogelijk? (llama-cpp aanwezig; model kan zo nodig gedownload)."""
        return self.have_llama()

    def _download(self, on_status=None):
        """Haal het kleine terugval-model op naar de eigen data-map (eenmalig)."""
        try:
            from huggingface_hub import hf_hub_download
        except Exception:
            return None
        try:
            if on_status:
                on_status("model_download")
            target = os.path.join(data_dir(), "model")
            os.makedirs(target, exist_ok=True)
            return hf_hub_download(repo_id=self.REPO, filename=self.FILE,
                                   local_dir=target)
        except Exception:
            return None

    def ensure(self, on_status=None, allow_download=False):
        if self.llm is not None:
            return True
        if not self.have_llama():
            return False
        mp = self.find_model()
        if not mp:
            if not allow_download:
                raise ModelNeeded()          # eerst vragen, niet stiekem downloaden
            mp = self._download(on_status)
        if not mp:
            return False
        from llama_cpp import Llama
        self.llm = Llama(model_path=mp, n_ctx=2048, verbose=False)
        return True

    def translate(self, text, frm, to, on_status=None, allow_download=False):
        if not self.ensure(on_status, allow_download):
            raise RuntimeError("geen lokaal model")
        sysmsg = ("You are a professional translator. Translate the user's text to "
                  "%s. Reply with ONLY the translation - no quotes, no notes, keep "
                  "the meaning and tone." % lang_name_en(to))
        out = self.llm.create_chat_completion(
            messages=[{"role": "system", "content": sysmsg},
                      {"role": "user", "content": text}],
            temperature=0.2, max_tokens=2048)
        return (out["choices"][0]["message"]["content"] or "").strip()


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------
class Translator:
    def __init__(self, cfg=None):
        cfg = cfg or {}
        self.argos = Argos()
        self.llm = LocalLLM(cfg.get("llm_model_path") or None)

    def status(self):
        return {"argos": self.argos.available(), "llm": self.llm.available()}

    def translate(self, text, frm, to, on_status=None, allow_download=False):
        """Geef (vertaling, motor, gebruikte_brontaal) terug. 'motor' is
        'argos' / 'llm' / 'gelijk'. Gooit ModelNeeded als er (met toestemming)
        eerst een lokaal model gedownload moet worden; RuntimeError als niets lukt."""
        text = (text or "").strip()
        if not text:
            return "", "", frm
        if frm in ("auto", ""):
            frm = detect_lang(text) or "en"
        if frm == to:
            return text, "gelijk", frm
        # 1) Argos
        if self.argos.available():
            try:
                if self.argos.ensure(frm, to, on_status):
                    res = self.argos.translate(text, frm, to)
                    if res and res.strip():
                        return res.strip(), "argos", frm
            except Exception:
                pass
        # 2) lokaal model (terugval). Ontbreekt het model, dan gooit dit ModelNeeded
        #    (de app vraagt dan eerst toestemming voor de download).
        if self.llm.available():
            if on_status:
                on_status("llm")
            return (self.llm.translate(text, frm, to, on_status=on_status,
                                       allow_download=allow_download), "llm", frm)
        raise RuntimeError(
            "Deze vertaling lukte niet. Mogelijke redenen:\n"
            "1) Eerste keer een Argos-talenpaar: daarvoor is eenmalig internet "
            "nodig om het te downloaden. Probeer het met internet opnieuw.\n"
            "2) Deze taal (bijv. Papiaments) zit NIET in Argos. Zet dan de offline "
            "terugval aan: dubbelklik 'Installeer-terugval-model.bat' (eenmalig). "
            "Daarna werkt ook deze taal, via een lokaal model.")
