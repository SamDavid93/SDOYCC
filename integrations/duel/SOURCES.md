# Quellenverzeichnis des D0-Techniklabors

Stand: 05.10.2026. Exakte Downloadadressen, Commitstände und SHA-256 stehen in [sources.lock.json](sources.lock.json). Downloads landen ausschließlich in `artifacts/duel-probe/`; sie werden nicht in den Hub-Katalog importiert. Neue Kartengrafiken, EDOPro-Musik oder Sounds werden in diesem Labor nicht kopiert.

| Komponente | Festgeschriebener Stand / Verwendung | Lizenz-/Herkunftsnachweis |
| --- | --- | --- |
| Python Embedded Windows x86 | 3.14.0, nur Worker-Laufzeit | [Offizieller Download](https://www.python.org/ftp/python/3.14.0/), mitgeliefertes `python32/LICENSE.txt` einschließlich Drittkomponenten beibehalten |
| EDOPro Core-Binärdatei | `ProjectIgnis/bin` Commit `479d3597f1b4993c4df3eba33ca92af537f186fc`, `ocgcore.dll`; API 11.0 im Lauf geprüft | [Binärquelle](https://github.com/ProjectIgnis/bin/tree/479d3597f1b4993c4df3eba33ca92af537f186fc), [Core-Repository](https://github.com/edo9300/ygopro-core) nennt AGPL-3.0-or-later |
| Core-API-Referenz | `edo9300/ygopro-core` Commit `38d04c9feb1a26617407091380634c87262fe3f8`; C-ABI-Typen und Aufrufe | [API-Header](https://github.com/edo9300/ygopro-core/blob/38d04c9feb1a26617407091380634c87262fe3f8/ocgapi.h), [Typen](https://github.com/edo9300/ygopro-core/blob/38d04c9feb1a26617407091380634c87262fe3f8/ocgapi_types.h) |
| EDOPro-Client | Protokollreferenz `gframe/duelclient.cpp`; nativer Client wird nicht ausgeliefert | [Client und Lizenzhinweise](https://github.com/edo9300/edopro); bei weiterem Protokollausbau genauen Referenzcommit festhalten |
| BabelCDB | `5ef09b033c3e26f74b2fdd0c336853c13217b85f`; Kartenwerte und englische Texte | [Quelle](https://github.com/ProjectIgnis/BabelCDB/tree/5ef09b033c3e26f74b2fdd0c336853c13217b85f); Rechte-/Weitergabebedingungen für Daten und Kartentexte vor öffentlicher Paketbereitstellung noch abschließend prüfen |
| CardScripts | `d331dbd1b5ce6ed829d80ce025e03020f89046d9`; Bootstrap und echte Karteneffekte | [Quelle](https://github.com/ProjectIgnis/CardScripts/tree/d331dbd1b5ce6ed829d80ce025e03020f89046d9); mitgelieferte Datei `scripts/COPYING` und Datei-Hinweise erhalten |
| LFLists | `56fed86d12c0cf2e1b612e649afc817b8c021cd7`; für nachfolgende Regelbasis vorbereitet | [Quelle](https://github.com/ProjectIgnis/LFLists/tree/56fed86d12c0cf2e1b612e649afc817b8c021cd7); noch nicht als aktiver TCG-Validator eingebunden |
| Multirole | Nur Architektur-Recherche; keine Serverbinärdatei Bestandteil des Laborstarts | [Repository](https://github.com/DyXel/Multirole), AGPL-3.0 |

Die DLL-Prüfsumme belegt die heruntergeladene Datei, nicht einen reproduzierbaren Build aus dem API-Referenzcommit. **Der zugehoerige Quellstand ist inzwischen anhand des Binaercommit-Hinweises identifiziert; Details und Buildweg unten. Ein lokal byteidentischer Neuaufbau wurde nicht durchgefuehrt.** API-Kompatibilität und der lokale Testlauf sind nachgewiesen; vollständige Kompatibilität aller Skripte und Kartentypen ist es noch nicht.

Vor Veröffentlichung der Engine-Integration: genaue Lizenzzuordnung der übernommenen Bestandteile, zugehöriger Quelltext/Änderungen, Buildanleitung und erforderliche Hinweise bereitstellen. Getrennte Prozesse allein klären die Lizenzpflichten nicht. Software-Lizenz und Nutzungsrechte an Kartenbildern, Texten, Marken oder Ton getrennt erfassen. Das Labor ist keine abgeschlossene Lizenzfreigabe für die spätere öffentliche DuelZone.


## Referenzerganzung 06.10.2026

Protokoll-/Deklarationsreferenz: EDOPro Commit `c250b6ab9beb`, [duelclient.cpp](https://github.com/edo9300/edopro/blob/c250b6ab9beb/gframe/duelclient.cpp), event_handler.cpp, client_field.cpp und data_manager.cpp. Prozessidentitaet: [psutil](https://psutil.readthedocs.io/); Ressourcenlimits: [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

[Offizielle EU-Bannliste](https://www.yugioh-card.com/eu/play/forbidden-and-limited-list/): Datenendpunkt beim Abruf `from=18/05/2026`; Nachweis unter `artifacts/duel-reference/official-banlist.json`. Abweichung zur Datei `2026.09TCG` ungeklart; keine aktuelle EU-Freigabe. Alle oben benannten offenen Quell-/Lizenznachweise bleiben bestehen. Ton synthetisch per WebAudio, keine EDOPro-Tonassets uebernommen.


## Zugeordneter DLL-Quellstand und Buildweg

Der [Binaercommit](https://github.com/ProjectIgnis/bin/commit/479d3597f1b4993c4df3eba33ca92af537f186fc) nennt `Update core to efc21aa`. Die GitHub-Commitzuordnung ergibt [Core efc21aa433b88cd35b7c37db4072a35c58d9d435](https://github.com/edo9300/ygopro-core/tree/efc21aa433b88cd35b7c37db4072a35c58d9d435); dessen Tree bindet [Lua 6e22fedb74cf0c9b6656e9fce8b7331db847c605](https://github.com/lua/lua/tree/6e22fedb74cf0c9b6656e9fce8b7331db847c605). `corresponding-source.lock.json` enthaelt beide unveraenderlichen Archiv-URLs und SHA-256. `provision_corresponding_source.py` liefert 177 Quelldateien inklusive LICENSE, COPYING, Lua und Provenienz nach `artifacts/duel-corresponding-source`.

Der API-Referenzcommit oben ist eine ABI-Referenz, nicht der jetzt zugeordnete Buildcommit. Der Quellstand ist durch den Upstream-Veroeffentlichungshinweis belegt; ein lokal byteidentischer Wiederaufbau der DLL ist nicht behauptet.

Der zugeordnete [Buildworkflow](https://github.com/edo9300/ygopro-core/blob/efc21aa433b88cd35b7c37db4072a35c58d9d435/.github/workflows/ygopro-core.yml) verwendet fuer x86 Visual Studio 2022 mit v141-/WinXP-Komponenten, Premake `--oldwindows=true`, Release/Win32 und das Ziel `ocgcoreshared`. Nach dem Checkout und rekursiver Submodulinitialisierung:

```powershell
premake5.exe vs2022 --oldwindows=true
msbuild.exe build/ocgcore.sln -p:Configuration=Release -p:Platform=Win32 -t:ocgcoreshared
```

Die Buildskripte und Premake-Konfiguration sind im Quellenpaket enthalten. Auf diesem Rechner fehlen die Compilerwerkzeuge; es wurde keine Installation oder Kompilierung vorgetaeuscht. Fuer eine Veroeffentlichung gehoeren diese Quellen und die Hub-/Adapteraenderungen in den vorgesehenen Quellbereitstellungsumfang. Die rechtliche Zuordnung dieses Umfangs und Kartenrechte sind damit nicht pauschal freigegeben.

Systemtexte: [ProjectIgnis/Distribution config/strings.conf](https://github.com/ProjectIgnis/Distribution/blob/54a6e2395c532648ff762540e9615319fac4f51b/config/strings.conf), Revision und Hash in `strings.lock.json`; Original-Copyrighthinweis erhalten. Texte werden als englischer Engine-Fallback verwendet. Keine fremden EDOPro-Tondateien oder Grafikeffekte uebernommen.
