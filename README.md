# Recover
Schlaf- & Kalorien-App mit Garmin-Sync (PWA).

- App: https://myronmg.github.io/recover
- Sync: `.github/workflows/sync.yml` holt 3× täglich Garmin-Daten über die offizielle Personal API und speichert sie verschlüsselt als `garmin.enc.json`.
- Secrets: `GARMIN_KEY` (Garmin Personal API Key), `SYNC_PASS` (Passwort, das auch in der App eingetragen wird).
