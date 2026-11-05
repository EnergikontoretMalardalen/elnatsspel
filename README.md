# Regionnätsspelet

Interaktivt spel för kommunala tjänstepersoner: hur påverkar en stor etablering (förbrukning eller produktion) i en kommun den lediga kapaciteten i en annan? Kartan visar Uppsala län med en station per kommun och stamnätsstationen i mitten. Kommunnamnen är bara kartunderlag; stationer, ledningar och siffror är **påhittade** och illustrerar bara en princip. Spelet är inget beslutsunderlag.

Allt körs i webbläsaren (ren HTML/CSS/JavaScript). Ingen server, databas eller byggsteg behövs.

## Filer

| Fil | Innehåll |
|---|---|
| `index.html` | Gränssnitt, uppdrag och texter |
| `sim.js` | Simuleringsmotor: DC-lastflöde, N-1, PTDF, ledig kapacitet, förstärkta och nya ledningar. Nätet är en stjärna kring stamnätsstationen och startvärdena finns överst i filen |
| `map.js` | Förenklad statisk karta över Uppsala län (genererad) |
| `tools/make_map.py` | Skapar `map.js` från öppna kommungränser (kräver `shapely`) |
| `fonts/` | Typsnitt som levereras från egen domän (inga anrop till Google, GDPR) |
| `.github/workflows/pages.yml` | Publicerar automatiskt till GitHub Pages |
| `embed-wordpress.html` | Iframe-kod för WordPress |

## Kör lokalt

Öppna `index.html` i en webbläsare, eller starta en enkel server: `python3 -m http.server 8000` och gå till `http://localhost:8000`.

## Publicera på GitHub Pages (gratis, publikt repo)

1. Skapa ett publikt repo på GitHub, till exempel `elnatsspel`, och ladda upp innehållet i den här mappen (inklusive mappen `.github`).
2. Repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Pusha till `main`. Under fliken **Actions** syns publiceringen. Sidan hamnar först på `https://<konto>.github.io/<repo>/`.

## Egen adress (t.ex. elnatsspel.minhemsida.se)

1. **DNS** hos den som sköter domänen: lägg en **CNAME-post**, namn `elnatsspel`, värde `<konto>.github.io` (utan sökväg).
2. Repo → **Settings → Pages → Custom domain**: skriv `elnatsspel.minhemsida.se` och spara. Då skapas en `CNAME`-fil i repot (du kan också lägga den själv; den ska bara innehålla adressen på en rad).
3. Vänta tills DNS slagit igenom (minuter till timmar) och kryssa i **Enforce HTTPS** när rutan blir valbar.
4. Tips: verifiera domänen under kontots **Settings → Pages** så att ingen annan kan ta över underdomänen.

## Bädda in i WordPress

Använd koden i `embed-wordpress.html` i ett Anpassad HTML-block. Vissa teman och säkerhetsplugin blockerar iframes; tillåt då den egna domänen. Länka också till spelet i eget fönster. Det fungerar bäst på mobil. Justera `height` om sidan klipps.

## Karta och data

Bakgrundskartan är statisk (ingen kartserver, inga anrop från besökarens webbläsare). Kommungränserna kommer från [okfse/sweden-geojson](https://github.com/okfse/sweden-geojson) (förenklade, ursprungligen Valmyndigheten via Opendatasoft). Kör `python3 tools/make_map.py` för att generera om `map.js`, till exempel om kartan ska beskära eller färgläggas annorlunda.

## Workshop-läge

Spelet startar i uppdraget **Befintligt nät** (förladdat regionnät där deltagarna placerar en stor etablering och ser i en tabell hur varje kommun påverkas). **Blank karta** ligger som alternativ i uppdragsraden. Uppdragen 1–4 och *Prova själv* finns kvar i koden men visas inte (se `TAB_ORDER` i `index.html`). Deltagarna placerar själva stamnätsstationer (högst fyra) och regionnätsstationer, drar ledningar mellan stationerna och placerar sedan etableringar. Varje regionnätsstation har en last (schablon 30 MW tills nätägarens siffror finns; ändras under *Last och produktion*) och nya etableringar ansluts till stationerna. Resultat visas per station, grupperat efter kommun. *Station på ledning* ger en knutpunkt utan last. Stationer som inte nås av någon ledning visas som *Ej ansluten*. Vattenfalls värde för ledig kapacitet visas som referens vid stationen (Vattenfalls data styr: ersätt schablonen med deras siffror i *Last och produktion*). Tanken är att visa en verklig karta (till exempel Svenska kraftnäts) på projektorn och låta gruppen bestämma hur nätet ska se ut; inga verkliga stationsdata finns i spelet.

### Stamnätet från Svenska kraftnäts filer (valfritt)

Knappen **Ladda stamnät** (under Stationer) läser in shapefilerna direkt (zip-filen SVK_STAMNAT, där bara STATIONER och SVK_LEDNINGAR används, eller de två lagren som separata zip-filer som markeras samtidigt) eller en `stamnat.json`: stamnätsstationerna inom länet placeras där de ligger och stamnätets ledningar visas som bakgrund. Filen kan också göras i förväg av shapefilerna:

```
pip install pyshp pyproj shapely
python3 tools/stamnat_till_json.py STATIONER.shp SVK_LEDNINGAR.shp stamnat.json
```

`stamnat.json` ligger i `.gitignore` och finns inte i repot, eftersom licensen för datan måste vara klar innan den publiceras. Utan filen i repot öppnar knappen en filväljare, och filen läses bara i webbläsaren. Stationerna har inga namn i underlaget och numreras därför.

### Regionnät från OpenStreetMap (valfritt)

**Ladda stamnät/regionnät** läser även en OpenStreetMap-export (Overpass-JSON eller GeoJSON): substationer och kraftledningar på 70, 130, 220 och 400 kV. Stationer på 220 kV och uppåt blir stamnätsstationer, 50–219 kV regionnätsstationer, och ledningarna visas som bakgrund. Frågan att köra i [overpass-turbo.eu](https://overpass-turbo.eu/) står i förklaringen under Stationer i spelet. Kapaciteter finns inte i OSM, så alla ledningar som räknas är de som spelarna drar själva. Källa: © OpenStreetMap-bidragsgivare (ODbL). Uppgifterna är inskickade av frivilliga och kan vara ofullständiga eller felaktiga. En OSM-export får läggas i repot om källan anges och filen delas under ODbL.

### Nätområden (lokalnät, valfritt)

Knappen **Ladda nätområden** (zip- eller shapefilen, eller `natomraden.json`) lägger ett lager över kartan med lokalnätens nätområden (områdesnamn och nätägare), som inte följer kommungränserna. Filen kan också göras i förväg:

```
python3 tools/natomraden_till_json.py Natomraden_SE3_Sw99TM.shp natomraden.json
```

`natomraden.json` ligger i `.gitignore` av samma skäl som stamnätsfilen: kontrollera licensen innan den publiceras.

## Att göra senare

- Bakgrund från OpenStreetMap (statisk bild eller SVG, med källhänvisning ©&nbsp;OpenStreetMap-bidragsgivare).

- Validera lastflödet mot IEEE-testsystem och pandapower (enhetstester av `sim.js`).
- Lägga till kostnads- och ledtidsindikatorer för nätåtgärder.
- Tillgänglighetsgranskning (WCAG) och test med skärmläsare.
- Överväg GitHub Pages med anpassad 404-sida och en `robots.txt` om sidan inte ska indexeras.

## Licenser

Typsnitten (IBM Plex, Barlow Semi Condensed) ligger under SIL Open Font License; licenstexter finns i `fonts/`.

## Shapefiler i webbläsaren

`shp.js` läser `.zip`, `.shp` och `.dbf` direkt i webbläsaren (zip packas upp med `DecompressionStream`, SWEREF 99 TM räknas om till kartans koordinater). Inget skickas någonstans, och ingen data ligger i repot.


### Regionnätsledningar som går att välja
OSM-ledningarna under 200 kV läses som en vektor per ledningssträcka. De är blå och ingår inte i beräkningen. Klicka på en i fliken Ledningar, ange kapacitet (MW) och den blir röd och räknas med. Längd = polylinjens längd i kartan; reaktans = 0,275·km/MW. Ändpunkterna snappas till närmaste station (≤ ca 2 km), annars skapas en regionnätsstation. Kapacitet finns inte i OSM, så den anges av användaren.

### Medföljande OSM-data
`osm_uppsala.json` är en export från Overpass (overpass-turbo.eu) för Uppsala län, omräknad till kartans koordinater. Knappen *Ladda stamnät/regionnät* läser den automatiskt (om `stamnat.json` saknas), så spelarna behöver inte hämta något. *Egen fil…* väljer en annan fil. Data © OpenStreetMap-bidragsgivare (ODbL), kan vara ofullständig eller felaktig.

### Vattenfalls kapacitetskarta (jämförelse)
`vattenfall_ref.json` innehåller de av Vattenfalls regionnätsstationer i Uppsala län som finns i Lantmäteriets filer (läget är flyttat dit; stationer som saknas där är borttagna; värden från screenshots av Vattenfalls kapacitetskarta; värden för ledig kapacitet för hög elkonsumtion avlästa via klick i kartan, >50 MW anges som >50). Närliggande stationer (≤ ca 5 km) är ihopslagna till en, som får det högsta värdet, inte summan. Lagret slås på med *Visa Vattenfalls kapacitetskarta* under kartan och ingår inte i beräkningen. Kontrollera att uppgifterna får visas innan spelet sprids.

### Lantmäteriets ledningar
`lm_uppsala.json` har ledningar från Lantmäteriet Topografi 100 Nedladdning vektor (lager Ledningslinje, objekttyp 1702 stam och 1703 region, CC0), samt stamnäts- och regionnätsstationernas lägen (lagren Transformatoromrade och Transformatoromradespunkt; stationernas lägen finns enbart i Topografi 50). Den läses före `osm_uppsala.json`. Lantmäteriet anger bara region (25–200 kV) och stam (över 200 kV), inte exakt kV. Omräkning: SWEREF 99 TM till kartans koordinater, förenklad med 0,8 px tolerans.

### Uppdatering: Lantmäteriets ledningar och stationer
`lm_uppsala.json` görs nu med `tools/lm_till_json.py` av Lantmäteriets GeoPackage-filer (ledningar_ln01 Stockholm, ln03 Uppsala, ln19 Västmanland, ln21 Gästrikland). Stationerna kommer från lagren transformatoromrade och transformatoromradespunkt (exakta lägen). Stationer nära en stamnätsledning blir stamnätsstationer, övriga regionnätsstationer. Ledningsbitar som möts i två ändar slås ihop. Vattenfalls stationer (`vattenfall_ref.json`) flyttas till närmaste station i filerna (högst 5 km). Kommandot står överst i skriptet.

### Röda och gröna regionnätsledningar, kommunvärden
Regionnätsledningarna är röda som standard (0 kV, 0 MW, ingår inte). Klicka på en i fliken Ledningar, ange kV och MW, så blir den grön och ingår i beräkningen. Reaktans med angiven spänning: 0,4 Ω/km · km · 100 / kV² (per-unit, 100 MVA). Egna ledningar utan spänning räknas som förut (0,275·km/MW). Kommunernas högsta last och installerad vind- och solkraft kan ändras under Stationer (Last och produktion); förvalen är påhittade tills verkliga siffror finns.

### Ledningar inom länet och stråk
`lm_uppsala.json` innehåller bara de delar av regionnätsledningarna som ligger i länet (plus en punkt utanför länsgränsen så att ledningen når gränsen). Vid aktivering kan kV och MW gälla en ledning, hela stråket (ledningar som möts utan station emellan) eller alla regionnätsledningar i länet.
