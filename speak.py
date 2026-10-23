# -*- coding: utf-8 -*-
"""speak.py - voorleesstem voor DraveTranslate via neuvoice (Dravenlock-standaard).

Zelfde neuvoice-stem als DraveAI/DraveKITT/DraveGames, maar afgespeeld via
sounddevice (deze app gebruikt geen pygame). De stem is instelbaar (keuze uit
alle neuvoice-stemmen) met snelheid en volume. Faalt er iets, dan blijft de app
gewoon werken (geen geluid).
"""
from __future__ import annotations

import threading

try:
    import numpy as np
except Exception:
    np = None


try:
    from uitspraak import uitspraak as _uitspraak
except Exception:
    try:
        from .uitspraak import uitspraak as _uitspraak
    except Exception:  # zonder uitspraak.py gewoon de tekst zelf
        def _uitspraak(t, taal="nl"):
            return t


class Voice:
    def __init__(self, voice="", speed=1.0, volume=1.0):
        self.voice = voice
        self.speed = speed
        self.volume = volume
        self._tts = None
        self._style = None
        self._sr = 24000
        self.voices = []
        self._ready = False
        self._failed = False
        self._lock = threading.Lock()

    def available(self):
        """Kan er gesproken worden? (neuvoice + numpy + sounddevice aanwezig)."""
        if np is None:
            return False
        try:
            import neuvoice  # noqa: F401
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    def _ensure(self):
        if self._ready or self._failed:
            return
        with self._lock:
            if self._ready or self._failed:
                return
            try:
                from neuvoice import TTS
                tts = TTS(auto_download=True)
                names = list(getattr(tts, "voice_style_names", []) or [])
                self.voices = names
                want = (self.voice or "").strip().lower()
                pick = None
                for n in names:
                    if n.strip().lower() == want:
                        pick = n
                        break
                if pick is None and "Leon" in names:
                    pick = "Leon"
                if pick is None and names:
                    pick = names[0]
                if pick:
                    self.voice = pick
                self._style = tts.get_voice_style(pick) if pick else None
                self._sr = int(getattr(tts, "sample_rate", 24000) or 24000)
                self._tts = tts
                self._ready = True
            except Exception:
                self._failed = True

    def list_voices(self):
        self._ensure()
        return list(self.voices)

    def set_voice(self, voice):
        if not voice or voice == self.voice:
            return
        self.voice = voice
        if self._tts is not None:
            try:
                self._style = self._tts.get_voice_style(voice)
                return
            except Exception:
                pass
        self._ready = False
        self._failed = False
        self._style = None
        self._tts = None

    def speak(self, text, lang="nl"):
        if not text or np is None:
            return
        threading.Thread(target=self._speak_blocking, args=(text, lang),
                         daemon=True).start()

    def _speak_blocking(self, text, lang):
        try:
            self._ensure()
            if not self._ready:
                return
            spd = float(self.speed) if 0.5 <= self.speed <= 2.0 else 1.0
            with self._lock:
                wav, dur = self._tts.synthesize(
                    _uitspraak(text, lang or "nl"), voice_style=self._style, total_steps=10,
                    speed=spd, lang=(lang or "nl"))
            data = np.asarray(wav, dtype=np.float32).flatten()
            if len(data) < 2:
                return
            vol = self.volume if 0.0 <= self.volume <= 1.0 else 1.0
            data = data * float(vol)
            import sounddevice as sd
            sd.stop()
            sd.play(data, self._sr)
            sd.wait()
        except Exception:
            pass
