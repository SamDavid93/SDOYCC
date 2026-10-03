"""Prepare public URLs without exposing or replacing existing local secrets."""
import argparse
from datetime import datetime, timezone
import ipaddress
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


def https_url(value):
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ValueError("Ungueltige HTTPS-Adresse.") from None
    if (parsed.scheme != "https" or not host or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or port not in (None, 443) or not host.isascii()
            or not re.fullmatch(r"[a-zA-Z0-9.-]+", host)
            or "." not in host or host.endswith((".localhost", ".local", ".internal"))
            or any(x in value.upper() for x in ("YOUR_", "REPLACE_", "EXAMPLE."))
            or not re.fullmatch(r"/[a-zA-Z0-9._/-]*|", parsed.path)
            or any(part in (".", "..") for part in parsed.path.split("/"))):
        raise ValueError("Eine oeffentliche HTTPS-Adresse ohne Zugangsdaten, Parameter oder Platzhalter angeben.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("Lokale oder private IP-Adressen sind nicht oeffentlich erreichbar.")
    return parsed


def public_values(frontend_url, backend_url):
    frontend = https_url(frontend_url)
    backend = https_url(backend_url)
    if backend.path not in ("", "/", "/api", "/api/"):
        raise ValueError("Backend-Adresse als HTTPS-Ursprung oder mit /api angeben.")
    base = frontend.path.rstrip("/") + "/"
    origin = f"https://{frontend.hostname}"
    return {
        "APP_ENV": "production",
        "ENABLE_DEMO_AUTH": "false",
        "FRONTEND_URL": origin + base,
        "CORS_ORIGINS": origin,
        "VITE_API_BASE_URL": f"https://{backend.hostname}/api",
        "VITE_BASE_PATH": base,
    }


def render_env(original, values):
    # Replace every occurrence (including `export KEY=...`) so dotenv cannot
    # resurrect an earlier value. Everything else, especially secrets, stays intact.
    remaining = dict(values)
    lines = []
    for line in original.splitlines(keepends=True):
        match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        key = match.group(1) if match else None
        if key in values:
            if key in remaining:
                lines.append(f"{key}={remaining.pop(key)}\n")
        else:
            lines.append(line)
    if remaining:
        if lines and not lines[-1].endswith(("\r", "\n")):
            lines.append("\n")
        lines.extend(f"{key}={value}\n" for key, value in remaining.items())
    return "".join(lines)


def apply_config(env_path, values, backup_dir):
    original = env_path.read_bytes()
    rendered = render_env(original.decode("utf-8-sig"), values).encode("utf-8")
    if rendered == original:
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_dir / f"local-{stamp}.env"
    with backup.open("xb") as output:
        output.write(original)
    descriptor, temporary = tempfile.mkstemp(prefix=".env.public-", dir=env_path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(rendered)
            output.flush()
            os.fsync(output.fileno())
        # Refuse an intervening edit rather than overwriting it.
        if env_path.read_bytes() != original:
            raise ValueError(".env wurde zwischenzeitlich geaendert. Bitte erneut ausfuehren.")
        os.replace(temporary, env_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup


def main():
    parser = argparse.ArgumentParser(description="Oeffentliche Konfiguration anzeigen; nur --apply schreibt die lokale .env.")
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        values = public_values(args.frontend_url, args.backend_url)
        if not (ROOT / ".env").is_file():
            raise ValueError("Lokale .env fehlt. Zuerst die lokale Einrichtung abschliessen.")
        for key, value in values.items():
            print(f"{key}={value}")
        if args.apply:
            backup = apply_config(ROOT / ".env", values, ROOT / "artifacts" / "config-backups")
            print(f"Konfiguration gespeichert. Sicherung: {backup}" if backup else "Konfiguration war bereits identisch.")
            print("Backend neu starten, check-system.bat --public ausfuehren und Frontend neu veroeffentlichen.")
        else:
            print("Nur Vorschau; keine Datei geaendert. Mit --apply uebernehmen, sobald beide Adressen feststehen.")
        print("GitHub Actions: Repository-Variable VITE_API_BASE_URL auf die oben angegebene API-Adresse setzen.")
    except (ValueError, OSError):
        # Do not print file contents or exception details containing arbitrary input.
        parser.exit(1, "Konfiguration nicht uebernommen: Adressen, lokale .env und Dateizugriff pruefen.\n")


if __name__ == "__main__":
    main()
