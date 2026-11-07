#!/usr/bin/env python3
"""
Garmin -> garmin.json für die Recover-App (offizielle Garmin Personal API, kein Passwort)
1) pip install garmin-connect-personal-api-python
2) Key erstellen: connect.garmin.com/app/settings/personalApiToken
3) python garmin_sync.py          (Key wird abgefragt, oder: GARMIN_KEY=... python garmin_sync.py)
   python garmin_sync.py -d       (speichert zusätzlich Rohdaten in garmin_raw.json zum Debuggen)
"""
import json, os, sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from garmin_personal_api import GarminPersonalApiClient, PersonalApiAuthenticator

DAYS = 14
DEBUG = "-d" in sys.argv
KEY = os.environ.get("GARMIN_KEY") or input("Garmin Personal API Key: ").strip()


def find(o, *keys):
    """Sucht rekursiv den ersten vorhandenen Key (robust gegen verschachtelte Antworten)."""
    if isinstance(o, dict):
        for k in keys:
            if o.get(k) is not None:
                return o[k]
        o = list(o.values())
    if isinstance(o, list):
        for v in o:
            if isinstance(v, (dict, list)):
                hit = find(v, *keys)
                if hit is not None:
                    return hit
    return None


def call(client, name, *args):
    fn = getattr(client, name, None)
    if not fn:
        return None
    try:
        return fn(*args)
    except Exception as e:
        print(f"  ! {name}{args}: {e}", file=sys.stderr)
        return None


def mins(s):
    return round(s / 60) if isinstance(s, (int, float)) else None


def clock(local_ms, gmt_ms):
    if isinstance(local_ms, (int, float)):
        return datetime.fromtimestamp(local_ms / 1000, timezone.utc).strftime("%H:%M")
    if isinstance(gmt_ms, (int, float)):
        return datetime.fromtimestamp(gmt_ms / 1000).strftime("%H:%M")
    return None


def summary_row(data, ds):
    rows = data if isinstance(data, list) else find(data, "dailySummaries", "summaries", "values") or [data]
    if not isinstance(rows, list):
        rows = [rows]
    for row in rows:
        if isinstance(row, dict) and find(row, "calendarDate") == ds:
            return row
    return rows[0] if rows and isinstance(rows[0], dict) else {}


def main():
    with PersonalApiAuthenticator() as auth:
        token = auth.obtain_token(KEY)

    days, raw = [], {}
    with GarminPersonalApiClient(token.access_token) as c:
        for i in range(DAYS - 1, -1, -1):
            ds = (date.today() - timedelta(days=i)).isoformat()
            print("hole", ds)
            s = call(c, "get_daily_sleep", ds) or {}
            sm_raw = call(c, "get_daily_summaries", ds, ds)
            raw[ds] = {"sleep": s, "summary": sm_raw}

            dto = s.get("dailySleepDTO", s) if isinstance(s, dict) else {}
            sm = summary_row(sm_raw, ds)
            need = find(s, "sleepNeed")
            score = find(s, "overall")

            days.append({
                "date": ds,
                "sleepMin": mins(find(dto, "sleepTimeSeconds")),
                "deepMin": mins(find(dto, "deepSleepSeconds")),
                "remMin": mins(find(dto, "remSleepSeconds")),
                "lightMin": mins(find(dto, "lightSleepSeconds")),
                "awakeMin": mins(find(dto, "awakeSleepSeconds")),
                "score": score.get("value") if isinstance(score, dict) else find(s, "sleepScore", "overallScore"),
                "needMin": (need.get("actual") or need.get("baseline")) if isinstance(need, dict) else need,
                "bed": clock(find(dto, "sleepStartTimestampLocal"), find(dto, "sleepStartTimestampGMT")),
                "wake": clock(find(dto, "sleepEndTimestampLocal"), find(dto, "sleepEndTimestampGMT")),
                "hrv": find(s, "avgOvernightHrv", "lastNightAvg"),
                "rhr": find(sm, "restingHeartRate") or find(s, "restingHeartRate"),
                "bb": find(sm, "bodyBatteryMostRecentValue", "bodyBatteryHighestValue"),
                "steps": find(sm, "totalSteps"),
                "stress": find(sm, "averageStressLevel"),
                "kcalTotal": find(sm, "totalKilocalories"),
                "kcalActive": find(sm, "activeKilocalories"),
                "kcalBmr": find(sm, "bmrKilocalories"),
            })

    now = datetime.now(ZoneInfo("Europe/Berlin"))
    out = {"synced": now.strftime("%d.%m.%Y %H:%M"), "days": days}
    pw = os.environ.get("SYNC_PASS")
    if pw:  # verschlüsselt speichern (für öffentliches GitHub-Repo)
        import base64
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        salt, iv = os.urandom(16), os.urandom(12)
        key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000).derive(pw.encode())
        ct = AESGCM(key).encrypt(iv, json.dumps(out).encode(), None)
        b64 = lambda x: base64.b64encode(x).decode()
        with open("garmin.enc.json", "w") as f:
            json.dump({"salt": b64(salt), "iv": b64(iv), "data": b64(ct)}, f)
    else:
        with open("garmin.json", "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
    if DEBUG:
        with open("garmin_raw.json", "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=1, default=str)

    t = days[-1]
    print(f"\n✓ garmin.json gespeichert ({len(days)} Tage) – letzte Nacht: {t['sleepMin']} min, "
          f"Score {t['score']}, Verbrauch gestern {days[-2]['kcalTotal']} kcal")


if __name__ == "__main__":
    main()
