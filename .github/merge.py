#!/usr/bin/env python3
"""Der einzige Schritt, der ins Repo schreibt: nimmt die fertigen Abschnitte aller Jobs und laedt sie in Stapeln hoch.
Aufruf: merge.py STIMME ORDNER_MIT_ABSCHNITTEN [Ergebnis des Herunterladens]"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

STAPEL = 150 * 1024 * 1024   # Bytes je Hochladen


def git(*a, check=True):
    return subprocess.run(["git", *a], check=check)


def pruefen(ordner):
    """Ein Abschnitt zaehlt nur, wenn zu jedem Eintrag in m.json die Tondatei da ist und umgekehrt."""
    try:
        with open(os.path.join(ordner, "m.json"), encoding="utf-8") as h:
            m = json.load(h)
    except Exception:
        return 0
    dateien = sorted(n for n in os.listdir(ordner) if n != "m.json")
    soll = sorted("%d.m4a" % i for i in range(len(m)))
    if not m or dateien != soll or sorted(m, key=int) != [str(i) for i in range(len(m))]:
        return 0
    gross = 0
    for n in dateien:
        g = os.path.getsize(os.path.join(ordner, n))
        if g < 1000:
            return 0
        gross += g
    return gross


def hochladen(liste, stapel, stimme):
    with open("liste.json", "w", encoding="utf-8") as h:
        json.dump(liste, h, separators=(",", ":"), sort_keys=True)
    git("add", "--", "liste.json", *stapel)
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        return
    git("commit", "-q", "-m", "Ton: %d Abschnitte, %s bis %s, Stimme %s" % (len(stapel), stapel[0], stapel[-1], stimme), "-m", "Co-Authored-By: Claude <noreply@anthropic.com>")
    for versuch in range(5):
        if git("push", "-q", "origin", "HEAD:main", check=False).returncode == 0:
            return
        time.sleep(10 * (versuch + 1))
        git("pull", "--rebase", "-q", "origin", "main", check=False)
    sys.exit("FEHLER Hochladen ging fuenfmal nicht")


def main():
    stimme, neu = sys.argv[1], sys.argv[2]
    geladen = sys.argv[3] if len(sys.argv) > 3 else "success"
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    liste = {}
    if os.path.isfile("liste.json"):
        with open("liste.json", encoding="utf-8") as h:
            liste = json.load(h)
    da = sorted(d for d in os.listdir(neu) if re.fullmatch(r"\d\d-\d\d", d)) if os.path.isdir(neu) else []
    kaputt, stapel, menge, gesamt = [], [], 0, 0
    for f in da:
        g = pruefen(os.path.join(neu, f))
        if not g:
            kaputt.append(f)
            continue
        shutil.rmtree(f, ignore_errors=True)
        shutil.move(os.path.join(neu, f), f)
        liste[f] = stimme
        stapel.append(f)
        menge += g
        gesamt += g
        if menge >= STAPEL:
            hochladen(liste, stapel, stimme)
            stapel, menge = [], 0
    if stapel:
        hochladen(liste, stapel, stimme)
    print("MERGE %d Abschnitte neu, %d Bytes, im Repo jetzt %d Abschnitte" % (len(da) - len(kaputt), gesamt, len(liste)), flush=True)
    if kaputt:
        print("FEHLER unvollstaendig:", ",".join(kaputt), flush=True)
    if geladen != "success" and da:
        print("FEHLER Herunterladen der Ergebnisse war unvollstaendig", flush=True)
    sys.exit(1 if kaputt or (geladen != "success" and da) else 0)


if __name__ == "__main__":
    main()
