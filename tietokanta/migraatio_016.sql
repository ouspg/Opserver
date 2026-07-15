-- Migraatio 016: HITL-korjauksen juurisyy (virhetaksonomia, CLAUDE.md).
-- Erottaa "riittämätön opinto-opas" (oikea vastaus ei johdettavissa oppaan
-- tekstistä → data-ongelma) LLM:n väärinymmärryksestä (vastaus johdettavissa,
-- mutta malli erehtyi → kehote-ongelma). Sallii NULLin: vanhat korjaukset
-- jäävät "tuntematon"-tilaan. Sallitut koodit: 'riittamaton_opas', 'llm_virhe'
-- (ks. tietokanta/mallit.py JUURISYYT).
ALTER TABLE HitlKorjaus ADD COLUMN Juurisyy VARCHAR(32) NULL;
