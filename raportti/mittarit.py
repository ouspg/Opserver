"""Raportin rakenteelliset luvut per-yliopisto-tilastoista (hae_tilastot_yliopistoittain):
kurssien suppilo ja HITL-mittarit sekä niiden tekstimuodot raporttikehotteisiin.
Auktoritatiivisia lukuja — LLM vain kirjoittaa niistä proosaa."""
from tietokanta import mallit

# Raporttiteksteissä käytetyt nimet (samat kaikissa osioissa, ettei luvut sekoitu).
NIMI_MUKANA = "Lopullinen mukana-lista (HITL:n jälkeen)"
NIMI_ALKUPERAINEN = "LLM:n alkuperäinen valinta"
NIMI_LLM_LLE = "LLM:n seulomat kurssit (meta-suodatuksen läpäisseet)"
NIMI_META = "Meta-suodatuksen hylkäämät (sääntöpohjainen taso-/oppiainerajaus, ei LLM)"


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


def keskeiset_luvut_teksti(tilastot: list[dict]) -> str:
    """Suppilo + LLM:n alkuperäinen valinta kehotteeseen. Sama lohko kaikissa osioissa,
    jotta jokainen luku on nimetty yksiselitteisesti ja samoin."""
    s, m = suppilo(tilastot), hitl_mittarit(tilastot)
    return (
        f"- Kursseja tutkimuksen rajauksessa (lukuvuosi + valitut korkeakoulut): {s['kursseja']}\n"
        f"- Odottaa vielä meta-suodatusta: {s['odottaa_meta']}\n"
        f"- {NIMI_META}: {s['meta_hylkaama']}\n"
        f"- {NIMI_LLM_LLE}: {s['llm_lle']}\n"
        f"  - joista odottaa vielä LLM-seulontaa: {s['odottaa_llm']}\n"
        f"  - LLM:n luokittelemia: {s['llm_kasitelty']}\n"
        f"- {NIMI_ALKUPERAINEN}: {m['llm_alkuperainen']} (ennen ihmisen korjauksia)\n"
        f"- {NIMI_MUKANA}: {s['mukana']}"
    )


def tilasto_taulukko(rivit: list[dict]) -> str:
    """Per-yliopisto-suppilo tekstitaulukkona."""
    sarakkeet = [("Kursseja", "KurssiYhteensa"), ("Meta-hylk.", "MetaHylkaama"), ("LLM:lle", "LLMlle"),
                 ("LLM-hyl.", "LLMHylatty"), ("Odottaa", None), ("Mukana*", "Mukana"),
                 ("Mukana-%", "%"), ("HITL", "HitlLkm")]
    otsikko = f"{'Yliopisto':<40}" + "".join(f" {nimi:>10}" for nimi, _ in sarakkeet)
    rivit_txt = [otsikko, "-" * len(otsikko)]
    for r in rivit:
        erikois = {None: r.get("OdottaaMeta", 0) + r.get("OdottaaLLM", 0),
                   "%": f"{_osuus(r.get('Mukana', 0), r.get('LLMlle', 0)):.1f}"}
        arvot = [erikois[avain] if avain in erikois else r.get(avain, 0) for _, avain in sarakkeet]
        rivit_txt.append(f"{r['KouluNimi']:<40}" + "".join(f" {a:>10}" for a in arvot))
    rivit_txt.append("Meta-hylk. = meta-suodatuksen hylkäämät; LLM:lle = meta-suodatuksen läpäisseet; "
                     "LLM-hyl. = nyt hylätyt, joiden päätös ei ole meta-suodatuksen; Odottaa = meta- tai "
                     "LLM-vaihe kesken; Mukana-% = mukana / LLM:lle (vertaa yliopistoja vain tällä); "
                     "HITL = korjaustapahtumia.")
    rivit_txt.append("* lopullinen mukana-lista HITL:n jälkeen")
    return "\n".join(rivit_txt)


def hitl_mittarit(tilastot: list[dict]) -> dict:
    """HITL-korjausmittarit (CLAUDE.md, vaihe 4) kunkin kurssin viimeisimmästä korjauksesta.

    - Suunta × kumottu vaihe: lisatty_/poistettu_ × meta/llm (nettomuutokset alkuperäiseen
      automaattiseen päätökseen; edestakaisin alkutilaan käännetyt = palautettu, eivät virheitä).
    - HITL:n kattavuus: tarkistetut (hyväksytyt tai korjatut) mukana-kurssit.
    - Kumottujen osuudet omista nimittäjistään: LLM-päätökset / LLM:n luokittelemat
      (meta-suodatuksen läpäisseet, joille LLM antoi päätöksen), meta-päätökset /
      meta-suodatuksen hylkäämät.
    - LLM:n alkuperäinen valinta = lopullinen mukana − ihmisen lisäämät + ihmisen poistamat
      − ihmisen suoraan mukaan ottamat LLM:ää odottaneet.
    - Juurisyyjakauma suunnittain ja yhteensä (osuus nettomuutoksista): riittämätön
      opas (data-ongelma) vs. LLM:n virhe (kehote-ongelma).
    """
    summa = lambda avain: sum(r.get(avain, 0) for r in tilastot)
    m = {"llm_kasitelty": summa("LLMKasitelty"), "meta_hylkaama": summa("MetaHylkaama"),
         "mukana": summa("Mukana"), "mukana_tarkistettu": summa("MukanaTarkistettu"),
         "korjattuja": summa("HitlKursseja"),
         "palautettu": summa("Palautettu"), "suoraan": summa("Suoraan")}
    for suunta in ("lisatty", "poistettu"):
        etu = suunta.capitalize()
        m[f"{suunta}_meta"], m[f"{suunta}_llm"] = summa(f"{etu}Meta"), summa(f"{etu}LLM")
        m[suunta] = m[f"{suunta}_meta"] + m[f"{suunta}_llm"]
        for syy, avain in (("opas", "Opas"), ("llm_virhe", "LlmVirhe"), ("tuntematon", "Tuntematon")):
            m[f"{suunta}_{syy}"] = summa(f"{etu}{avain}")
    m["muutettu"] = m["lisatty"] + m["poistettu"]
    m["llm_kumottu"] = m["lisatty_llm"] + m["poistettu_llm"]
    m["llm_kumottu_pros"] = _osuus(m["llm_kumottu"], m["llm_kasitelty"])
    m["meta_kumottu"] = m["lisatty_meta"] + m["poistettu_meta"]
    m["meta_kumottu_pros"] = _osuus(m["meta_kumottu"], m["meta_hylkaama"])
    m["llm_alkuperainen"] = m["mukana"] - m["lisatty"] + m["poistettu"] - summa("SuoraanMukana")
    for syy in ("opas", "llm_virhe", "tuntematon"):
        m[syy] = m[f"lisatty_{syy}"] + m[f"poistettu_{syy}"]
        m[f"{syy}_pros"] = _osuus(m[syy], m["muutettu"])
    return m


def hitl_yhteenveto_teksti(m: dict) -> str:
    """Muotoilee HITL-mittarit raporttikehotteeseen sopivaksi tekstilohkoksi."""
    opas_nimi = mallit.JUURISYYT["riittamaton_opas"]
    llm_nimi = mallit.JUURISYYT["llm_virhe"]
    syyt = lambda suunta: (f"{opas_nimi} {m[f'{suunta}_opas']}, {llm_nimi} {m[f'{suunta}_llm_virhe']}, "
                           f"merkitsemättä {m[f'{suunta}_tuntematon']}")
    return (
        f"Luokittelupäätösten korjaukset (kunkin kurssin viimeisin korjaus verrattuna "
        f"alkuperäiseen automaattiseen päätökseen):\n"
        f"- Ihminen lisäsi mukaan: {m['lisatty']} (LLM:n hylkäämiä {m['lisatty_llm']}, "
        f"meta-suodatuksen hylkäämiä {m['lisatty_meta']})\n"
        f"- Ihminen poisti: {m['poistettu']} (LLM:n valitsemia {m['poistettu_llm']}, "
        f"meta-suodatuksen {m['poistettu_meta']})\n"
        f"- Korjattu edestakaisin ja palautettu alkutilaan (ei nettomuutosta): {m['palautettu']}\n"
        f"- LLM-seulontaa odottaneita, jotka ihminen päätti suoraan: {m['suoraan']} "
        f"(eivät ole LLM:n päätöksiä eivätkä korjauksia)\n"
        f"- {NIMI_ALKUPERAINEN}: {m['llm_alkuperainen']} → {NIMI_MUKANA}: {m['mukana']}\n"
        f"- LLM:n päätöksiä kumottu: {m['llm_kumottu']} / {m['llm_kasitelty']} LLM:n luokittelemasta "
        f"kurssista ({m['llm_kumottu_pros']:.1f} %; nimittäjä = meta-suodatuksen läpäisseet "
        f"kurssit, joille LLM antoi päätöksen)\n"
        f"- Meta-suodatuksen päätöksiä kumottu: {m['meta_kumottu']} / {m['meta_hylkaama']} "
        f"meta-suodatuksen hylkäämästä ({m['meta_kumottu_pros']:.1f} %)\n"
        f"Juurisyyt suunnittain: lisätyt: {syyt('lisatty')}; poistetut: {syyt('poistettu')}.\n"
        f"Juurisyyt yhteensä (osuus {m['muutettu']} nettomuutoksesta):\n"
        f"- {opas_nimi} (tieto ei ollut oppaassa, data-ongelma): "
        f"{m['opas']} kpl ({m['opas_pros']:.1f} %)\n"
        f"- {llm_nimi} (kehotetta parannettava): "
        f"{m['llm_virhe']} kpl ({m['llm_virhe_pros']:.1f} %)\n"
        f"- Juurisyy merkitsemättä: {m['tuntematon']} kpl ({m['tuntematon_pros']:.1f} %)\n"
        f"HITL:n kattavuus: Ihminen on tarkistanut (hyväksynyt tai korjannut) {m['mukana_tarkistettu']} / "
        f"{m['mukana']} lopullisen mukana-listan kurssia. Hylättyjä kursseja ei ole käyty "
        f"järjestelmällisesti läpi: korjauksia on tehty molempiin suuntiin, mutta hylättyjen "
        f"tarkistuksesta ei ole kirjausta (vain ihmisen lisäämät {m['lisatty']} kurssia tunnetaan). "
        f"Siksi korjausosuudesta ei voi päätellä väärien poisjättöjen määrää eikä seulonnan tarkkuutta."
    )
