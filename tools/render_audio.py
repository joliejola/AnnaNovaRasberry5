#!/usr/bin/env python3
"""Render alle opgenomen zinnen uit content/inhoud.json naar audio/<id>.wav.

TTS: Piper nl_BE-nathalie-medium. Bron 2 noemt Voxtral TTS maar die bestaat
niet — Piper is Jolanda's gekozen stem (confirmed in oude .env op Pi).

Hash-check: audio/<id>.wav.sha256 bewaart sha256 van de tekst. Alleen opnieuw
renderen als de tekst gewijzigd is, of met --force.

Draai:
  python3 tools/render_audio.py                 # vergelijk+render wat nodig is
  python3 tools/render_audio.py --dry           # alleen tonen wat zou gebeuren
  python3 tools/render_audio.py --force         # alles opnieuw
  python3 tools/render_audio.py --voice <path>  # andere stem-ONNX

Env:
  PIPER_BIN       binary; default `piper` uit PATH of venv
  PIPER_VOICE     pad naar .onnx; default assets/voices/nl_BE-nathalie-medium.onnx
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INHOUD = ROOT / "content" / "inhoud.json"
AUDIO = ROOT / "audio"
DEFAULT_VOICE = ROOT / "assets" / "voices" / "nl_BE-nathalie-medium.onnx"

VOICE = Path(os.environ["PIPER_VOICE"]) if os.environ.get("PIPER_VOICE") else DEFAULT_VOICE


def _find_piper_bin() -> str | None:
    """Zoek piper in: env PIPER_BIN, venv script dir, PATH."""
    env_bin = os.environ.get("PIPER_BIN")
    if env_bin and Path(env_bin).exists():
        return env_bin
    # venv (relatief)
    venv_bin = ROOT / ".venv" / "bin" / "piper"
    if venv_bin.exists():
        return str(venv_bin)
    # PATH
    import shutil
    found = shutil.which("piper")
    return found


def _collect_items(inhoud: dict) -> list[tuple[str, str, str]]:
    """Trek alle (id, tekst, locatie) tuples uit inhoud.json.

    Locatie is alleen info — bijv. 'reeks.v1', 'reeks.v1.reacties.ja'.
    """
    items: list[tuple[str, str, str]] = []

    def add(idval, tekst, loc):
        idval = str(idval).strip()
        tekst = str(tekst).strip()
        if idval and tekst:
            items.append((idval, tekst, loc))

    for i, o in enumerate(inhoud.get("openingen", [])):
        add(o["id"], o["tekst"], f"openingen[{i}]")

    for i, l in enumerate(inhoud.get("lokzinnen", [])):
        add(l["id"], l["tekst"], f"lokzinnen[{i}]")

    for i, v in enumerate(inhoud.get("reeks", [])):
        add(v["id"], v["tekst"], f"reeks[{i}]")
        for key, r in (v.get("reacties") or {}).items():
            if isinstance(r, dict) and r.get("id") and r.get("tekst"):
                add(r["id"], r["tekst"], f"reeks[{i}].reacties.{key}")

    for i, w in enumerate(inhoud.get("wachtzinnen", [])):
        add(w["id"], w["tekst"], f"wachtzinnen[{i}]")

    for key, s in (inhoud.get("situaties") or {}).items():
        if isinstance(s, dict):
            add(s["id"], s["tekst"], f"situaties.{key}")

    af = inhoud.get("afsluiting")
    if isinstance(af, dict):
        add(af["id"], af["tekst"], "afsluiting")

    nn = inhoud.get("na_nee")
    if isinstance(nn, dict):
        add(nn["id"], nn["tekst"], "na_nee")

    for i, s in enumerate(inhoud.get("slotzinnen", [])):
        add(s["id"], s["tekst"], f"slotzinnen[{i}]")

    return items


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _needs_render(wav: Path, hash_file: Path, text: str) -> tuple[bool, str]:
    if not wav.exists():
        return True, "new"
    if not hash_file.exists():
        return True, "no-hash-file"
    try:
        if hash_file.read_text().strip() == _hash(text):
            return False, "unchanged"
    except Exception:
        return True, "hash-read-fail"
    return True, "changed"


def _render_one(piper: str, voice: Path, text: str, out: Path) -> bool:
    try:
        subprocess.run(
            [piper, "-m", str(voice), "-f", str(out)],
            input=text.encode("utf-8"),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        return True
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"[fail] piper: {e.stderr.decode(errors='ignore')}\n")
        return False
    except subprocess.TimeoutExpired:
        sys.stderr.write("[fail] piper timeout\n")
        return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry", action="store_true", help="niet renderen, alleen tonen")
    p.add_argument("--force", action="store_true", help="herrender ook ongewijzigde zinnen")
    p.add_argument("--voice", type=Path, default=VOICE, help="pad naar Piper .onnx")
    p.add_argument("--only", help="alleen dit id renderen")
    args = p.parse_args()

    inhoud = json.loads(INHOUD.read_text(encoding="utf-8"))
    items = _collect_items(inhoud)
    if args.only:
        items = [t for t in items if t[0] == args.only]
        if not items:
            print(f"[miss] id {args.only!r} niet gevonden")
            return 1

    AUDIO.mkdir(exist_ok=True)

    if args.dry:
        print(f"[DRY] {len(items)} items in inhoud.json\n")
        for idv, tekst, loc in items:
            wav = AUDIO / f"{idv}.wav"
            hashf = AUDIO / f"{idv}.wav.sha256"
            render, reden = _needs_render(wav, hashf, tekst)
            tag = "render" if (render or args.force) else "skip"
            reden_str = reden if (render or args.force) else "unchanged"
            print(f"  [{tag:6}] {idv:12} ({reden_str:10}) {loc:30} {tekst[:50]!r}")
        return 0

    piper = _find_piper_bin()
    if not piper:
        sys.stderr.write("[err] piper binary niet gevonden. "
                         "pip install piper-tts, of zet PIPER_BIN\n")
        return 2
    if not args.voice.exists():
        sys.stderr.write(f"[err] voice niet gevonden: {args.voice}\n"
                         f"      Download van https://huggingface.co/rhasspy/piper-voices\n")
        return 3

    print(f"[piper] {piper}\n[voice] {args.voice}\n[audio] {AUDIO}\n")

    nieuw = veranderd = ok = fout = skip = 0
    for idv, tekst, loc in items:
        wav = AUDIO / f"{idv}.wav"
        hashf = AUDIO / f"{idv}.wav.sha256"
        render, reden = _needs_render(wav, hashf, tekst)
        if not render and not args.force:
            skip += 1
            continue
        success = _render_one(piper, args.voice, tekst, wav)
        if success:
            hashf.write_text(_hash(tekst))
            if reden == "new":
                nieuw += 1
            elif reden == "changed":
                veranderd += 1
            ok += 1
            size = wav.stat().st_size
            print(f"  [ok]   {idv:12} ({reden:10}) {size:>6}B  {tekst[:50]!r}")
        else:
            fout += 1

    print(f"\n{ok} gerenderd ({nieuw} nieuw, {veranderd} veranderd), {skip} ongewijzigd, {fout} fout")
    return 0 if fout == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
