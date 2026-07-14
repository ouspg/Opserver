"""Tulostaa raportin LLM-kehotteet tutkimukselle ilman LLM-kutsua.

Käyttö:
    ./kehotteet <slug>
    ./kehotteet esr_kyber | less
"""
import sys
import os

# Lisää projektin juuri Python-polkuun
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

if len(sys.argv) != 2:
    print(f"Käyttö: ./kehotteet <tutkimuksen-slug>", file=sys.stderr)
    sys.exit(1)

slug = sys.argv[1]

from tietokanta import mallit
from raportti import llmraportti

tutkimus = mallit.hae_tutkimus_slugilla(slug)
if tutkimus is None:
    print(f"Virhe: tutkimusta '{slug}' ei löydy tietokannasta.", file=sys.stderr)
    sys.exit(1)

tid = tutkimus["TID"]
tilastot = mallit.hae_tilastot_yliopistoittain(tid)
kysymykset = mallit.hae_kysymykset(tid)
jarjestelma = llmraportti._lue_jarjestelmakehote()

viestirakentajat = {
    "johdanto":   lambda: llmraportti._rakenna_johdanto_viesti(tutkimus, tilastot),
    "kurssit":    lambda: llmraportti._rakenna_kurssit_viesti(tutkimus, tilastot),
    "arvioinnit": lambda: llmraportti._rakenna_arvioinnit_viesti(tutkimus, kysymykset, tilastot),
}

viiva = "=" * 72

print(f"\n{viiva}")
print(f"  JÄRJESTELMÄKEHOTE (kaikille osioille)")
print(viiva)
print(jarjestelma)

for avain, rakentaja in viestirakentajat.items():
    print(f"\n{viiva}")
    print(f"  OSIO: {avain.upper()}")
    print(viiva)
    print(rakentaja())

print(f"\n{viiva}\n")
