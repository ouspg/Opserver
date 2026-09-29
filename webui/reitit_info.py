"""Opserver-infomodaalin data: infosivu (Opserver.md) ja ajossa oleva versio."""
import functools
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter

reititin = APIRouter()

_JUURI = Path(__file__).resolve().parent.parent
_INFOSIVU = _JUURI / "Opserver.md"


@functools.cache
def _versio() -> tuple[str, str]:
    """(commit, päivä): Docker-kuvaan käännetty (OPSERVER_VERSIO, ./asenna) tai
    kehityksessä työkopion git; muuten ("tuntematon", "")."""
    arvo = os.environ.get("OPSERVER_VERSIO", "").strip()
    if not arvo:
        try:
            arvo = subprocess.run(["git", "log", "-1", "--format=%h %cs"], cwd=_JUURI,
                                  capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        except Exception:
            arvo = ""
    versio, _, paiva = arvo.partition(" ")
    return (versio, paiva) if versio else ("tuntematon", "")


@reititin.get("/api/info")
def api_info() -> dict:
    versio, paiva = _versio()
    return {"teksti": _INFOSIVU.read_text(encoding="utf-8"), "versio": versio, "paiva": paiva}
