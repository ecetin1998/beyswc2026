"""
BEYSWC2026 — canlı tahmin ligi paneli
Veri kaynağı: openfootball (key gerekmez), 2026 Dünya Kupası maç sonuçları.
Grup sıralaması maç skorlarından FIFA kriterleriyle HESAPLANIR
(puan > ikili maç (puan>averaj>gol) > genel averaj > genel gol).
Çalıştır:  streamlit run app.py
"""
import csv
import os
from collections import Counter, defaultdict

import requests
import streamlit as st
import pandas as pd

import config as C

CSV_PATH = os.path.join(os.path.dirname(__file__), "tahminler.csv")
DATA_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
GROUPS = [f"Grup {h}" for h in "ABCDEFGHIJKL"]

st.set_page_config(page_title="BEYSWC2026", page_icon="🏆", layout="wide")


# ---------------------------------------------------------------------------
# Tahminler
# ---------------------------------------------------------------------------
@st.cache_data
def load_predictions():
    preds = {p: defaultdict(dict) for p in C.PLAYERS}
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="|"):
            asama = row["asama"].strip()
            poz = int(row["pozisyon"])
            for p in C.PLAYERS:
                preds[p][asama][poz] = row[p].strip()
    return preds


def ordered(asama_dict, asama):
    d = asama_dict.get(asama, {})
    return [d[k] for k in sorted(d)]


def pairs_from(asama_dict, asama):
    teams = ordered(asama_dict, asama)
    return [frozenset({teams[i], teams[i + 1]}) for i in range(0, len(teams) - 1, 2)]


# ---------------------------------------------------------------------------
# Veri çek
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_matches(_nonce=0):
    r = requests.get(DATA_URL, timeout=20)
    r.raise_for_status()
    return r.json().get("matches", [])


def classify_round(round_str):
    rl = C.normalize(round_str)
    if "32" in rl:
        return "Son 32"
    if "16" in rl:
        return "Son 16"
    if "quarter" in rl:
        return "Ceyrek Final"
    if "semi" in rl:
        return "Yari Final"
    if "3rd" in rl or "third" in rl or "play off" in rl or "playoff" in rl:
        return "3rd"
    if "final" in rl:
        return "Final"
    return None


def ko_winner(m):
    sc = m.get("score") or {}
    ft = sc.get("ft")
    if not ft:
        return None
    a, b = ft
    t1, t2 = C.to_tr_token(m["team1"]), C.to_tr_token(m["team2"])
    if a > b:
        return t1
    if b > a:
        return t2
    for k in ("p", "pen", "pens", "ps", "penalties"):  # uzatma/penaltı
        if sc.get(k):
            pa, pb = sc[k]
            return t1 if pa > pb else t2
    return None


# ---------------------------------------------------------------------------
# Grup sıralaması (FIFA kriterleri ile hesaplanır)
# ---------------------------------------------------------------------------
def compute_standings(matches):
    """{grup: [ {tr,rank,pts,gd,gf,played}... ]} — puan>ikili maç>genel averaj>genel gol>FIFA sırası."""
    table = defaultdict(lambda: defaultdict(lambda: {"pts": 0, "gf": 0, "ga": 0, "pl": 0}))
    played_in_group = defaultdict(list)  # grup -> [(t1,t2,a,b)]
    for m in matches:
        g = (m.get("group") or "").replace("Group", "Grup").strip()
        sc = m.get("score") or {}
        ft = sc.get("ft")
        if not g or not ft:
            continue
        t1, t2 = C.to_tr_token(m["team1"]), C.to_tr_token(m["team2"])
        if not t1 or not t2:
            continue
        a, b = ft
        played_in_group[g].append((t1, t2, a, b))
        for tt, gf, ga in ((t1, a, b), (t2, b, a)):
            s = table[g][tt]
            s["gf"] += gf; s["ga"] += ga; s["pl"] += 1
            s["pts"] += 3 if gf > ga else (1 if gf == ga else 0)

    def mini_table(subset, gmatches):
        """Yalnızca alt-kümedeki takımların kendi aralarındaki maçlardan tablo."""
        st = {t: {"pts": 0, "gd": 0, "gf": 0} for t in subset}
        for t1, t2, a, b in gmatches:
            if t1 in st and t2 in st:
                st[t1]["gf"] += a; st[t1]["gd"] += a - b
                st[t1]["pts"] += 3 if a > b else (1 if a == b else 0)
                st[t2]["gf"] += b; st[t2]["gd"] += b - a
                st[t2]["pts"] += 3 if b > a else (1 if a == b else 0)
        return st

    def order_tied(teams, gmatches, overall):
        """Puanı eşit takımları FIFA kriterleriyle sırala.
        1-3: ikili maç puan/averaj/gol  4: kalan eşitlere 1-3 tekrar
        5-6: genel averaj/gol  (7-9: fair play / FIFA sırası -> veri yok)."""
        if len(teams) == 1:
            return teams
        mt = mini_table(set(teams), gmatches)
        key = lambda t: (mt[t]["pts"], mt[t]["gd"], mt[t]["gf"])
        teams = sorted(teams, key=key, reverse=True)
        result, i = [], 0
        while i < len(teams):
            j = i
            while j + 1 < len(teams) and key(teams[j + 1]) == key(teams[i]):
                j += 1
            sub = teams[i:j + 1]
            if len(sub) == 1:
                result.extend(sub)
            elif len(sub) < len(teams):
                result.extend(order_tied(sub, gmatches, overall))   # madde 4: tekrar uygula
            else:
                # ikili maçta da tam eşit -> genel averaj, genel gol, FIFA sırası (madde 8)
                result.extend(sorted(sub, key=lambda t: (overall[t]["gd"], overall[t]["gf"],
                                                         -C.FIFA_RANK.get(t, 999)),
                                     reverse=True))
            i = j + 1
        return result

    out = {}
    for g, teams in table.items():
        overall = {tr: {"pts": s["pts"], "gd": s["gf"] - s["ga"], "gf": s["gf"],
                        "ga": s["ga"], "pl": s["pl"]} for tr, s in teams.items()}
        # önce toplam puana göre kümele, her puan kümesinde tiebreaker uygula
        by_pts = defaultdict(list)
        for tr in overall:
            by_pts[overall[tr]["pts"]].append(tr)
        ordered_teams = []
        for pts in sorted(by_pts, reverse=True):
            ordered_teams.extend(order_tied(by_pts[pts], played_in_group[g], overall))
        rows = []
        for rank, tr in enumerate(ordered_teams, 1):
            o = overall[tr]
            rows.append({"tr": tr, "rank": rank, "pts": o["pts"],
                         "gd": o["gd"], "gf": o["gf"], "played": o["pl"]})
        out[g] = rows
    return out


def rank_thirds(thirds):
    """12 grup üçüncüsünü kendi aralarında sırala: puan > averaj > atılan gol > FIFA sırası.
    (Farklı gruplarda oldukları için ikili maç kriteri uygulanmaz.)"""
    return sorted(thirds, key=lambda x: (x["pts"], x["gd"], x["gf"],
                                         -C.FIFA_RANK.get(x["tr"], 999)), reverse=True)


# ---------------------------------------------------------------------------
# Gerçek sonuçlar
# ---------------------------------------------------------------------------
def build_actuals(matches):
    actual = {"group": {}, "best_third": set(),
              "round_set": defaultdict(set), "pair_set": defaultdict(set),
              "champion": None}
    standings = compute_standings(matches)
    thirds = []
    for g, rows in standings.items():
        for r in rows:
            if 1 <= r["rank"] <= 4:
                actual["group"][(g, r["rank"])] = r["tr"]
            if r["rank"] == 3:
                thirds.append(r)

    by_round = defaultdict(list)
    for m in matches:
        if m.get("group"):          # grup maçı -> knockout değil
            continue
        rnd = classify_round(m.get("round", ""))
        if rnd:
            by_round[rnd].append(m)

    def teams_in(rnd):
        s = set()
        for m in by_round.get(rnd, []):
            for side in ("team1", "team2"):
                tr = C.to_tr_token(m[side])
                if tr:
                    s.add(tr)
        return s

    # en iyi 8 üçüncü: önce gerçek Son 32 katılımcıları, yoksa puan>averaj>gol ilk 8
    r32 = teams_in("Son 32")
    adv = {t["tr"] for t in thirds if t["tr"] in r32}
    if adv:
        actual["best_third"] = adv                       # API bracket'i belirtmiş (kesin)
    elif thirds:
        # 12 üçüncüyü tek grup gibi canlı sırala, ilk 8'i al (grup bitmesini beklemeden)
        actual["best_third"] = {t["tr"] for t in rank_thirds(thirds)[:8]}
    else:
        actual["best_third"] = set()

    # Son 32'ye kalanlar = her grubun ilk 2'si + en iyi 8 üçüncü (canlı türetilir)
    top2 = {r["tr"] for rs in standings.values() for r in rs if r["rank"] <= 2}
    actual["r32_set"] = top2 | actual["best_third"]

    for rnd in ["Son 16", "Ceyrek Final", "Yari Final", "Final"]:
        actual["round_set"][rnd] = teams_in(rnd)
    for m in by_round.get("Final", []):
        w = ko_winner(m)
        if w:
            actual["champion"] = w
    for rnd in C.KO_PAIR_POINTS:
        for m in by_round.get(rnd, []):
            h, a = C.to_tr_token(m["team1"]), C.to_tr_token(m["team2"])
            if h and a:
                actual["pair_set"][rnd].add(frozenset({h, a}))
    return actual


def demo_actuals(preds):
    actual = {"group": {}, "best_third": set(),
              "round_set": defaultdict(set), "pair_set": defaultdict(set),
              "champion": None}
    for g in GROUPS:
        for poz in (1, 2, 3, 4):
            votes = Counter(preds[p][g][poz] for p in C.PLAYERS)
            actual["group"][(g, poz)] = votes.most_common(1)[0][0]
    return actual


# ---------------------------------------------------------------------------
# Puanlama
# ---------------------------------------------------------------------------
def score_player(pp, actual):
    grp = ko_w = ko_p = b3 = 0
    for g in GROUPS:
        exact = True
        have_all = all((g, poz) in actual["group"] for poz in (1, 2, 3, 4))
        for poz in (1, 2, 3, 4):
            real = actual["group"].get((g, poz))
            if real is not None and pp[g].get(poz) == real:
                grp += C.GROUP_POINTS[poz]
            else:
                exact = False
        if have_all and exact:
            grp += C.GROUP_EXACT_BONUS
    if actual["best_third"]:
        b3 = len(set(ordered(pp, "En Iyi 3.ler")) & actual["best_third"]) * C.BEST_THIRD_POINTS
    for rnd, pts in C.KO_WINNER_POINTS.items():
        if rnd == "Sampiyon":
            continue
        rs = actual["round_set"].get(rnd, set())
        if rs:
            ko_w += len(set(ordered(pp, rnd)) & rs) * pts
    if actual["champion"] and pp.get("Sampiyon", {}).get(1) == actual["champion"]:
        ko_w += C.KO_WINNER_POINTS["Sampiyon"] + C.CHAMPION_BONUS
    for rnd, pts in C.KO_PAIR_POINTS.items():
        rp = actual["pair_set"].get(rnd, set())
        if rp:
            for pr in pairs_from(pp, rnd):
                if pr in rp:
                    ko_p += pts
    return {"Grup": grp, "En İyi 3": b3, "KO Kazanan": ko_w,
            "KO Pair": ko_p, "Toplam": grp + b3 + ko_w + ko_p}


# ---------------------------------------------------------------------------
# Arayüz
# ---------------------------------------------------------------------------
preds = load_predictions()

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');
:root{ --bg:#0B1220; --panel:#131C2E; --panel2:#18233a; --line:#243049;
  --tx:#E8EDF6; --mut:#8A97AD; --gold:#F5C451;
  --grp:#45B36B; --b3:#4C8DD6; --kw:#9B6DD6; --kp:#E6A23C; --red:#E5484D; }
.stApp{ background:
  radial-gradient(900px 420px at 50% -140px, rgba(245,196,81,.10), transparent 60%),
  radial-gradient(700px 480px at 10% 0, rgba(76,141,214,.08), transparent 55%), var(--bg);
  color:var(--tx); }
[data-testid="stToolbar"]{display:none;}
#MainMenu, footer{visibility:hidden;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1rem; max-width:880px;}
.hero{text-align:center; padding:6px 0 8px;}
.hero .cup{font-size:42px; filter:drop-shadow(0 0 18px rgba(245,196,81,.5));}
.hero h1{font-family:'Anton',sans-serif; font-size:clamp(40px,9vw,70px); letter-spacing:1px; margin:2px 0 0; line-height:.92;}
.hero .sub{color:var(--mut); font-family:'Inter',sans-serif; font-size:13px; margin:6px 0 12px;}
.pill{display:inline-block; font-family:'Inter',sans-serif; font-size:12px; background:var(--panel); border:1px solid var(--line); padding:5px 12px; border-radius:999px;}
.legend{display:flex; gap:14px; justify-content:center; flex-wrap:wrap; margin-top:12px; font-family:'Inter',sans-serif; font-size:11.5px; color:var(--mut);}
.legend span{display:inline-flex; align-items:center; gap:6px;}
.dot{width:9px; height:9px; border-radius:3px; display:inline-block;}
.dot.grp{background:var(--grp);} .dot.b3{background:var(--b3);} .dot.kw{background:var(--kw);} .dot.kp{background:var(--kp);}
.track{height:8px; border-radius:6px; background:#0c1424; border:1px solid var(--line); overflow:hidden; display:flex; margin-top:8px;}
.seg{height:100%;} .seg.grp{background:var(--grp);} .seg.b3{background:var(--b3);} .seg.kw{background:var(--kw);} .seg.kp{background:var(--kp);}
.podium{display:flex; gap:10px; align-items:flex-end; justify-content:center; margin:16px 0 8px;}
.pod{flex:1; max-width:240px; background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:14px 12px 16px; text-align:center;}
.pod.first{padding-top:22px; border-color:rgba(245,196,81,.55); background:linear-gradient(180deg, rgba(245,196,81,.14), var(--panel)); box-shadow:0 0 34px rgba(245,196,81,.16);}
.pod .medal{font-size:26px; line-height:1;}
.pod-name{font-family:'Inter',sans-serif; font-weight:600; font-size:14px; margin-top:6px;}
.pod-pts{font-family:'Space Grotesk',monospace; font-weight:700; font-size:30px;}
.pod.first .pod-pts{color:var(--gold);}
.pod .chips{justify-content:center;}
.board{display:flex; flex-direction:column; gap:8px; margin-top:12px;}
.row{display:flex; align-items:center; gap:12px; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px 14px;}
.row .pos{font-family:'Space Grotesk',monospace; font-weight:700; color:var(--mut); width:22px; text-align:center; font-size:15px;}
.row .info{flex:1; min-width:0;}
.row .name{font-family:'Inter',sans-serif; font-weight:600; font-size:14px;}
.chips{display:flex; gap:6px; flex-wrap:wrap; margin-top:7px;}
.chip{font-family:'Inter',sans-serif; font-size:10.5px; color:var(--mut); border:1px solid var(--line); border-radius:999px; padding:2px 8px;}
.chip.grp{border-color:rgba(69,179,107,.45);} .chip.b3{border-color:rgba(76,141,214,.45);} .chip.kw{border-color:rgba(155,109,214,.45);} .chip.kp{border-color:rgba(230,162,60,.45);}
.row .pts{font-family:'Space Grotesk',monospace; font-weight:700; font-size:22px;}
.row .pts span{font-size:11px; color:var(--mut); font-weight:500;}
.row.last{border-color:rgba(229,72,77,.5); background:linear-gradient(180deg, rgba(229,72,77,.11), var(--panel));}
.row.last .pos, .row.last .pts{color:var(--red);}
.ggrid{display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px;}
.gcard{background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden;}
.ghead{font-family:'Anton',sans-serif; letter-spacing:.5px; font-size:14px; padding:8px 12px; background:var(--panel2);}
.grow{display:flex; align-items:center; gap:8px; padding:6px 12px; font-family:'Inter',sans-serif; font-size:13px; border-top:1px solid var(--line);}
.grow .gp{width:18px; height:18px; border-radius:5px; font-size:11px; font-weight:700; display:flex; align-items:center; justify-content:center; color:#0B1220; background:var(--mut);}
.grow.q .gp{background:var(--grp); color:#08130c;} .grow.t3 .gp{background:var(--b3); color:#06121f;}
.grow.out{opacity:.42;}
.chiprow{display:flex; flex-wrap:wrap; gap:7px; align-items:center; margin:8px 0 2px;}
.chiprow b{font-family:'Inter',sans-serif; font-size:12px; color:var(--mut);}
.tchip{font-family:'Inter',sans-serif; font-size:12px; background:var(--panel); border:1px solid var(--line); border-radius:999px; padding:4px 10px;}
.tchip.hit{border-color:var(--grp); background:rgba(69,179,107,.14); color:#c7ecd4;}
.sec-title{font-family:'Anton',sans-serif; font-size:22px; letter-spacing:.5px; margin:26px 0 6px; text-align:center;}
.tn.hit{color:#c7ecd4;}
.tn.near{color:#f1b0b2;}
.rules{display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-top:4px;}
.rblock{background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden;}
.rblock .rhead{font-family:'Anton',sans-serif; letter-spacing:.5px; font-size:14px; padding:9px 12px; border-top:3px solid var(--mut);}
.rblock.grp .rhead{border-color:var(--grp);} .rblock.kw .rhead{border-color:var(--kw);} .rblock.kp .rhead{border-color:var(--kp);}
.rrow{display:flex; justify-content:space-between; gap:10px; padding:7px 12px; font-family:'Inter',sans-serif; font-size:13px; border-top:1px solid var(--line);}
.rrow span{color:var(--mut);} .rrow b{color:var(--tx); font-family:'Space Grotesk',monospace;}
.rnote{font-family:'Inter',sans-serif; font-size:11.5px; color:var(--mut); margin-top:10px; line-height:1.55;}
.kround{background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:11px 14px; margin-top:8px;}
.krhead{font-family:'Inter',sans-serif; font-weight:600; font-size:11.5px; letter-spacing:.7px; text-transform:uppercase; color:var(--mut); margin-bottom:9px; display:flex; align-items:center; gap:8px;}
.krcnt{font-family:'Space Grotesk',monospace; font-size:11px; color:var(--mut); background:var(--panel2); border:1px solid var(--line); border-radius:999px; padding:1px 7px;}
.kteams{display:flex; flex-wrap:wrap; gap:6px;}
.kteams.pairs{gap:8px;}
.matchup{display:inline-flex; align-items:center; gap:7px; background:var(--panel2); border:1px solid var(--line); border-radius:999px; padding:5px 12px; font-family:'Inter',sans-serif; font-size:12px;}
.matchup .mt{color:var(--tx);}
.matchup .mt.ok{color:#c7ecd4; font-weight:600;}
.matchup .mt.no{color:#f1b0b2;}
.matchup .vs{color:var(--mut); font-size:10px;}
.matchup.pairhit{border-color:var(--grp); background:rgba(69,179,107,.14);}
.matchup .mt.win{color:#c7ecd4; font-weight:700;}
.matchup .mt.lose{opacity:.4;}
.kround.champ{border-color:rgba(245,196,81,.5); background:linear-gradient(180deg, rgba(245,196,81,.10), var(--panel));}
.kround.champ .krhead{color:var(--gold);}
.kround.champ .tchip{border-color:var(--gold); color:var(--gold); font-weight:600;}
@media(max-width:560px){ .pod-pts{font-size:23px;} .podium{gap:6px;} .pod{padding:10px 6px 12px;} }
</style>"""
st.markdown(CSS, unsafe_allow_html=True)

CAT = [("Grup", "grp"), ("En İyi 3", "b3"), ("KO Kazanan", "kw"), ("KO Pair", "kp")]


def _bar(r):
    segs = ""
    for label, cls in CAT:
        w = r[label] / 1000 * 100
        if w > 0:
            segs += f'<span class="seg {cls}" style="width:{w:.3f}%"></span>'
    return f'<div class="track">{segs}</div>'


def _chips(r):
    return ('<div class="chips">'
            f'<span class="chip grp">Grup {r["Grup"]}</span>'
            f'<span class="chip b3">3.ler {r["En İyi 3"]}</span>'
            f'<span class="chip kw">KO {r["KO Kazanan"]}</span>'
            f'<span class="chip kp">Pair {r["KO Pair"]}</span></div>')


def podium_html(top):
    medal = {0: "🥇", 1: "🥈", 2: "🥉"}
    place = {0: "first", 1: "second", 2: "third"}
    cards = ""
    for idx in (1, 0, 2):
        if idx >= len(top):
            continue
        r = top[idx]
        cards += (f'<div class="pod {place[idx]}"><div class="medal">{medal[idx]}</div>'
                  f'<div class="pod-name">{r["Oyuncu"]}</div>'
                  f'<div class="pod-pts">{r["Toplam"]}</div>{_bar(r)}{_chips(r)}</div>')
    return f'<div class="podium">{cards}</div>'


def board_html(rest, start):
    items = ""
    n = len(rest)
    for i, r in enumerate(rest):
        cls = "row last" if i == n - 1 else "row"
        items += (f'<div class="{cls}"><div class="pos">{start + i}</div>'
                  f'<div class="info"><div class="name">{r["Oyuncu"]}</div>'
                  f'{_bar(r)}{_chips(r)}</div>'
                  f'<div class="pts">{r["Toplam"]}<span>/1000</span></div></div>')
    return f'<div class="board">{items}</div>'


def groups_html(actual):
    bt = actual["best_third"]
    cards = ""
    for g in GROUPS:
        grows = ""
        for poz in (1, 2, 3, 4):
            t = actual["group"].get((g, poz), "—")
            if poz <= 2:
                adv = "q"
            elif poz == 3:
                adv = "t3" if t in bt else "out"
            else:
                adv = "out"
            grows += (f'<div class="grow {adv}"><span class="gp">{poz}</span>'
                      f'<span class="tn">{t}</span></div>')
        cards += f'<div class="gcard"><div class="ghead">{g}</div>{grows}</div>'
    return f'<div class="ggrid">{cards}</div>'


def rules_html():
    g, w, pr = C.GROUP_POINTS, C.KO_WINNER_POINTS, C.KO_PAIR_POINTS
    grp = [("1. sıra doğru", g[1]), ("2. sıra", g[2]), ("3. sıra", g[3]),
           ("4. sıra", g[4]), ("Tam sıra (1-2-3-4) bonus", C.GROUP_EXACT_BONUS)]
    ko = [("Her doğru 'en iyi 3.'", C.BEST_THIRD_POINTS),
          ("Son 16'ya kalan (R32 kazananı)", w["Son 16"]),
          ("Çeyreğe kalan (R16 kazananı)", w["Ceyrek Final"]),
          ("Yarıya kalan (çeyrek kazananı)", w["Yari Final"]),
          ("Finale kalan (yarı kazananı)", w["Final"]),
          ("Final kazananı (şampiyon)", w["Sampiyon"]),
          ("Şampiyon bonusu", C.CHAMPION_BONUS)]
    pair = [("Son 32 eşleşmesi", pr["Son 32"]), ("Son 16 eşleşmesi", pr["Son 16"]),
            ("Çeyrek eşleşmesi", pr["Ceyrek Final"]), ("Yarı eşleşmesi", pr["Yari Final"]),
            ("Final eşleşmesi (iki finalist)", pr["Final"])]

    def block(title, accent, items):
        rrows = "".join(f'<div class="rrow"><span>{l}</span><b>+{v}</b></div>'
                        for l, v in items)
        return f'<div class="rblock {accent}"><div class="rhead">{title}</div>{rrows}</div>'

    return ('<div class="rules">'
            + block("GRUP · 360", "grp", grp)
            + block("KNOCKOUT · 400", "kw", ko)
            + block("DOĞRU EŞLEŞME · 240", "kp", pair)
            + '</div>'
            '<div class="rnote">'
            '<b>Grup sırası eşitlikte:</b> puan → ikili maç (puan/averaj/gol) → genel averaj '
            '→ genel gol → güncel FIFA sıralaması.<br>'
            '<b>En iyi 3.ler:</b> 12 grup üçüncüsü aynı kriterle (ikili maç hariç, çünkü '
            'birbirleriyle oynamıyorlar) sıralanır, en iyi 8\'i tur atlar ve sayılır.<br>'
            '<b>Kazanan puanı set bazlı</b> (takım o tura ulaştıysa), <b>eşleşme puanı</b> '
            'ise iki takımı birden doğru bilmeyi gerektirir. Toplam tavan: 1000.</div>')


def _round_card(title, teams, actual_set=None, accent=""):
    chips = "".join(
        f'<span class="tchip {"hit" if (actual_set and t in actual_set) else ""}">{t}</span>'
        for t in teams)
    return (f'<div class="kround {accent}"><div class="krhead">{title}'
            f'<span class="krcnt">{len(teams)}</span></div>'
            f'<div class="kteams">{chips}</div></div>')


def _pair_card(title, teams, reached=None, pairset=None):
    """Komşu ikilileri eşleşme (matchup) kutusu olarak göster.
    Tur belli olduysa: ulaşan takım yeşil, ulaşamayan kırmızı · kutu yeşil = eşleşme tuttu."""
    decided = bool(reached)
    units = ""
    for i in range(0, len(teams) - 1, 2):
        a, b = teams[i], teams[i + 1]
        ph = "pairhit" if (pairset and frozenset({a, b}) in pairset) else ""
        ca = ("ok" if a in reached else "no") if decided else ""
        cb = ("ok" if b in reached else "no") if decided else ""
        units += (f'<div class="matchup {ph}"><span class="mt {ca}">{a}</span>'
                  f'<span class="vs">–</span><span class="mt {cb}">{b}</span></div>')
    return (f'<div class="kround"><div class="krhead">{title}'
            f'<span class="krcnt">{len(teams) // 2} eşleşme</span></div>'
            f'<div class="kteams pairs">{units}</div></div>')


def _result_pairs_card(title, pairs, winners):
    """Gerçek knockout maçları: kazanan yeşil, elenen sönük."""
    units = ""
    for pr in sorted(pairs, key=lambda p: sorted(p)):
        a, b = tuple(pr)
        ca = "win" if a in winners else "lose"
        cb = "win" if b in winners else "lose"
        units += (f'<div class="matchup"><span class="mt {ca}">{a}</span>'
                  f'<span class="vs">–</span><span class="mt {cb}">{b}</span></div>')
    return (f'<div class="kround"><div class="krhead">{title}'
            f'<span class="krcnt">{len(pairs)} maç</span></div>'
            f'<div class="kteams pairs">{units}</div></div>')


def player_predictions_html(pp, actual):
    pb3 = set(ordered(pp, "En Iyi 3.ler"))     # oyuncunun en iyi 3. tahminleri
    cards = ""
    for g in GROUPS:
        agset = {actual["group"].get((g, p)) for p in (1, 2, 3, 4)}
        agset.discard(None)
        grows = ""
        for poz in (1, 2, 3, 4):
            pick = pp[g].get(poz, "—")
            # akıbet (oyuncunun tahminine göre): ilk2 geçer, 3. ancak en iyi 3.'ye yazdıysa
            if poz <= 2:
                adv = "q"
            elif poz == 3:
                adv = "t3" if pick in pb3 else "out"
            else:
                adv = "out"
            # doğruluk (gerçeğe göre): isimde yeşil/kırmızı
            real = actual["group"].get((g, poz))
            corr = ""
            if real is not None:
                corr = "hit" if pick == real else ("near" if pick in agset else "")
            grows += (f'<div class="grow {adv}"><span class="gp">{poz}</span>'
                      f'<span class="tn {corr}">{pick}</span></div>')
        cards += f'<div class="gcard"><div class="ghead">{g}</div>{grows}</div>'
    html = f'<div class="ggrid">{cards}</div>'
    html += _round_card("En İyi 3.ler", ordered(pp, "En Iyi 3.ler"), actual["best_third"])
    html += _pair_card("Son 32", ordered(pp, "Son 32"), actual.get("r32_set", set()),
                       actual["pair_set"].get("Son 32", set()))
    for label, key in [("Son 16", "Son 16"), ("Çeyrek", "Ceyrek Final"),
                       ("Yarı", "Yari Final"), ("Final", "Final")]:
        html += _pair_card(label, ordered(pp, key), actual["round_set"].get(key, set()),
                           actual["pair_set"].get(key, set()))
    champ = pp.get("Sampiyon", {}).get(1, "—")
    champ_set = {actual["champion"]} if actual["champion"] else set()
    html += _round_card("Şampiyon", [champ], champ_set, accent="champ")
    return html


with st.sidebar:
    st.header("Veri")
    demo = st.checkbox("Demo modu", value=False,
                       help="Gruplar oyuncu konsensüsüyle çözülür (test için)")
    if "nonce" not in st.session_state:
        st.session_state.nonce = 0
    if st.button("🔄 Yenile"):
        st.session_state.nonce += 1
        st.cache_data.clear()
    st.caption("Kaynak ~günlük güncellenir; saatlik canlı değildir.")

err = None
if demo:
    actual = demo_actuals(preds)
    src = "Demo modu · konsensüs"
else:
    try:
        matches = fetch_matches(st.session_state.nonce)
        actual = build_actuals(matches)
        played = sum(1 for m in matches if m.get("group") and (m.get("score") or {}).get("ft"))
        src = f"openfootball · {played} grup maçı oynandı"
    except Exception as e:  # noqa
        err = str(e)
        actual = demo_actuals(preds)
        src = "Veri alınamadı · demo"

rows = sorted(({"Oyuncu": p, **score_player(preds[p], actual)} for p in C.PLAYERS),
              key=lambda r: r["Toplam"], reverse=True)

st.markdown(f"""<div class="hero">
  <div class="cup">🏆</div>
  <h1>BEYSWC2026</h1>
  <p class="sub">Dünya Kupası 2026 · canlı tahmin ligi · 8 oyuncu</p>
  <span class="pill">{src} · maks 1000</span>
  <div class="legend">
    <span><i class="dot grp"></i>Grup</span>
    <span><i class="dot b3"></i>En İyi 3</span>
    <span><i class="dot kw"></i>KO Kazanan</span>
    <span><i class="dot kp"></i>KO Pair</span>
  </div>
</div>""", unsafe_allow_html=True)

with st.expander("📋 Puanlama nasıl hesaplanıyor? · maks 1000 puan"):
    st.markdown(rules_html(), unsafe_allow_html=True)

if err:
    st.error(f"Veri hatası: {err}")

st.markdown(podium_html(rows[:3]) + board_html(rows[3:], 4), unsafe_allow_html=True)

st.markdown('<div class="sec-title">Tahminler</div>', unsafe_allow_html=True)
who = st.selectbox("Kimin tahminleri?", C.PLAYERS,
                   index=C.PLAYERS.index(rows[0]["Oyuncu"]))
st.caption("Gruplar — rozet: yeşil ilk 2, mavi en iyi 3., sönük elenen · isim: yeşil doğru, "
           "kırmızı yanlış sıra.  Eşleşmeler: takım yeşil = o tura ulaştı, kırmızı = ulaşamadı, "
           "kutu yeşil = ikili birebir tuttu.")
st.markdown(player_predictions_html(preds[who], actual), unsafe_allow_html=True)

st.markdown('<div class="sec-title">Gerçek Sonuçlar</div>', unsafe_allow_html=True)
st.caption("Grup sırası: puan → ikili maç → genel averaj → genel gol → FIFA. "
           "Yeşil = ilk 2, mavi = en iyi 3. (tur atlar), sönük = elenen. "
           "Knockout maçlarında kazanan yeşil, elenen sönük.")
st.markdown(groups_html(actual), unsafe_allow_html=True)

real = ""
if actual["best_third"]:
    real += _round_card("En İyi 3.ler (ilk 8)", sorted(actual["best_third"]))
for lab, pkey, nextkey in [("Son 32", "Son 32", "Son 16"),
                           ("Son 16", "Son 16", "Ceyrek Final"),
                           ("Çeyrek", "Ceyrek Final", "Yari Final"),
                           ("Yarı", "Yari Final", "Final"),
                           ("Final", "Final", None)]:
    pairs = actual["pair_set"].get(pkey)
    if pairs:
        winners = ({actual["champion"]} if nextkey is None
                   else actual["round_set"].get(nextkey, set()))
        real += _result_pairs_card(lab, pairs, winners)
if actual["champion"]:
    real += _round_card("Şampiyon", [actual["champion"]], accent="champ")
if real:
    st.markdown(real, unsafe_allow_html=True)
