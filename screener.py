#!/usr/bin/env python3
"""
Levy RSL Momentum Screener for Swedish Stocks
Computes Relative Strength Levy (RSL) = Current Price / 130-day (26-week) SMA
Ranks all stocks, saves top 25 + full skip log to JSON for the webpage.

Universe sourced from Börsdata — Swedish listed companies only.
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

# ── Universe: Swedish-listed companies from Börsdata 2026-03-04 ────────────
# Norwegian companies (Frontline, Höegh Autoliners, Kongsberg, BW Energy etc.)
# and other non-Swedish names have been removed.
TICKERS = [
    ("AAK",                      "AAK.ST"),
    ("ABB",                      "ABB.ST"),
    ("AFRY",                     "AFRY.ST"),
    ("AQ Group",                 "AQ.ST"),
    ("AcadeMedia",               "ACAD.ST"),
    ("Acast",                    "ACAST.ST"),
    ("Actic Group",              "ATIC.ST"),
    ("Active Biotech",           "ACTI.ST"),
    ("AddLife",                  "ALIF-B.ST"),
    ("Addnode",                  "ANOD-B.ST"),
    ("Addtech",                  "ADDT-B.ST"),
    ("Alfa Laval",               "ALFA.ST"),
    ("Alimak",                   "ALIG.ST"),
    ("Alleima",                  "ALLEI.ST"),
    ("Alligator Bioscience",     "ATORX.ST"),
    ("Alligo",                   "ALLIGO-B.ST"),
    ("Alvotech SDB",             "ALVO-SDB.ST"),
    ("Ambea",                    "AMBEA.ST"),
    ("Anoto",                    "ANOT.ST"),
    ("Apotea",                   "APOTEA.ST"),
    ("Arctic Paper",             "ARP.ST"),
    ("Arjo",                     "ARJO-B.ST"),
    ("Arla Plast",               "ARPL.ST"),
    ("Ascelia Pharma",           "ACE.ST"),
    ("Asker Healthcare",         "ASKER.ST"),
    ("Asmodee",                  "ASMDEE-B.ST"),
    ("Assa Abloy",               "ASSA-B.ST"),
    ("AstraZeneca",              "AZN.ST"),
    ("Atlas Copco A",            "ATCO-A.ST"),
    ("Atlas Copco B",            "ATCO-B.ST"),
    ("Attendo",                  "ATT.ST"),
    ("Autoliv",                  "ALIV-SDB.ST"),
    ("Axfood",                   "AXFO.ST"),
    ("B3 Consulting",            "B3.ST"),
    ("BE Group",                 "BEGR.ST"),
    ("BHG Group",                "BHG.ST"),
    ("BICO Group",               "BICO.ST"),
    ("BTS Group",                "BTS-B.ST"),
    ("Bactiguard",               "BACTI-B.ST"),
    ("Balco Group",              "BALCO.ST"),
    ("Beijer Alma",              "BEIA-B.ST"),
    ("Beijer Ref",               "BEIJ-B.ST"),
    ("Bergman & Beving",         "BERG-B.ST"),
    ("Berner Industrier",        "BERNER-B.ST"),
    ("Betsson",                  "BETS-B.ST"),
    ("Better Collective",        "BETCO.ST"),
    ("Bilia",                    "BILI-A.ST"),
    ("Billerud",                 "BILL.ST"),
    ("BioArctic",                "BIOA-B.ST"),
    ("BioGaia",                  "BIOG-B.ST"),
    ("Bioinvent",                "BINV.ST"),
    ("Björn Borg",               "BORG.ST"),
    ("Boliden",                  "BOL.ST"),
    ("Bonesupport",              "BONEX.ST"),
    ("Bong Ljungdahl",           "BONG.ST"),
    ("Boozt",                    "BOOZT.ST"),
    ("Boule Diagnostics",        "BOUL.ST"),
    ("Bravida",                  "BRAV.ST"),
    ("Bufab",                    "BUFAB.ST"),
    ("Bulten",                   "BULTEN.ST"),
    ("Byggmax",                  "BMAX.ST"),
    ("C-RAD",                    "CRAD-B.ST"),
    ("CTEK",                     "CTEK.ST"),
    ("CTT Systems",              "CTT.ST"),
    ("Camurus",                  "CAMX.ST"),
    ("Cantargia",                "CANTA.ST"),
    ("Carasent",                 "CARA.ST"),
    ("Catena Media",             "CTM.ST"),
    ("Cavotec",                  "CCC.ST"),
    ("CellaVision",              "CEVI.ST"),
    ("Cinclus Pharma",           "CINPHA.ST"),
    ("Cint Group",               "CINT.ST"),
    ("Clas Ohlson",              "CLAS-B.ST"),
    ("Cloetta",                  "CLA-B.ST"),
    ("CoinShares",               "CS.ST"),
    ("Concejo B",                "CNCJO-B.ST"),
    ("Coor Service Management",  "COOR.ST"),
    ("Dedicare",                 "DEDI.ST"),
    ("Dometic",                  "DOM.ST"),
    ("Duni",                     "DUNI.ST"),
    ("Duroc",                    "DURC-B.ST"),
    ("Dustin Group",             "DUST.ST"),
    ("Dynavox Group",            "DYVOX.ST"),
    ("EQL Pharma",               "EQL.ST"),
    ("Egetis Therapeutics",      "EGTX.ST"),
    ("Elanders",                 "ELAN-B.ST"),
    ("Electrolux B",             "ELUX-B.ST"),
    ("Electrolux Professional B","EPRO-B.ST"),
    ("Elekta",                   "EKTA-B.ST"),
    ("Elon",                     "ELON.ST"),
    ("Eltel",                    "ELTEL.ST"),
    ("Embracer",                 "EMBRAC-B.ST"),
    ("Enad Global 7",            "EG7.ST"),
    ("Enea",                     "ENEA.ST"),
    ("Engcon",                   "ENGCON-B.ST"),
    ("Eniro",                    "ENRO.ST"),
    ("Eolus",                    "EOLU-B.ST"),
    ("Ependion",                 "EPEN.ST"),
    ("Epiroc B",                 "EPI-B.ST"),
    ("Episurf Medical",          "EPIS-B.ST"),
    ("Ericsson B",               "ERIC-B.ST"),
    ("Essity B",                 "ESSITY-B.ST"),
    ("Evolution",                "EVO.ST"),
    ("FM Mattsson",              "FMM-B.ST"),
    ("Fagerhult",                "FAG.ST"),
    ("Fasadgruppen",             "FG.ST"),
    ("Fenix Outdoor",            "FOI-B.ST"),
    ("Ferronordic",              "FNM.ST"),
    ("Fingerprint Cards",        "FING-B.ST"),
    ("Flerie",                   "FLERIE.ST"),
    ("Formpipe Software",        "FPIP.ST"),
    ("G5 Entertainment",         "G5EN.ST"),
    ("Garo",                     "GARO.ST"),
    ("Gentoo Media",             "G2M.ST"),
    ("Getinge",                  "GETI-B.ST"),
    ("Green Landscaping",        "GREEN.ST"),
    ("Gruvaktiebolaget Viscaria","VISC.ST"),
    ("Gränges",                  "GRNG.ST"),
    ("HMS Networks",             "HMS.ST"),
    ("Hacksaw",                  "HACK.ST"),
    ("Hansa Biopharma",          "HNSA.ST"),
    ("Hanza",                    "HANZA.ST"),
    ("Hemnet",                   "HEM.ST"),
    ("Hennes & Mauritz",         "HM-B.ST"),
    ("Hexagon",                  "HEXA-B.ST"),
    ("Hexatronic",               "HTRO.ST"),
    ("Hexpol",                   "HPOL-B.ST"),
    ("Holmen B",                 "HOLM-B.ST"),
    ("Humana",                   "HUM.ST"),
    ("Humble Group",             "HUMBLE.ST"),
    ("Husqvarna B",              "HUSQ-B.ST"),
    ("IRLAB Therapeutics",       "IRLAB-A.ST"),
    ("ITAB Shop Concept",        "ITAB.ST"),
    ("Image Systems",            "IS.ST"),
    ("Immunovia",                "IMMNOV.ST"),
    ("Indutrade",                "INDT.ST"),
    ("Infant Bacterial",         "IBT-B.ST"),
    ("Infrea",                   "INFREA.ST"),
    ("Inission",                 "INISS-B.ST"),
    ("Instalco",                 "INSTAL.ST"),
    ("International Petroleum",  "IPCO.ST"),
    ("Invisio",                  "IVSO.ST"),
    ("Inwido",                   "INWI.ST"),
    ("Isofol Medical",           "ISOFOL.ST"),
    ("JM",                       "JM.ST"),
    ("Kabe",                     "KABE-B.ST"),
    ("Karnell Group",            "KARNEL-B.ST"),
    ("Karnov",                   "KAR.ST"),
    ("KnowIT",                   "KNOW.ST"),
    ("Lagercrantz",              "LAGR-B.ST"),
    ("Lammhults Design",         "LAMM-B.ST"),
    ("Lifco",                    "LIFCO-B.ST"),
    ("Lime Technologies",        "LIME.ST"),
    ("Lindab",                   "LIAB.ST"),
    ("Loomis",                   "LOOMIS.ST"),
    ("Lundin Gold",              "LUG.ST"),
    ("Lundin Mining",            "LUMI.ST"),
    ("MEKO",                     "MEKO.ST"),
    ("Maha Capital",             "MAHA-A.ST"),
    ("Malmbergs Elektriska",     "MEAB-B.ST"),
    ("MedCap",                   "MCAP.ST"),
    ("Medicover",                "MCOV-B.ST"),
    ("Medivir",                  "MVIR.ST"),
    ("Mendus",                   "IMMU.ST"),
    ("Meren Energy",             "MER.ST"),
    ("Micro Systemation",        "MSAB-B.ST"),
    ("Midsona B",                "MSON-B.ST"),
    ("Mildef Group",             "MILDEF.ST"),
    ("Mips",                     "MIPS.ST"),
    ("Moberg Pharma",            "MOB.ST"),
    ("Modern Times Group B",     "MTG-B.ST"),
    ("Moment Group",             "MOMENT.ST"),
    ("Momentum Group",           "MMGR-B.ST"),
    ("Munters",                  "MTRS.ST"),
    ("Mycronic",                 "MYCR.ST"),
    ("NCAB Group",               "NCAB.ST"),
    ("NCC B",                    "NCC-B.ST"),
    ("NIBE Industrier",          "NIBE-B.ST"),
    ("NOTE",                     "NOTE.ST"),
    ("Nanologica",               "NICA.ST"),
    ("Nederman",                 "NMAN.ST"),
    ("Nelly Group",              "NELLY.ST"),
    ("Net Insight",              "NETI-B.ST"),
    ("Netel Holding",            "NETEL.ST"),
    ("New Wave",                 "NEWA-B.ST"),
    ("Nilörngruppen",            "NIL-B.ST"),
    ("Nobia",                    "NOBI.ST"),
    ("Nokia",                    "NOKIA-SEK.ST"),
    ("Nolato",                   "NOLA-B.ST"),
    ("Nordisk Bergteknik",       "NORB-B.ST"),
    ("Novotek",                  "NTEK-B.ST"),
    ("OEM International",        "OEM-B.ST"),
    ("Oncopeptides",             "ONCO.ST"),
    ("Orexo",                    "ORX.ST"),
    ("Orrön Energy",             "ORRON.ST"),
    ("Ovzon",                    "OVZON.ST"),
    ("PION Group",               "PION-B.ST"),
    ("Peab",                     "PEAB-B.ST"),
    ("Pierce Group",             "PIERCE.ST"),
    ("PowerCell",                "PCELL.ST"),
    ("Precise Biometrics",       "PREC.ST"),
    ("Prevas",                   "PREV-B.ST"),
    ("Pricer",                   "PRIC-B.ST"),
    ("Proact IT",                "PACT.ST"),
    ("ProfilGruppen",            "PROF-B.ST"),
    ("Profoto",                  "PRFO.ST"),
    ("Q-Linea",                  "QLINEA.ST"),
    ("Railcare",                 "RAIL.ST"),
    ("RaySearch Laboratories",   "RAY-B.ST"),
    ("Rejlers",                  "REJL-B.ST"),
    ("Revolutionrace",           "RVRC.ST"),
    ("Rottneros",                "RROS.ST"),
    ("Rusta",                    "RUSTA.ST"),
    ("SCA B",                    "SCA-B.ST"),
    ("SKF B",                    "SKF-B.ST"),
    ("SSAB B",                   "SSAB-B.ST"),
    ("Saab",                     "SAAB-B.ST"),
    ("Sandvik",                  "SAND.ST"),
    ("Saniona",                  "SANION.ST"),
    ("Scandi Standard",          "SCST.ST"),
    ("Scandic Hotels",           "SHOT.ST"),
    ("Sdiptech",                 "SDIP-B.ST"),
    ("Sectra",                   "SECT-B.ST"),
    ("Securitas",                "SECU-B.ST"),
    ("Sedana Medical",           "SEDANA.ST"),
    ("Sensys Gatso",             "SGG.ST"),
    ("Senzime",                  "SEZI.ST"),
    ("Sinch",                    "SINCH.ST"),
    ("SinterCast",               "SINT.ST"),
    ("Sivers Semiconductors",    "SIVE.ST"),
    ("Skanska",                  "SKA-B.ST"),
    ("SkiStar",                  "SKIS-B.ST"),
    ("Sleep Cycle",              "SLEEP.ST"),
    ("Softronic",                "SOF-B.ST"),
    ("Starbreeze B",             "STAR-B.ST"),
    ("Stillfront",               "SF.ST"),
    ("Stora Enso R",             "STE-R.ST"),
    ("Studsvik",                 "SVIK.ST"),
    ("Svedbergs Group",          "SVED-B.ST"),
    ("Sweco B",                  "SWEC-B.ST"),
    ("Swedish Orphan Biovitrum", "SOBI.ST"),
    ("SynAct Pharma",            "SYNACT.ST"),
    ("Synsam",                   "SYNSAM.ST"),
    ("Systemair",                "SYSR.ST"),
    ("Tele2 B",                  "TEL2-B.ST"),
    ("Telia Company",            "TELIA.ST"),
    ("Thule",                    "THULE.ST"),
    ("TietoEVRY",                "TIETOS.ST"),
    ("Tobii",                    "TOBII.ST"),
    ("TradeDoubler",             "TRAD.ST"),
    ("Transtema",                "TRANS.ST"),
    ("Traton",                   "8TRA.ST"),
    ("Trelleborg",               "TREL-B.ST"),
    ("Troax Group",              "TROAX.ST"),
    ("Truecaller",               "TRUE-B.ST"),
    ("VBG Group",                "VBG-B.ST"),
    ("Verisure",                 "VSURE.ST"),
    ("Viaplay B",                "VPLAY-B.ST"),
    ("Vicore Pharma",            "VICO.ST"),
    ("Vimian Group",             "VIMIAN.ST"),
    ("Vitec Software",           "VIT-B.ST"),
    ("Vitrolife",                "VITR.ST"),
    ("Viva Wine",                "VIVA.ST"),
    ("Vivesto",                  "VIVE.ST"),
    ("Volvo B",                  "VOLV-B.ST"),
    ("Volvo Car",                "VOLCAR-B.ST"),
    ("Wall to Wall",             "WTW-A.ST"),
    ("Wise Group",               "WISE.ST"),
    ("Wästbygg",                 "WBGR-B.ST"),
    ("XANO Industri",            "XANO-B.ST"),
    ("Xbrane Biopharma",         "XBRANE.ST"),
    ("Xspray Pharma",            "XSPRAY.ST"),
    ("Xvivo Perfusion",          "XVIVO.ST"),
    ("Yubico",                   "YUBICO.ST"),
    ("eWork",                    "EWRK.ST"),
    ("mySafety",                 "SAFETY-B.ST"),
]

RSL_PERIOD      = 130   # trading days (~26 weeks)
TOP_N           = 25    # ← extended from 20 to 25
OUTPUT_JSON     = "screener_data.json"
PREV_RANKS_FILE = "prev_ranks.json"


def compute_rsl(tickers, period=130):
    results, skipped = [], []
    total      = len(tickers)
    end_date   = datetime.datetime.today()
    start_date = end_date - datetime.timedelta(days=400)

    print("=" * 65)
    print("  Levy RSL Screener — Nasdaq Stockholm (Swedish only)")
    print(f"  Universe: {total} tickers  |  Top {TOP_N} output")
    print(f"  Running at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 65 + "\n")

    for i, (name, symbol) in enumerate(tickers):
        print(f"[{i+1:>3}/{total}] {symbol:<22}", end="", flush=True)
        try:
            hist = yf.Ticker(symbol).history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                auto_adjust=True
            )
            if hist.empty:
                skipped.append({"name": name, "ticker": symbol, "reason": "No price data returned", "days_available": 0})
                print("✗  No price data")
                time.sleep(0.3); continue

            series = hist["Close"].dropna()
            days   = len(series)
            if days < period:
                skipped.append({"name": name, "ticker": symbol,
                                 "reason": f"Insufficient history — needs {period} days, only {days} available",
                                 "days_available": days})
                print(f"✗  Only {days}/{period} days")
                time.sleep(0.3); continue

            price  = float(series.iloc[-1])
            sma130 = float(series.iloc[-period:].mean())
            rsl    = price / sma130

            results.append({"name": name, "ticker": symbol,
                             "price": round(price, 2), "sma130": round(sma130, 2),
                             "rsl": round(rsl, 4)})
            print(f"✓  Price={price:>9.2f}  SMA130={sma130:>9.2f}  RSL={rsl:.4f}")
        except Exception as e:
            skipped.append({"name": name, "ticker": symbol, "reason": f"Error: {str(e)[:60]}", "days_available": 0})
            print(f"✗  {str(e)[:50]}")
        time.sleep(0.3)

    print(f"\n{'-'*65}")
    print(f"  Valid: {len(results)}   Skipped: {len(skipped)}")
    print(f"{'-'*65}")

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


def save_prev_ranks(top_n):
    with open(PREV_RANKS_FILE, "w") as f:
        json.dump({r["ticker"]: r["rank"] for r in top_n}, f)


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    all_stocks, skipped = compute_rsl(TICKERS, RSL_PERIOD)
    top_n = all_stocks[:TOP_N]

    prev_ranks = load_prev_ranks()
    for r in top_n:
        r["prev_rank"] = prev_ranks.get(r["ticker"], None)
    save_prev_ranks(top_n)

    output = {
        "updated":         now.strftime("%Y-%m-%d %H:%M UTC"),
        "period_days":     RSL_PERIOD,
        "total_attempted": len(TICKERS),
        "stocks_screened": len(all_stocks),
        "skipped_count":   len(skipped),
        "top25":           top_n,        # ← key is now top25
        "skipped":         skipped,
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*65}")
    print(f"  TOP {TOP_N} — LEVY RSL RANKING")
    print(f"{'='*65}")
    for r in top_n:
        prev = f"(prev #{r['prev_rank']})" if r["prev_rank"] else "(new)"
        print(f"  #{r['rank']:>2}  RSL={r['rsl']}  {r['name']}  {prev}")
    print(f"\n✅  Saved → {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
