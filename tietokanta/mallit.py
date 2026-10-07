"""Tietokantamallit — julkisivu. Kutsujat käyttävät `from tietokanta import mallit` ja
`mallit.X`; toteutus on aihepiireittäin omissa moduuleissaan (TASKS #8, ~500 rivin raja):

  kurssit      korkeakoulut, kurssit, lukuvuodet, tasot, oppiaineet
  tutkimukset  tutkimukset, niiden korkeakoulut, arviointikysymykset
  luokitukset  meta-/LLM-luokittelu, luokitusnäkymät, suppilo, HITL-korjaukset
  vastaukset   arviointien vastaukset ja ihmisten korjaukset niihin
  raportti     raporttiosiot, tuoreus, tilastot
  listayhdistys  lista-arvojen mainintamäärät ja yhdistämispäätökset
  _yhteiset    kyselyapufunktiot ja rajaus-SQL (yksityinen)

Testeissä sisäisen kutsun patchaus (esim. _rajaus) kohdistetaan määrittelevään moduuliin.
"""
from tietokanta.kurssit import *  # noqa: F401,F403
from tietokanta.tutkimukset import *  # noqa: F401,F403
from tietokanta.luokitukset import *  # noqa: F401,F403
from tietokanta.vastaukset import *  # noqa: F401,F403
from tietokanta.raportti import *  # noqa: F401,F403
from tietokanta.listayhdistys import *  # noqa: F401,F403
