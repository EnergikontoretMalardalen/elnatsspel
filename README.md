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

Fliken **Workshop** börjar med en tom karta. Deltagarna placerar själva stamnätsstationer (högst fyra) och en regionstation per kommun, drar ledningar mellan stationerna och placerar sedan etableringar. Kommuner som inte nås av någon ledning visas som *Ej ansluten*. Tanken är att visa en verklig karta (till exempel Svenska kraftnäts) på projektorn och låta gruppen bestämma hur nätet ska se ut; inga verkliga stationsdata finns i spelet.

## Att göra senare

- Bakgrund från OpenStreetMap (statisk bild eller SVG, med källhänvisning ©&nbsp;OpenStreetMap-bidragsgivare).

- Validera lastflödet mot IEEE-testsystem och pandapower (enhetstester av `sim.js`).
- Lägga till kostnads- och ledtidsindikatorer för nätåtgärder.
- Tillgänglighetsgranskning (WCAG) och test med skärmläsare.
- Överväg GitHub Pages med anpassad 404-sida och en `robots.txt` om sidan inte ska indexeras.

## Licenser

Typsnitten (IBM Plex, Barlow Semi Condensed) ligger under SIL Open Font License; licenstexter finns i `fonts/`.
