#!/usr/bin/env python3
"""Fertiger Ton fuer Speak auf dlichters.com/ecom: je Post eine Datei, dazu die Startzeit jeder Slide.
Aufruf: ton.py STIMME "21-08,21-25" AUSGABE [liste.json des Repos]
Ein Abschnitt erscheint in AUSGABE erst, wenn alle seine Posts fertig sind. Was im Repo schon mit dieser Stimme liegt, wird uebersprungen."""
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

BASIS = "https://dlichters.com/ecom/feed/"
TEMPO = 1.3
PAUSE = 0.25
FRIST = float(os.environ.get("FRIST_MIN", "320")) * 60   # danach beginnt kein neuer Abschnitt mehr, ein Job darf 6 h laufen


def holen(f):
    for versuch in range(5):
        try:
            with urllib.request.urlopen(BASIS + "d/" + f + ".json", timeout=60) as r:
                return json.load(r)
        except Exception:
            if versuch == 4:
                raise
            time.sleep(5 * (versuch + 1))


def vorlese(s):
    """Genau derselbe Text wie vorlese() in der Seite."""
    if s.get("k") == "t":
        return ". ".join(x for x in (s.get("t"), s.get("s")) if x)
    t = ((s["h"] + ". ") if s.get("h") else "") + s["t"].replace("\n", ". ")
    return t.replace("**", "")


def abschnitt(k, f, stimme, aus):
    posts = holen(f)["p"]
    halb = os.path.join(aus, ".halb-" + f)
    shutil.rmtree(halb, ignore_errors=True)
    os.makedirs(halb)
    m, ton, gross, zeichen = {}, 0.0, 0, 0
    for n, slides in enumerate(posts):
        stuecke, marken, jetzt, sr = [], [], 0.0, 24000
        for s in slides:
            marken.append(round(jetzt, 2))
            text = vorlese(s)
            zeichen += len(text)
            a, sr = k.create(text, voice=stimme, speed=TEMPO, lang="en-gb")
            stille = np.zeros(int(PAUSE * sr), dtype=a.dtype)
            stuecke += [a, stille]
            jetzt += len(a) / sr + PAUSE
        ziel = os.path.join(halb, "%d.m4a" % n)
        with tempfile.NamedTemporaryFile(suffix=".wav") as w:
            sf.write(w.name, np.concatenate(stuecke), sr)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", w.name, "-ac", "1", "-c:a", "aac", "-b:a", "40k", "-movflags", "+faststart", ziel], check=True)
        m[str(n)] = marken
        ton += jetzt
        gross += os.path.getsize(ziel)
    with open(os.path.join(halb, "m.json"), "w", encoding="utf-8") as h:
        json.dump(m, h, separators=(",", ":"))
    fertig = os.path.join(aus, f)
    shutil.rmtree(fertig, ignore_errors=True)
    os.rename(halb, fertig)
    return len(posts), ton, gross, zeichen


def main():
    stimme, teil, aus = sys.argv[1], sys.argv[2], sys.argv[3]
    vorhanden = {}
    if len(sys.argv) > 4 and os.path.isfile(sys.argv[4]):
        with open(sys.argv[4], encoding="utf-8") as h:
            vorhanden = json.load(h)
    os.makedirs(aus, exist_ok=True)
    print("kokoro-onnx", importlib.metadata.version("kokoro-onnx"), "| Kerne", os.cpu_count(), flush=True)
    k = Kokoro("kokoro.onnx", "voices.bin")
    if stimme not in k.get_voices():
        sys.exit("FEHLER Stimme %r gibt es nicht" % stimme)
    start = time.time()
    fehler, offen, g_ton, g_zeit, g_gross, g_zeichen, g_posts = [], [], 0.0, 0.0, 0, 0, 0
    for f in [x.strip() for x in teil.split(",") if x.strip()]:
        if not re.fullmatch(r"\d\d-\d\d", f):
            fehler.append(f)
            print("FEHLER kein Abschnitt:", repr(f), flush=True)
            continue
        if vorhanden.get(f) == stimme:
            print(f, "schon da mit", stimme, flush=True)
            continue
        if time.time() - start > FRIST:
            offen.append(f)
            continue
        t0 = time.time()
        try:
            posts, ton, gross, zeichen = abschnitt(k, f, stimme, aus)
        except Exception:
            traceback.print_exc()
            fehler.append(f)
            print("FEHLER", f, flush=True)
            continue
        z = time.time() - t0
        g_ton += ton
        g_zeit += z
        g_gross += gross
        g_zeichen += zeichen
        g_posts += posts
        print("%s %s: %d Posts, %d Zeichen, %.0f s Ton in %.0f s, %d KB" % (f, stimme, posts, zeichen, ton, z, gross // 1024), flush=True)
    if g_zeit:
        print("GESAMT %d Posts, %d Zeichen, %.0f s Ton in %.0f s, %.2f-fach, %d Bytes, %.1f Bytes je Zeichen, %.1f Zeichen je s" % (g_posts, g_zeichen, g_ton, g_zeit, g_ton / g_zeit, g_gross, g_gross / max(1, g_zeichen), g_zeichen / g_zeit), flush=True)
    if offen:
        print("OFFEN wegen Frist:", ",".join(offen), flush=True)
    if fehler:
        print("FEHLER bei:", ",".join(fehler), flush=True)
    sys.exit(1 if fehler or offen else 0)


if __name__ == "__main__":
    main()
