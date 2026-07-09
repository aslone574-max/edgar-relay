# -*- coding: utf-8 -*-
"""fetch_edgar (relay) — runs on a US GitHub Actions runner because SEC blocks KR IP ranges.
Same logic as Alpa_pack2/us_collect/edgar_fetch.py. Output: out/form8k.csv, out/form4.csv
(wide date x symbol daily filing counts). SEC fair-access: UA with contact, ~7 req/s max.
"""
import argparse
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "AlphaPack2 research abyssofvoid@naver.com"}


def _get_json(url, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                return r.json()
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--days", type=int, default=400)
    a = ap.parse_args()
    syms = pd.read_csv(HERE / "sp600.csv")["symbol"].astype(str).tolist()[: a.max]
    j = _get_json("https://www.sec.gov/files/company_tickers.json")
    if j is None:
        raise SystemExit("[edgar] company_tickers.json unreachable")
    cmap = {v["ticker"].upper().replace(".", "-"): int(v["cik_str"]) for v in j.values()}
    cutoff = (pd.Timestamp.today() - pd.Timedelta(days=a.days)).strftime("%Y-%m-%d")
    f8k, f4 = defaultdict(dict), defaultdict(dict)
    ok = fail = 0
    for i, s in enumerate(syms):
        cik = cmap.get(s.upper())
        if cik is None:
            fail += 1
            continue
        jj = _get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", tries=2)
        if jj is None:
            fail += 1
            continue
        try:
            rec = jj["filings"]["recent"]
            for form, date in zip(rec["form"], rec["filingDate"]):
                if date < cutoff:
                    continue
                if form == "8-K":
                    f8k[date][s] = f8k[date].get(s, 0) + 1
                elif form == "4":
                    f4[date][s] = f4[date].get(s, 0) + 1
            ok += 1
        except Exception:
            fail += 1
        if (i + 1) % 25 == 0:
            print(f"[edgar] {i+1}/{len(syms)} ok={ok} fail={fail}", flush=True)
        time.sleep(0.15)
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    for name, d in (("form8k.csv", f8k), ("form4.csv", f4)):
        new = pd.DataFrame.from_dict(d, orient="index").sort_index()
        if new.empty:
            print(f"[edgar] {name}: no rows")
            continue
        new.index = pd.to_datetime(new.index)
        new.fillna(0).to_csv(out / name)
        print(f"[edgar] {name}: {new.shape[0]} days x {new.shape[1]} symbols")
    print(f"[edgar] DONE ok={ok} fail={fail}")
    if ok == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
