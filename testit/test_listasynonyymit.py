"""Vaihe b): LLM:n synonyymiehdotukset (raportti/listasynonyymit.py), LLM mockattu."""
import json
from unittest.mock import patch

import pytest

from raportti import listasynonyymit as ls
from raportti import listanormalisointi as ln

KYSYMYS = {"KysID": 11, "nro": 2, "Kysymys": "Opetusmenetelmät?"}


def _vastaus(*ryhmat):
    return json.dumps({"yhdistykset": [{"kohde": k, "lahteet": l} for k, l in ryhmat]}, ensure_ascii=False)


class TestJasennaVastaus:
    def test_perusmuoto(self):
        teksti = _vastaus(("Luennot", ["Luento-opetus", "Luentoja"]))
        assert ls.jasenna_vastaus(teksti) == [("Luento-opetus", "Luennot"), ("Luentoja", "Luennot")]

    def test_koodiaita_ja_peraan_roskaa(self):
        teksti = "```json\n" + _vastaus(("A", ["a1"])) + "\n```\nToivottavasti auttoi!},"
        assert ls.jasenna_vastaus(teksti) == [("a1", "A")]

    def test_ohjausmerkit_merkkijonossa_sallitaan(self):
        teksti = '{"yhdistykset": [{"kohde": "A\tB", "lahteet": ["x"]}]}'
        assert ls.jasenna_vastaus(teksti) == [("x", "A\tB")]

    def test_tyhja_lista_on_kelvollinen(self):
        assert ls.jasenna_vastaus('{"yhdistykset": []}') == []

    def test_virheelliset_alkiot_ohitetaan_muut_sailyvat(self):
        teksti = json.dumps({"yhdistykset": [
            {"kohde": "A", "lahteet": ["a1", 3, None, "  "]},
            {"kohde": "", "lahteet": ["b1"]},
            {"lahteet": ["c1"]},
            "roskaa",
            {"kohde": "D", "lahteet": "d1"},      # merkkijono listan sijaan → yksi lähde
        ]})
        assert ls.jasenna_vastaus(teksti) == [("a1", "A"), ("d1", "D")]

    @pytest.mark.parametrize("teksti", [
        "",
        "En löytänyt synonyymejä.",
        '{"yhdistykset": [{"kohde": "Luennot", "lahteet": ["Luento-op',   # katkennut
        '{"muuta": 1}',
        "[1, 2]",
    ])
    def test_rikkinainen_vastaus_nostaa_valueerror(self, teksti):
        with pytest.raises(ValueError):
            ls.jasenna_vastaus(teksti)


class TestSuodataParit:
    MAARAT = {"Luennot": 30, "Luento-opetus": 5, "luentoja": 2, "Ryhmätyö": 4}

    def test_tuntemattomat_lahteet_ja_samat_pudotetaan(self):
        parit = [("Luento-opetus", "Luennot"), ("Keksitty", "Luennot"), ("Luennot", "Luennot")]
        assert ls.suodata_parit(parit, self.MAARAT, set(), 11) == {"Luento-opetus": "Luennot"}

    def test_ensimmainen_ryhma_voittaa_ja_ketjut_ratkaistaan(self):
        parit = [("luentoja", "Luento-opetus"), ("luentoja", "Ryhmätyö"), ("Luento-opetus", "Luennot")]
        assert ls.suodata_parit(parit, self.MAARAT, set(), 11) == {
            "luentoja": "Luennot", "Luento-opetus": "Luennot"}

    def test_hylatyt_pudotetaan(self):
        parit = [("Luento-opetus", "Luennot")]
        assert ls.suodata_parit(parit, self.MAARAT, {(11, "Luento-opetus", "Luennot")}, 11) == {}

    def test_liian_pitka_kohde_pudotetaan(self):
        assert ls.suodata_parit([("Ryhmätyö", "x" * 256)], self.MAARAT, set(), 11) == {}


class TestKysyErissa:
    def test_viesti_sisaltaa_kysymyksen_arvot_ja_maarat(self):
        with patch("raportti.listasynonyymit.kutsu.kysy", return_value='{"yhdistykset": []}') as kysy:
            ls.kysy_erissa("Opetusmenetelmät?", {"Luennot": 30, "luento": 1}, "J")
        viesti, jarjestelma = kysy.call_args[0][:2]
        assert "Opetusmenetelmät?" in viesti and '["Luennot", 30]' in viesti and '["luento", 1]' in viesti
        assert jarjestelma == "J" and kysy.call_args.kwargs["json_muoto"] is True
        assert kysy.call_args.kwargs["rajaton"] is True

    def test_isot_joukot_pilkotaan_aakkosjarjestyksessa(self):
        maarat = {f"arvo{i:04d}": 1 for i in range(ls.ERAKOKO + 5)}
        with patch("raportti.listasynonyymit.kutsu.kysy", return_value='{"yhdistykset": []}') as kysy:
            parit, virheet = ls.kysy_erissa("K", maarat, "J")
        assert kysy.call_count == 2 and virheet == 0
        assert '"arvo0000"' in kysy.call_args_list[0][0][0]
        assert f'"arvo{ls.ERAKOKO:04d}"' in kysy.call_args_list[1][0][0]

    def test_katkennut_vastaus_puolittaa_eran(self):
        maarat = {f"a{i:02d}": 1 for i in range(40)}
        vastaukset = iter(['{"yhdistykset": [{"kohde": "a00", "lah',          # katkesi
                           _vastaus(("a00", ["a01"])), _vastaus(("a20", ["a21"]))])
        with patch("raportti.listasynonyymit.kutsu.kysy", side_effect=lambda *a, **k: next(vastaukset)) as kysy:
            parit, virheet = ls.kysy_erissa("K", maarat, "J")
        assert kysy.call_count == 3 and virheet == 0
        assert parit == [("a01", "a00"), ("a21", "a20")]

    def test_pienikin_era_epaonnistuu_lasketaan_virheeksi(self):
        with patch("raportti.listasynonyymit.kutsu.kysy", return_value="roskaa"):
            parit, virheet = ls.kysy_erissa("K", {"a": 1, "b": 2}, "J")
        assert parit == [] and virheet == 1


class TestSynonyymiehdotukset:
    def _aja(self, maarat, kasitellyt=None, paatokset=(), vastaus='{"yhdistykset": []}'):
        with patch("raportti.listasynonyymit.mallit.hae_lista_arvomaarat", return_value=maarat), \
             patch("raportti.listasynonyymit.mallit.hae_lista_paatokset", return_value=list(paatokset)), \
             patch("raportti.listasynonyymit.mallit.hae_llm_kasitellyt", return_value=kasitellyt or {}), \
             patch("raportti.listasynonyymit.lue_kehote", return_value="KEHOTE"), \
             patch("raportti.listasynonyymit.kutsu.kysy", return_value=vastaus) as kysy:
            return ls.synonyymiehdotukset(1, [KYSYMYS]), kysy

    def test_ehdotukset_ja_lahetetyt(self):
        (ehdotukset, lahetetyt, virheet), _ = self._aja(
            {11: {"Luennot": 30, "Luento-opetus": 5}},
            vastaus=_vastaus(("Luennot", ["Luento-opetus"])))
        assert [(e.kysid, e.kysymys_nro, e.lahde, e.kohde) for e in ehdotukset] == [
            (11, 2, "Luento-opetus", "Luennot")]
        assert lahetetyt == {11: {"Luennot", "Luento-opetus"}}
        assert virheet == []

    def test_jo_kasitelty_arvojoukko_ei_kysy_llmlta(self):
        maarat = {11: {"Luennot": 30, "Ryhmätyö": 5}}
        kasitelty = {11: ln.arvojoukon_tiiviste({"Luennot", "Ryhmätyö"}, "KEHOTE")}
        (ehdotukset, lahetetyt, _), kysy = self._aja(maarat, kasitellyt=kasitelty)
        kysy.assert_not_called()
        assert ehdotukset == [] and lahetetyt == {}

    def test_alle_kaksi_arvoa_ei_kysyta(self):
        (_, lahetetyt, _), kysy = self._aja({11: {"Luennot": 3}})
        kysy.assert_not_called()
        assert lahetetyt == {}

    def test_epaonnistunut_era_ei_merkitse_kysymysta_kasitellyksi(self):
        (ehdotukset, lahetetyt, virheet), _ = self._aja({11: {"a": 1, "b": 1}}, vastaus="roskaa")
        assert ehdotukset == [] and lahetetyt == {} and len(virheet) == 1
