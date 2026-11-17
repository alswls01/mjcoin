# MJ코인 미국 경제지표 발표 일정 파일(web/econ_events.js) 만들기
# 출처: BLS 발표 일정표(bls.gov/schedule), BEA release_dates.json, 연준 FOMC 일정표 (2026-11-17 받음)
import json, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
ET, UTC = ZoneInfo("America/New_York"), ZoneInfo("UTC")
def utc(day, hm):
    d = datetime.strptime(day + hm, "%Y-%m-%d%H%M").replace(tzinfo=ET)
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")
def prev(ref, n):
    if "-Q" in ref:
        y, q = int(ref[:4]), int(ref[-1]); i = y * 4 + q - 1 - n; return f"{i // 4}-Q{i % 4 + 1}"
    y, m = int(ref[:4]), int(ref[5:]); i = y * 12 + m - 1 - n; return f"{i // 12}-{i % 12 + 1:02d}"
rows = [l.split() for l in open("bls.txt") if l.strip()]
ev = []
for k in ["cpi", "ppi", "nfp", "jolts", "eci"]:
    r = sorted([x for x in rows if x[0] == k], key=lambda x: x[1])
    firstknown = next(i for i, x in enumerate(r) if len(x) > 3)
    for i, x in enumerate(r):
        ref = x[3] if len(x) > 3 else prev(r[firstknown][3], firstknown - i)
        ev.append({"k": k, "t": utc(x[1], x[2]), "ref": ref})
bea = json.load(open(sys.argv[1]))
for k, name in [("gdp", "Gross Domestic Product"), ("pce", "Personal Income and Outlays")]:
    for s in sorted(set(bea[name]["release_dates"])):
        if s >= "2026":
            ev.append({"k": k, "t": datetime.fromisoformat(s).astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")})
fomc = {"2026": [("01", "28", 0), ("03", "18", 1), ("04", "29", 0), ("06", "17", 1), ("07", "29", 0), ("09", "16", 1), ("10", "28", 0), ("12", "09", 1)],
        "2027": [("01", "27", 0), ("03", "17", 0), ("04", "28", 0), ("06", "09", 0), ("07", "28", 0), ("09", "15", 0), ("10", "27", 0), ("11", "17", 0)]}
for y, ms in fomc.items():
    for m, d, sep in ms:
        e = {"k": "fomc", "t": utc(f"{y}-{m}-{d}", "1400")}
        if sep: e["sep"] = 1
        ev.append(e)
ev.sort(key=lambda e: (e["t"], e["k"]))
out = "// MJ코인 미국 경제지표 발표 일정 (시간은 UTC). gen.py 로 만듦, 2026-11-17 기준\n"
out += "// 출처: BLS 발표 일정표, BEA 발표 일정, 연준 FOMC 일정표. 2028년 일정은 2027년 하반기에 공개되면 다시 만들어야 함\n"
out += "window.ECON_EVENTS = [\n" + ",\n".join(json.dumps(e, separators=(",", ":")) for e in ev) + "\n];\n"
open(sys.argv[2], "w").write(out)
print(len(ev), "건")
