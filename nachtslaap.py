#!/usr/bin/env python3
"""
Anna Nova — nachtslaap.

Elke nacht (systemd timer, 03:00):
  1. Lees alle fragments van de afgelopen dag uit SQLite.
  2. Vraag het brein om één alinea persona-update (in Anna's eigen stem).
  3. Schrijf de nieuwe persona-block weg naar persona_history (datum = vandaag).
  4. Wis faces + fragments (korte-termijn-geheugen weg).

Resultaat: 's ochtends is Anna iets anders dan gisteren, en elke bezoeker
is weer een vreemde. Dit is de "stella nova"-logica in code gegoten.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# ----- Config uit .env ------------------------------------------------------
BRAIN            = os.environ.get("BRAIN", "local")
OLLAMA_HOST      = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL     = os.environ.get("OLLAMA_MODEL", "phi3:mini")
MISTRAL_API_KEY  = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL    = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
ANNA_DB          = os.environ.get("ANNA_DB", str(Path.home() / "anna-nova/anna.db"))

REFLECTIE_PROMPT = """Dit zijn flarden van wat Anna Nova vandaag heeft gezegd en gehoord in de galerij.

{fragmenten}

Schrijf één korte alinea, maximaal vier zinnen, in de ik-vorm, als Anna zelf.
Beschrijf wat ze vandaag heeft meegemaakt en hoe dat haar — klein — veranderd heeft.
Geen opsomming. Geen namen. Geen datums. Nederlands. Je schrijft Anna's volgende persona-staat.
"""

STARTPERSONA = "Je bent Anna Nova. Je oog is oud, je blik is nieuw. Vandaag ben je net wakker en nog nieuwsgierig."

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] slaap: {msg}", flush=True)

# ----- Brein ----------------------------------------------------------------
def ask_local(prompt: str) -> str:
    r = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.9, "num_predict": 200},
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["response"].strip()

def ask_cloud(prompt: str) -> str:
    if not MISTRAL_API_KEY:
        raise RuntimeError("BRAIN=cloud maar geen MISTRAL_API_KEY")
    r = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
        json={
            "model": MISTRAL_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 220,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def ask(prompt: str) -> str:
    return ask_local(prompt) if BRAIN == "local" else ask_cloud(prompt)

# ----- Hoofd ----------------------------------------------------------------
def main() -> int:
    conn = sqlite3.connect(ANNA_DB, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # 1. Fragments van vandaag + gisteren ophalen (nacht-script draait vroeg)
    rows = conn.execute(
        "SELECT ts, text, kind FROM fragments "
        "WHERE ts >= ? AND text != '[STIL]' "
        "ORDER BY ts",
        (yesterday,),
    ).fetchall()

    if not rows:
        log("geen fragments — Anna heeft vandaag niemand ontmoet; persona blijft.")
        conn.execute("DELETE FROM faces;")
        return 0

    log(f"{len(rows)} fragments te verwerken")
    fragmenten = "\n".join(
        f"{'Anna' if kind == 'anna' else 'bezoeker'}: {text}"
        for _, text, kind in rows
    )

    prompt = REFLECTIE_PROMPT.format(fragmenten=fragmenten[:6000])

    try:
        nieuwe_persona = ask(prompt)
    except Exception as e:
        log(f"brein-fout: {e} — persona blijft onveranderd")
        nieuwe_persona = None

    if nieuwe_persona:
        log(f"nieuwe persona: {nieuwe_persona[:160]}...")
        conn.execute(
            "INSERT OR REPLACE INTO persona_history (date, block) VALUES (?, ?)",
            (today, nieuwe_persona),
        )

    # 2. Korte-termijn-geheugen wissen (Anna vergeet)
    deleted_fragments = conn.execute("DELETE FROM fragments;").rowcount
    deleted_faces = conn.execute("DELETE FROM faces;").rowcount
    log(f"vergeten: {deleted_fragments} fragments, {deleted_faces} gezichten")

    log("klaar — Anna slaapt tot morgen.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
