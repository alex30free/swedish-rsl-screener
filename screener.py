#!/usr/bin/env python3
"""
Levy RSL Momentum Screener for Swedish Stocks
Computes Relative Strength Levy (RSL) = Current Price / 130-day (26-week) SMA
Ranks all stocks, saves top 20 + full skip log to JSON for the webpage.
"""

import json
import os
import time
import datetime
import warnings
warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: Run: pip install yfinance pandas")
    raise

# --- Load tickers ---
TICKERS = [
    ("AAK", "AAK.ST"), ("ABB", "ABB.ST"), ("AFRY", "AFRY.ST"), ("AQ Group", "AQ.ST"),
    ("AcadeMedia", "ACAD.ST"), ("Acast", "ACAST.ST"), ("Acrinova B", "ACRI-B.ST"),
    ("Active Biotech", "ACTI.ST"), ("AddLife", "ALIF-B.ST"), ("Addnode", "ANOD-B.ST"),
    ("Addtech", "ADDT-B.ST"), ("Alfa Laval", "ALFA.ST"), ("Alimak", "ALIG.ST"),
    ("Alleima", "ALLEI.ST"), ("Alligo", "ALLIGO-B.ST"), ("Alvotech SDB", "ALVO-SDB.ST"),
    ("Ambea", "AMBEA.ST"), ("Arctic Paper", "ARP.ST"), ("Arion Banki", "ARION-SDB.ST"),
    ("Arjo", "ARJO-B.ST"), ("Arla Plast", "ARPL.ST"), ("Assa Abloy", "ASSA-B.ST"),
    ("AstraZeneca", "AZN.ST"), ("Atlas Copco B", "ATCO-B.ST"), ("Atrium Ljungberg", "ATRLJ-B.ST"),
    ("Attendo", "ATT.ST"), ("Autoliv", "ALIV-SDB.ST"), ("Avanza Bank", "AZA.ST"),
    ("Axfood", "AXFO.ST"), ("B3 Consulting", "B3.ST"), ("BE Group", "BEGR.ST"),
    ("BHG Group", "BHG.ST"), ("BICO Group", "BICO.ST"), ("BTS Group", "BTS-B.ST"),
    ("Balco Group", "BALCO.ST"), ("Beijer Alma", "BEIA-B.ST"), ("Beijer Ref", "BEIJ-B.ST"),
    ("Bergman & Beving", "BERG-B.ST"), ("Betsson", "BETS-B.ST"), ("Better Collective", "BETCO.ST"),
    ("Bilia", "BILI-A.ST"), ("Billerud", "BILL.ST"), ("BioArctic", "BIOA-B.ST"),
    ("BioGaia", "BIOG-B.ST"), ("Bjorn Borg", "BORG.ST"), ("Boliden", "BOL.ST"),
    ("Bonava B", "BONAV-B.ST"), ("Bonesupport", "BONEX.ST"), ("Boozt", "BOOZT.ST"),
    ("Boule Diagnostics", "BOUL.ST"), ("Bravida", "BRAV.ST"), ("Bufab", "BUFAB.ST"),
    ("Bulten", "BULTEN.ST"), ("Bure Equity", "BURE.ST"), ("Byggmax", "BMAX.ST"),
    ("C-RAD", "CRAD-B.ST"), ("CTEK", "CTEK.ST"), ("CTT Systems", "CTT.ST"),
    ("Camurus", "CAMX.ST"), ("Castellum", "CAST.ST"), ("Catena", "CATE.ST"),
    ("CellaVision", "CEVI.ST"), ("Cibus Nordic", "CIBUS.ST"), ("Cint Group", "CINT.ST"),
    ("Clas Ohlson", "CLAS-B.ST"), ("Cloetta", "CLA-B.ST"), ("CoinShares", "CS.ST"),
    ("Coor Service Management", "COOR.ST"), ("Corem Property B", "CORE-B.ST"),
    ("Dedicare", "DEDI.ST"), ("Dios Fastigheter", "DIOS.ST"), ("Dometic", "DOM.ST"),
    ("Duni", "DUNI.ST"), ("Dustin Group", "DUST.ST"), ("Dynavox Group", "DYVOX.ST"),
    ("EQT", "EQT.ST"), ("Eastnine", "EAST.ST"), ("Elanders", "ELAN-B.ST"),
    ("Electrolux B", "ELUX-B.ST"), ("Electrolux Professional B", "EPRO-B.ST"),
    ("Elekta", "EKTA-B.ST"), ("Eltel", "ELTEL.ST"), ("Embracer", "EMBRAC-B.ST"),
    ("Enea", "ENEA.ST"), ("Engcon", "ENGCON-B.ST"), ("Eniro", "ENRO.ST"),
    ("Eolus", "EOLU-B.ST"), ("Epiroc B", "EPI-B.ST"), ("Ericsson B", "ERIC-B.ST"),
    ("Essity B", "ESSITY-B.ST"), ("Evolution", "EVO.ST"), ("FM Mattsson", "FMM-B.ST"),
    ("Fabege", "FABG.ST"), ("Fagerhult", "FAG.ST"), ("Fast Balder", "BALD-B.ST"),
    ("Fastpartner A", "FPAR-A.ST"), ("Fenix Outdoor", "FOI-B.ST"), ("Fingerprint Cards", "FING-B.ST"),
    ("Formpipe Software", "FPIP.ST"), ("G5 Entertainment", "G5EN.ST"), ("Garo", "GARO.ST"),
    ("Genova Property", "GPG.ST"), ("Getinge", "GETI-B.ST"), ("Granges", "GRNG.ST"),
    ("HMS Networks", "HMS.ST"), ("Handelsbanken B", "SHB-B.ST"), ("Hanza", "HANZA.ST"),
    ("Heba", "HEBA-B.ST"), ("Hemnet", "HEM.ST"), ("Hennes and Mauritz", "HM-B.ST"),
    ("Hexagon", "HEXA-B.ST"), ("Hexatronic", "HTRO.ST"), ("Hexpol", "HPOL-B.ST"),
    ("Holmen B", "HOLM-B.ST"), ("Hufvudstaden A", "HUFV-A.ST"), ("Humana", "HUM.ST"),
    ("Husqvarna B", "HUSQ-B.ST"), ("ITAB Shop Concept", "ITAB.ST"),
    ("Industrivarден C", "INDU-C.ST"), ("Indutrade", "INDT.ST"), ("Instalco", "INSTAL.ST"),
    ("International Petroleum", "IPCO.ST"), ("Intrum", "INTRUM.ST"), ("Investor B", "INVE-B.ST"),
    ("Invisio", "IVSO.ST"), ("Inwido", "INWI.ST"), ("JM", "JM.ST"),
    ("K-Fast Holding", "KFAST-B.ST"), ("Kinnevik B", "KINV-B.ST"), ("KnowIT", "KNOW.ST"),
    ("Lagercrantz", "LAGR-B.ST"), ("Latour", "LATO-B.ST"), ("Lifco", "LIFCO-B.ST"),
    ("Lime Technologies", "LIME.ST"), ("Lindab", "LIAB.ST"), ("Loomis", "LOOMIS.ST"),
    ("Lundbergforetagen", "LUND-B.ST"), ("Lundin Gold", "LUG.ST"), ("Lundin Mining", "LUMI.ST"),
    ("MEKO", "MEKO.ST"), ("Malmbergs Elektriska", "MEAB-B.ST"), ("MedCap", "MCAP.ST"),
    ("Medicover", "MCOV-B.ST"), ("Midsona B", "MSON-B.ST"), ("Mildef Group", "MILDEF.ST"),
    ("Mips", "MIPS.ST"), ("Modern Times Group B", "MTG-B.ST"), ("Momentum Group", "MMGR-B.ST"),
    ("Munters", "MTRS.ST"), ("Mycronic", "MYCR.ST"), ("NCAB Group", "NCAB.ST"),
    ("NCC B", "NCC-B.ST"), ("NIBE Industrier", "NIBE-B.ST"), ("NOTE", "NOTE.ST"),
    ("NP3 Fastigheter", "NP3.ST"), ("Nederman", "NMAN.ST"), ("Nelly Group", "NELLY.ST"),
    ("Neobo Fastigheter", "NEOBO.ST"), ("New Wave", "NEWA-B.ST"), ("Nobia", "NOBI.ST"),
    ("Nolato", "NOLA-B.ST"), ("Nordea Bank", "NDA-SE.ST"), ("Nordnet", "SAVE.ST"),
    ("Nyfosa", "NYF.ST"), ("OEM International", "OEM-B.ST"), ("Orexo", "ORX.ST"),
    ("Orron Energy", "ORRON.ST"), ("Pandox", "PNDX-B.ST"), ("Peab", "PEAB-B.ST"),
    ("Platzer Fastigheter", "PLAZ-B.ST"), ("Pricer", "PRIC-B.ST"), ("Proact IT", "PACT.ST"),
    ("Profoto", "PRFO.ST"), ("Ratos B", "RATO-B.ST"), ("RaySearch Laboratories", "RAY-B.ST"),
    ("Rejlers", "REJL-B.ST"), ("Revolutionrace", "RVRC.ST"), ("Rottneros", "RROS.ST"),
    ("Rusta", "RUSTA.ST"), ("SCA B", "SCA-B.ST"), ("SEB C", "SEB-C.ST"),
    ("SKF B", "SKF-B.ST"), ("SSAB B", "SSAB-B.ST"), ("Saab", "SAAB-B.ST"),
    ("Sagax B", "SAGA-B.ST"), ("Sandvik", "SAND.ST"), ("Scandi Standard", "SCST.ST"),
    ("Scandic Hotels", "SHOT.ST"), ("Sdiptech", "SDIP-B.ST"), ("Sectra", "SECT-B.ST"),
    ("Securitas", "SECU-B.ST"), ("Sinch", "SINCH.ST"), ("Skanska", "SKA-B.ST"),
    ("SkiStar", "SKIS-B.ST"), ("Storskogen", "STOR-B.ST"), ("Stora Enso R", "STE-R.ST"),
    ("Sweco B", "SWEC-B.ST"), ("Swedbank", "SWED-A.ST"), ("Swedish Logistic Property", "SLP-B.ST"),
    ("Swedish Orphan Biovitrum", "SOBI.ST"), ("Systemair", "SYSR.ST"), ("TF Bank", "TFBANK.ST"),
    ("Tele2 B", "TEL2-B.ST"), ("Telia Company", "TELIA.ST"), ("Thule", "THULE.ST"),
    ("TietoEVRY", "TIETOS.ST"), ("Trelleborg", "TREL-B.ST"), ("Troax Group", "TROAX.ST"),
    ("Truecaller", "TRUE-B.ST"), ("VBG Group", "VBG-B.ST"), ("VNV Global", "VNV.ST"),
    ("Vitec Software", "VIT-B.ST"), ("Vitrolife", "VITR.ST"), ("Volati", "VOLO.ST"),
    ("Volvo B", "VOLV-B.ST"), ("Volvo Car", "VOLCAR-B.ST"), ("Wallenstam", "WALL-B.ST"),
    ("Wihlborgs Fastigheter", "WIHL.ST"), ("XANO Industri", "XANO-B.ST"),
    ("Xvivo Perfusion", "XVIVO.ST"), ("Yubico", "YUBICO.ST"), ("eWork", "EWRK.ST"),
    ("Oresund", "ORES.ST"),
]

RSL_PERIOD = 130  # trading days (~26 weeks)
OUTPUT_JSON = "screener_data.json"
PREV_RANKS_FILE = "prev_ranks.json"


def compute_rsl(tickers, period=130):
    results = []
    skipped = []
    total = len(tickers)

    end_date   = datetime.datetime.today()
    start_date = end_date - datetime.timedelta(days=400)

    print("=" * 65)
    print("  Levy RSL Screener — OMX Stockholm")
    print("  Universe: " + str(total) + " tickers (Large + Mid + Small Cap)")
    print("  Running at: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 65)
    print("")

    for i, (name, symbol) in enumerate(tickers):
        print("[" + str(i + 1).rjust(3) + "/" + str(total) + "] " + symbol.ljust(20), end="", flush=True)

        try:
            stock = yf.Ticker(symbol)
            hist  = stock.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                auto_adjust=True
            )

            if hist.empty or len(hist) == 0:
                skipped.append({
                    "name": name, "ticker": symbol,
                    "reason": "No price data returned", "days_available": 0
                })
                print("X  No price data")
                time.sleep(0.3)
                continue

            series = hist["Close"].dropna()
            days   = len(series)

            if days < period:
                skipped.append({
                    "name": name, "ticker": symbol,
                    "reason": "Insufficient history - needs " + str(period) + " days, only " + str(days) + " available",
                    "days_available": days
                })
                print("X  Only " + str(days) + "/" + str(period) + " days of history")
                time.sleep(0.3)
                continue

            current_price = float(series.iloc[-1])
            sma           = float(series.iloc[-period:].mean())
            rsl           = current_price / sma

            results.append({
                "name":   name,
                "ticker": symbol,
                "price":  round(current_price, 2),
                "sma130": round(sma, 2),
                "rsl":    round(rsl, 4),
            })

            print("OK  Price=" + str(round(current_price, 2)).rjust(9) +
                  "  SMA130=" + str(round(sma, 2)).rjust(9) +
                  "  RSL=" + str(round(rsl, 4)))

        except Exception as e:
            skipped.append({
                "name": name, "ticker": symbol,
                "reason": "Error: " + str(e)[:60], "days_available": 0
            })
            print("X  " + str(e)[:50])

        time.sleep(0.3)

    print("")
    print("-" * 65)
    print("  Valid: " + str(len(results)) + " stocks   Skipped: " + str(len(skipped)))
    print("-" * 65)

    results.sort(key=lambda x: x["rsl"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    skipped.sort(key=lambda x: x["days_available"])
    return results, skipped


def load_prev_ranks():
    if os.path.exists(PREV_RANKS_FILE):
        with open(PREV_RANKS_FILE) as f:
            return json.load(f)
    return {}


def save_prev_ranks(top20):
    ranks = {r["ticker"]: r["rank"] for r in top20}
    with open(PREV_RANKS_FILE, "w") as f:
        json.dump(ranks, f)


def main():
    now = datetime.datetime.now(datetime.timezone.utc)

    all_stocks, skipped = compute_rsl(TICKERS, RSL_PERIOD)
    top20 = all_stocks[:20]

    prev_ranks = load_prev_ranks()
    for r in top20:
        r["prev_rank"] = prev_ranks.get(r["ticker"], None)

    save_prev_ranks(top20)

    not_found  = [s for s in skipped if s["days_available"] == 0 and "Not found" in s["reason"]]
    no_data    = [s for s in skipped if s["days_available"] == 0 and "No price" in s["reason"]]
    short_hist = [s for s in skipped if s["days_available"] > 0]
    errors     = [s for s in skipped if "Error:" in s["reason"]]

    print("")
    print("--- SKIP SUMMARY ---")
    print("  Total attempted     : " + str(len(TICKERS)))
    print("  Successfully loaded : " + str(len(all_stocks)))
    print("  Skipped total       : " + str(len(skipped)))
    print("    Not found on Yahoo Finance   : " + str(len(not_found)))
    print("    No price data                : " + str(len(no_data)))
    print("    Insufficient history <130d   : " + str(len(short_hist)))
    print("    Other errors                 : " + str(len(errors)))

    output = {
        "updated":         now.strftime("%Y-%m-%d %H:%M UTC"),
        "period_days":     RSL_PERIOD,
        "total_attempted": len(TICKERS),
        "stocks_screened": len(all_stocks),
        "skipped_count":   len(skipped),
        "top20":           top20,
        "skipped":         skipped,
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("")
    print("=" * 65)
    print("  TOP 20 — LEVY RSL RANKING")
    print("=" * 65)
    for r in top20:
        prev = "(prev #" + str(r["prev_rank"]) + ")" if r["prev_rank"] else "(new)"
        print("  #" + str(r["rank"]).rjust(2) + "  RSL=" + str(r["rsl"]) +
              "  " + r["name"] + "  " + prev)

    print("")
    print("Saved " + OUTPUT_JSON)


if __name__ == "__main__":
    main()
