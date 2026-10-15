# PALAUTE 1

Keräsin huomioita/sekavaa sepostusta tuosta opserveristä kurssien luokittelun vahvistamisen lomassa. En tiedä oliko näitä tarkoitus koota johonkin mutta tässä nyt on :D (ja Piia projektin vetäjänä cc:nä)

Käytettävyyteen liittyen:
Jos tekstiä maalaa yksittäisen kurssin opinto-opas näkymässä, käyttäjä poistuu kyseisestä näkymästä (eikä mahdollisia muutoksia tallenneta)
Ainakin HY:llä kurssien esitietovaatimukset on toisinaan listattu tekstin sijaan linkkaamalla kyseiset kurssit “Esitiedot” kohtaan eikä näin merkattuja esitietovaatimuksia ilmeisesti saada haettua opserverin esittämään opinto-oppaaseen

Fanitan palloja!

Tekoälyn syötteessä luokittelulle ei oltu määritelty kovinkaan tarkkaa kriteeristöä arviointia varten. Täysin tarkkarajainen jako on toki epärealistista mutta itse koin että esim työelämälähtöisyyteen viisiportainen asteikko on turhan laaja. AI:n luokittelu oli toistaiseksi melko epäjohdonmukainen ja oppaan formulointiin perustuva mikä korostui HY:n kursseissa kun meillä käytännössä katsoen sama kurssi on listattu useampaan kertaan. 

1. Listaus oli simppeli ja tekoäly onnistui siinä hyvin. Sopisiko tähän vastaisuudessa valmiiksi määritellyt “labelit” joista valitaan kuhunkin kurssiin pätevät vaihtoehdot? Tällä hetkellä listausten vertailua hankaloittaa sanamuoto, jossa on paljon variaatiota -mm. tentti tai koe opinto-oppaan muotoilusta riippuen.
2. Joustavuus oli etenkin MOOC kurssien osalta yksinkertainen ja luokittelua helpotti luokkien vähyys. Ongelmat liittyivät tämän osalta pääasiassa opinto-oppaiden puutteisiin.
3. Soveltuvuuden "edellyttää osaamista/laajaa osaamista" raja on häilyvä. Itse jakaisin "laajan osaamisen" lähtökohtaisesti esim maisteritason tkt/data science kurssiksi tai käyttäisin tätä jaon tukena.
4. Soveltuvuus (kokonaisuuteen liittyvä kohta): Tässäkin ainakin “ihmisarvioijana” koin tarvetta selkeämmälle erolle 3 ja 4 soveltuvuusarviointien välillä. Tekoälylle annettavassa kehotteessa 3. Ja 4. Kohtien erot ei tulleet kovin tarkasti ilmi joten työkalu näytti luokittelevan 3 ja 4 kohdan soveltuvuuden pääosin identtisesti. Mietin itse rajanvedoksi joitain vs paljon vaatimuksia välille sitä, voiko kurssille ilmoittautua ilman että suorittaa esitietovaatimusten kursseja ensin. HY:n osalta esitietovaatimuksille on oma kappale mutta työkalu arvioi kohtia kokonaisuutena eli voi antaa eri arvion vaikka relevantti kappale olisi identtinen. Tämän fiksaaminen toki edellyttäisi että opinto-oppaat olisivat edes jokseenkin yhdenmukaisia.
5. Asteikko on hieman epäselvä siltä osin mikä on "ajantasaista työelämärelevanttia sisältöä". Opinto-oppaasta voi päätellä (ja se miten ai työkalu luokittelee tässä) miten paljon kurssi sisältää käytännön harjoituksia mutta ei sitä miten ne suhtautuu työelämän kannalta relevantteihin sisältöihin
6. Työkalu ei huomioi käsillä olevan kurssin laajuutta minkä ihminen ottaisi huomioon kurssin joustavuuden osalta. Esim 1op kurssi on itsessään joustava kokonaisuus mutta rakenne ei välttämättä (esim projektikurssien osalta) ole modulaarinen. Tämän kohdan osalta eritoten opinto-oppaissa oli paljon puutteita mutta tekoälytulkinnan virheitä oli myös > esimerkiksi kurssi on modulaarinen koska se voidaan jakaa kurssiin ja kurssikokeeseen?


# PALAUTE 2

Huomasimme, että AI:n arvioinnissa oli virheitä, koska se ei tarkisti ruotsinkieliset kurssikuvaukset. Joidenkin kurssien osalta jouduimme arvioimaan teittyjä asioita oman asiantuntemuksemme perusteella, koska niitä ei ollut kuvattu selkeästi studiehandbokenissamme.


# PALAUTE 3

Kävin JYU:n kurssit läpi työkalulla, pääosin työkalu toimi erinomaisesti, muutamaa poikkeusta lukuun ottamatta.

Tässä lista tekemiäni huomioita työkalun tekemistä luokituksista ja loppuraportista:


Huomioita/muistiinpanoja työkalun käytöstä.

Työkalu ei huomio sitä, että kurssista saatavan opintopistemäärän suurus voi vaihdella, esim. Information Security Management -opintojakso on todellisuudessa 3-5op.
Kun pyrki muokkaamaan LLM tekemää kuvausta ja maalasi koko tekstin, työkalu sulki avatun valikon ja vaihtoi valittua riviä, joten epähuomiossa saattoi muokata tämän jälkeen väärää kurssia (käytössä Chromen uusin versio).
LLM antavat luokitukset olivat välillä ristiriidassa toistensa kanssa, vaikka LLM ja OPS perustelut olivat samat, silti luokitus eri esim. Modulaarisuus/ esitietovaatimukset.
Parhaimmillaan LLM oli tehnyt todella hyvää luokittelua.
Pystyikö LLM tarkastelemaan OPS kautta käsillä olevan suoritustavan lisätietoja? JYU:lla on muutama kurssi, joissa suoritustavat/ sisältö selviää vasta Sisun aktiivisen toteutuksen alasivulta.
Toisinaan luokituksissa käytetyt perustelut vaikuttivat ainakin osittain LLM hallusinoimilta, tai ainakin perustelu ei noudattanut kokonaan sitä, mitä OPS:ssa luki.


Raportin huomiot:
Raportti itsessään onnistuu hyvin ansiokkaasti kuvaamaan luokittelun tuloksia.
Allekirjoittaneelle generoitu teksti oli kuitenkin paikoin hieman vaikealukuista/tönkköä.
