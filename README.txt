DraveTranslate - offline vertaler (Dravenlock)
==============================================

Wat is het?
-----------
Een vertaalapp die op je eigen pc draait. Je typt of plakt tekst, kiest de
bron- en doeltaal en klikt Vertaal. Werkt offline.

Twee vertaalmotoren (allebei in de app/EXE ingebakken)
------------------------------------------------------
1) Argos Translate (primair, standaard): echte offline vertaalmodellen. De
   EERSTE keer dat je een talenpaar gebruikt, wordt daarvoor eenmalig een klein
   modelletje gedownload (internet nodig). Daarna werkt dat paar zonder internet.
2) Lokaal taalmodel (terugval): sommige talen (bijv. Papiaments) zitten NIET in
   Argos. Kies je zo'n taal, dan VRAAGT DraveTranslate eerst of je het losse
   onderdeel mag downloaden: een klein lokaal model van ~1 GB (eenmalig, internet
   nodig) naar DraveTranslate-data\model. Pas na jouw 'ja' wordt het opgehaald;
   niets gebeurt stiekem. Je kunt in Instellingen ook zelf een GGUF-model
   aanwijzen. Let op: de kwaliteit van zulke talen is wisselend; Argos-talen zijn
   het beste. Voor Papiaments staat er ook een knop naar het Palabricks-
   woordenboek (betrouwbaar voor losse woorden).

De voorleesstem gebruikt neuvoice (dezelfde Dravenlock-stem als DraveAI/KITT)
en is instelbaar bij Instellingen (stem + snelheid). De stem wordt de eerste
keer gedownload.

Alles zit in de EXE: PyQt6, Argos, langdetect, neuvoice (stem) en llama-cpp
worden meegebakken. Alleen de modellen (Argos-talenpaar, de stem en het
terugval-model) worden zo nodig gedownload, omdat ze te groot zijn om mee te
leveren.

Bediening
---------
- Linkervak: jouw tekst. Rechtervak: de vertaling.
- Van/Naar: kies de talen (of laat 'Automatisch' staan voor de brontaal).
- Vertaal (of Ctrl+Enter), Wissel (talen + teksten omdraaien), Kopieer, Wis.
- Spreek uit: leest de vertaling voor (als er een stem op je pc staat).
- F1 = Snelgids. (hart) Donatie linksboven (paypal.me/roger076).

Starten (Windows)
-----------------
- Dubbelklik run.bat (installeert eenmalig de omgeving en start de app).

Een EXE maken
-------------
- Dubbelklik bouw-exe.bat -> dist\DraveTranslate\DraveTranslate.exe (map-versie;
  houd de hele map bij elkaar). herstel.bat ruimt .venv/build/dist op.

Instellingen (dravetranslate_config.json)
-----------------------------------------
  "lang"            : interface-taal ("" = automatisch, "nl", "en")
  "from" / "to"     : laatst gekozen talen
  "llm_model_path"  : pad naar een GGUF-model voor de offline terugval

Werkt iets niet?
----------------
- "Geen vertaler beschikbaar": de eerste Argos-download heeft internet nodig,
  of plaats een GGUF-model voor de terugval.
- Bij een crash: zie dravetranslate-fout.txt naast het programma.
