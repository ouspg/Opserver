"""Raportin rakenteelliset luvut per-yliopisto-tilastoista (hae_tilastot_yliopistoittain):
kurssien suppilo ja HITL-mittarit sekä niiden tekstimuodot raporttikehotteisiin.
Auktoritatiivisia lukuja — LLM vain kirjoittaa niistä proosaa."""
from tietokanta import mallit

# Raporttiteksteissä käytetyt nimet (samat kaikissa osioissa, ettei luvut sekoitu).
NIMI_MUKANA = "Lopullinen mukana-lista HITL:n jälkeen"
NIMI_LLM_LLE = "LLM:lle meni (meta-suodatuksen läpäisseet)"
NIMI_META = "Meta-suodatus (sääntöpohjainen, ei LLM) hylkäsi"


def _osuus(osa: int, koko: int) -> float:
    return 100 * osa / koko if koko else 0.0


def suppilo(tilastot: list[dict]) -> dict:
    """Koko tutkimuksen suppilo yliopistorivien summana."""
    summa = lambda avain: sum(r.get(avain, 0) for r in tilastot)
    return {
        "kursseja": summa("KurssiYhteensa"), "odottaa_meta": summa("OdottaaMeta"),
        "meta_hylkaama": summa("MetaHylkaama"), "llm_lle": summa("LLMlle"),
        "odottaa_llm": summa("OdottaaLLM"), "llm_kasitelty": summa("LLMKasitelty"),
        "llm_hylatty": summa("LLMHylatty"), "mukana": summa("Mukana"),
        "hylatty": summa("Hylatty"),
    }


def suppilo_teksti(s: dict) -> str:
    """Suppilo kehotteeseen: jokainen luku nimettynä yksiselitteisesti."""
    return (
        f"- Kursseja tutkimuksen rajauksessa (lukuvuosi + valitut korkeakoulut): {s['kursseja']}\n"
        f"- Odottaa vielä meta-suodatusta: {s['odottaa_meta']}\n"
        f"- {NIMI_META}: {s['meta_hylkaama']}\n"
        f"- {NIMI_LLM_LLE}: {s['llm_lle']}\n"
        f"  - joista odottaa vielä LLM-seulontaa: {s['odottaa_llm']}\n"
        f"  - LLM:n luokittelemia: {s['llm_kasitelty']}\n"
        f"- {NIMI_MUKANA}: {s['mukana']}"
    )


def tilasto_taulukko(rivit: list[dict]) -> str:
    """Per-yliopisto-suppilo tekstitaulukkona."""
    sarakkeet = [("Kursseja", "KurssiYhteensa"), ("Meta-hylk.", "MetaHylkaama"), ("LLM:lle", "LLMlle"),
                 ("LLM-hyl.", "LLMHylatty"), ("Odottaa", None), ("Mukana*", "Mukana"), ("HITL", "HitlLkm")]
    otsikko = f"{'Yliopisto':<40}" + "".join(f" {nimi:>10}" for nimi, _ in sarakkeet)
    rivit_txt = [otsikko, "-" * len(otsikko)]
    for r in rivit:
        arvot = [r.get("OdottaaMeta", 0) + r.get("OdottaaLLM", 0) if avain is None else r.get(avain, 0)
                 for _, avain in sarakkeet]
        rivit_txt.append(f"{r['KouluNimi']:<40}" + "".join(f" {a:>10}" for a in arvot))
    rivit_txt.append("Meta-hylk. = meta-suodatuksen hylkäämät; LLM:lle = meta-suodatuksen läpäisseet; "
                     "LLM-hyl. = nyt hylätyt, joiden päätös ei ole meta-suodatuksen; Odottaa = meta- tai "
                     "LLM-vaihe kesken; HITL = korjaustapahtumia.")
    rivit_txt.append("* lopullinen mukana-lista HITL:n jälkeen")
    return "\n".join(rivit_txt)


def hitl_mittarit(tilastot: list[dict]) -> dict:
    """Kaksi raporttimittaria HITL-korjauksista (CLAUDE.md, vaihe 4):

    1. Käsin muutettujen osuus = muutetut kurssit / LLM:n luokittelemat kurssit
       (meta-suodatuksen läpäisseet, joille LLM on antanut päätöksen).
    2. Juurisyyjakauma = korjauksista montako % johtui riittämättömästä
       oppaasta (data-ongelma) vs. LLM:n virheestä (kehote-ongelma).
    """
    llm_kasitelty = sum(r["LLMKasitelty"] for r in tilastot)
    muutettu = sum(r["HitlKursseja"] for r in tilastot)
    opas = sum(r["RiittamatonOpas"] for r in tilastot)
    llm_virhe = sum(r["LlmVirhe"] for r in tilastot)
    tuntematon = sum(r["TuntematonSyy"] for r in tilastot)
    return {
        "llm_kasitelty": llm_kasitelty, "muutettu": muutettu,
        "muutettu_pros": _osuus(muutettu, llm_kasitelty),
        "opas": opas, "opas_pros": _osuus(opas, muutettu),
        "llm_virhe": llm_virhe, "llm_virhe_pros": _osuus(llm_virhe, muutettu),
        "tuntematon": tuntematon, "tuntematon_pros": _osuus(tuntematon, muutettu),
    }


def hitl_yhteenveto_teksti(m: dict) -> str:
    """Muotoilee HITL-mittarit raporttikehotteeseen sopivaksi tekstilohkoksi."""
    opas_nimi = mallit.JUURISYYT["riittamaton_opas"]
    llm_nimi = mallit.JUURISYYT["llm_virhe"]
    return (
        f"Ihmisen käsin muuttamia luokittelupäätöksiä: {m['muutettu']} / "
        f"{m['llm_kasitelty']} LLM:n luokittelemaa kurssia ({m['muutettu_pros']:.1f} %; "
        f"nimittäjä = meta-suodatuksen läpäisseet kurssit, joille LLM antoi päätöksen).\n"
        f"Korjausten juurisyyt (osuus käsin muutetuista kursseista):\n"
        f"- {opas_nimi} (tieto ei ollut oppaassa, data-ongelma): "
        f"{m['opas']} kpl ({m['opas_pros']:.1f} %)\n"
        f"- {llm_nimi} (kehotetta parannettava): "
        f"{m['llm_virhe']} kpl ({m['llm_virhe_pros']:.1f} %)\n"
        f"- Juurisyy merkitsemättä: {m['tuntematon']} kpl ({m['tuntematon_pros']:.1f} %)"
    )
