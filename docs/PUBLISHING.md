# Veröffentlichung: GitHub Pages und lokaler Server

Stand: 03.10.2026. Der Hub ist lokal abgenommen. Der Quellcode ist in [SamDavid93/SDOYCC](https://github.com/SamDavid93/SDOYCC) hochgeladen. GitHub Pages ist mit GitHub Actions und HTTPS für `https://samdavid93.github.io/SDOYCC/` aktiviert. Die öffentliche Backend-Adresse und damit die Repository-Variable `VITE_API_BASE_URL` fehlen noch; deshalb ist die Website noch nicht ausgeliefert. Der erste Deployment-Versuch wird durch die fehlende API-Adresse blockiert.

## 1. Ziel festlegen

Der erste GitHub-Prüflauf [Verify hub](https://github.com/SamDavid93/SDOYCC/actions/runs/37152987100) ist erfolgreich: 138 Backend-Tests und Frontend-Build. Der separate Deployment-Workflow benötigt noch die öffentliche Backend-Adresse; der erfolgreiche Prüfbuild allein veröffentlicht keine Website.

Festgelegt: GitHub-Benutzer **SamDavid93**, Repository **SDOYCC**, Sichtbarkeit **Public**. Benötigt wird noch eine öffentliche HTTPS-Adresse für den lokalen Server. GitHub Pages ist mit GitHub Free für öffentliche Repositories verfügbar. [GitHub-Dokumentation](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)

Für dieses Projekt lautet die Website `https://samdavid93.github.io/SDOYCC/`. Die Großschreibung von **SDOYCC** im Pfad beibehalten. Ein Repository namens `BENUTZER.github.io` würde den Wurzelpfad `/` verwenden; der vorhandene Pages-Workflow berücksichtigt beide Varianten. Die Anwendung verwendet Hash-Routen unter dem jeweiligen Basispfad.

## 2. Backend über HTTPS erreichbar machen

Der Backend-Prozess bleibt auf `127.0.0.1:8002`. Ein Tunnel leitet die öffentliche HTTPS-Adresse an diesen lokalen HTTP-Dienst weiter. Streamer.bot verwendet weiterhin `http://127.0.0.1:8002/api` und seinen lokalen Schlüssel.

Für den dauerhaften Betrieb einen benannten Cloudflare-Tunnel mit einer eigenen, in Cloudflare eingerichteten Domain verwenden. Im Cloudflare-Dashboard den Tunnel-Connector für Windows und die öffentliche Route zur lokalen Adresse `http://127.0.0.1:8002` einrichten. Tunnel-Anmeldedaten ausschließlich lokal bzw. beim Anbieter verwalten, nicht ins Repository oder in den Chat kopieren. [Cloudflare-Einrichtung](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/)

Ohne Domain ist zunächst ein **zeitlich begrenzter Test** möglich: Nach Installation von `cloudflared` lautet der Aufruf `cloudflared tunnel --url http://127.0.0.1:8002`. Die erzeugte `trycloudflare.com`-Adresse ändert sich bei jedem neuen Tunnel. Danach müssen Backend-Adresse und Pages-Build erneut angepasst werden. Ein Quick Tunnel ist kein dauerhafter Produktionszugang. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

Das Backend und der Tunnel müssen laufen, damit Zuschauer sich anmelden, Kartenbilder laden oder Käufe durchführen können. Der PC darf dabei nicht in den Ruhezustand wechseln. GitHub Pages stellt nur das Frontend bereit.

## 3. Öffentliche Konfiguration vorbereiten

Im Projektordner zunächst die Vorschau mit den **tatsächlichen** Adressen ausführen:

```powershell
.\configure-public.bat --frontend-url "https://samdavid93.github.io/SDOYCC/" --backend-url "https://api.DEINE-DOMAIN.de"
```

Der Befehl zeigt nur sechs öffentliche Einstellungen an und schreibt zunächst nichts. Er setzt den CORS-Ursprung ohne Repository-Pfad und den Vite-Basispfad mit Repository-Pfad. Backend-Adressen mit oder ohne `/api` sind möglich. Lokale Adressen, HTTP, Zugangsdaten in URLs, URL-Parameter und bekannte Platzhalter werden abgelehnt. Die Prüfung kontrolliert das Format, nicht DNS oder Erreichbarkeit.

Sobald die Zieladressen eingerichtet sind, denselben Aufruf mit `--apply` ausführen. Die bisherige `.env` wird unter `artifacts/config-backups/` gesichert, danach werden nur diese Einstellungen ersetzt:

- `APP_ENV=production`
- `ENABLE_DEMO_AUTH=false`
- `FRONTEND_URL`
- `CORS_ORIGINS`
- `VITE_API_BASE_URL`
- `VITE_BASE_PATH`

Datenbankpfad, Streamer.bot-Schlüssel, Reward-ID und sonstige Einstellungen bleiben erhalten. Die Sicherung enthält lokale Geheimnisse und bleibt ebenfalls außerhalb von Git. Der Befehl startet keine Prozesse neu und führt keine Kontobuchungen durch.

Backend neu starten und `check-system.bat --public` ausführen. Die Prüfung ist lokal und ersetzt nicht den Zugriffstest von außerhalb. Die lokale Vite-Seite ist nach dieser Umstellung nicht mehr in der CORS-Liste; für den öffentlichen Test die Pages-Adresse verwenden.

## 4. GitHub Pages bereitstellen

1. Repository mit der festgelegten Sichtbarkeit anlegen und den Quellcode einschließlich `.github/workflows/` hochladen. `.env`, Datenbanken einschließlich WAL-/SHM-Dateien, Sicherungen, Cache und `artifacts/` bleiben ausgeschlossen. Vor dem ersten Push die vorgemerkten Dateien prüfen.
2. Unter **Settings → Secrets and variables → Actions → Variables** die Repository-Variable `VITE_API_BASE_URL` auf die vollständige Backend-API-Adresse setzen, etwa `https://api.DEINE-DOMAIN.de/api`. Das ist eine öffentliche Adresse, kein Geheimnis. Niemals den Streamer.bot-Schlüssel als `VITE_`-Variable hinterlegen.
3. Unter **Settings → Pages → Build and deployment → Source** **GitHub Actions** wählen. [GitHub-Anleitung](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
4. Den Workflow **Deploy frontend to GitHub Pages** ausführen. Er verweigert eine leere/lokale Backend-Adresse und erzeugt den passenden Basispfad. Bei einer späteren Änderung der API-Adresse den Workflow erneut ausführen; die Adresse wird beim Build eingebaut.
5. Zusätzlich muss **Verify hub** erfolgreich sein. Der Cloud-Katalogimport ist für die lokale SQLite-Installation deaktiviert. Nur bei bewusst separat eingerichteter Remote-Datenbank `ENABLE_REMOTE_CATALOG_SYNC=true` und das Secret `CARD_DATABASE_URL` setzen; für diesen lokalen Server ist das nicht erforderlich.

## 5. Tatsächliche Abnahme

- Auf einem anderen Gerät über Mobilfunk Pages aufrufen; Logo, Banner, Katalog und Kartenbilder prüfen.
- Backend-Health unter der öffentlichen Adresse mit `/api/health` prüfen. Browser-Konsole darf keine CORS- oder Mixed-Content-Fehler melden.
- Registrierung über `!register`, browsergebundenen Code und `!confirm CODE` abschließen; danach Passwort-Login testen. Bestehende Konten können sich direkt anmelden.
- Eine echte Reward-Einlösung durchführen: 1.000 Kanalpunkte werden zu genau 100 Sammelpunkten; der Queue-Eintrag wird nach erfolgreicher Buchung abgeschlossen. Wiederholung derselben Redemption-ID darf nicht doppelt buchen.
- Einen Standardbooster für 100 Punkte kaufen, Beleg und Tresor prüfen und öffnen. Das sind echte Kontoaktionen, daher mit dem Betreiber durchführen.
- Erste Saison im Admin-Bereich nach bewusst gewählten Zeiten und Belohnungen veröffentlichen.

Erst nach diesen Nachweisen ist der öffentliche Start abgenommen. Die lokale Software-Abnahme steht getrennt davon in [FINAL_STATUS.md](FINAL_STATUS.md).
