"""BEYSWC2026 — puanlama kuralları ve takım adı eşleştirme."""
import unicodedata

# ----------------------------------------------------------------------------
# PUANLAMA (toplam 1000)
# ----------------------------------------------------------------------------
GROUP_POINTS = {1: 10, 2: 8, 3: 5, 4: 1}   # grup sıralaması doğru
GROUP_EXACT_BONUS = 6                       # 1-2-3-4 dördü de doğru
BEST_THIRD_POINTS = 2                       # her doğru "en iyi 3." (set bazlı)

# knockout KAZANAN puanı: bir sonraki turun takımları = önceki turun kazananları
# (Son 16'daki takımlar = R32 kazananları, vb.)  -> set bazlı sayılır
KO_WINNER_POINTS = {
    "Son 16": 4,        # Round of 32 kazananı
    "Ceyrek Final": 8,  # Round of 16 kazananı
    "Yari Final": 16,   # Çeyrek final kazananı
    "Final": 30,        # Yarı final kazananı
    "Sampiyon": 55,     # Final kazananı
}
CHAMPION_BONUS = 77

# knockout PAIR (iki takım birden) puanı: komşu slotlar -> eşleşme (sırasız çift)
KO_PAIR_POINTS = {
    "Son 32": 3,
    "Son 16": 7,
    "Ceyrek Final": 13,
    "Yari Final": 22,
    "Final": 40,
}

# hangi turun gerçek maçları hangi "round adı" altında gelir (API-Football round string)
API_ROUND_KEYS = {
    "Son 32": ["round of 32"],
    "Son 16": ["round of 16"],
    "Ceyrek Final": ["quarter"],
    "Yari Final": ["semi"],
    "Final": ["final"],   # "3rd place" ayrıca elenecek
}

# ----------------------------------------------------------------------------
# TAKIM ADLARI: türkçe token -> kabul edilen ingilizce karşılıklar
# ----------------------------------------------------------------------------
TR_TO_EN = {
    "meksika": ["Mexico"],
    "güney kore": ["South Korea", "Korea Republic"],
    "çekya": ["Czech Republic", "Czechia"],
    "güney afrika": ["South Africa"],
    "isviçre": ["Switzerland"],
    "bosna": ["Bosnia and Herzegovina", "Bosnia & Herzegovina"],
    "kanada": ["Canada"],
    "katar": ["Qatar"],
    "brezilya": ["Brazil"],
    "fas": ["Morocco"],
    "iskoçya": ["Scotland"],
    "haiti": ["Haiti"],
    "türkiye": ["Turkey", "Türkiye", "Turkiye"],
    "avustralya": ["Australia"],
    "abd": ["USA", "United States"],
    "paraguay": ["Paraguay"],
    "almanya": ["Germany"],
    "ekvador": ["Ecuador"],
    "fildişi": ["Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"],
    "curaçao": ["Curacao", "Curaçao"],
    "hollanda": ["Netherlands"],
    "japonya": ["Japan"],
    "isveç": ["Sweden"],
    "tunus": ["Tunisia"],
    "belçika": ["Belgium"],
    "mısır": ["Egypt"],
    "iran": ["Iran"],
    "yeni zelanda": ["New Zealand"],
    "ispanya": ["Spain"],
    "uruguay": ["Uruguay"],
    "suudi arabistan": ["Saudi Arabia"],
    "yeşil burun": ["Cape Verde", "Cabo Verde"],
    "fransa": ["France"],
    "norveç": ["Norway"],
    "senegal": ["Senegal"],
    "ırak": ["Iraq"],
    "arjantin": ["Argentina"],
    "avusturya": ["Austria"],
    "cezayir": ["Algeria"],
    "ürdün": ["Jordan"],
    "portekiz": ["Portugal"],
    "kolombiya": ["Colombia"],
    "kongo": ["DR Congo", "Congo DR", "Democratic Republic of the Congo", "Congo"],
    "özbekistan": ["Uzbekistan"],
    "hırvatistan": ["Croatia"],
    "ingiltere": ["England"],
    "gana": ["Ghana"],
    "panama": ["Panama"],
}

_TR_CHAR = str.maketrans({
    "ı": "i", "İ": "i", "I": "i", "ş": "s", "Ş": "s", "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u",
})


def normalize(name: str) -> str:
    """Aksan/Türkçe karakter farklarını eze eze sade bir anahtar üret."""
    if not name:
        return ""
    s = name.translate(_TR_CHAR)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = "".join(c if c.isalnum() else " " for c in s)
    return " ".join(s.split())


# ingilizce (normalize) -> türkçe token  (API cevabını türkçe tokena çevirmek için)
EN_NORM_TO_TR = {}
for _tr, _ens in TR_TO_EN.items():
    EN_NORM_TO_TR[normalize(_tr)] = _tr
    for _en in _ens:
        EN_NORM_TO_TR[normalize(_en)] = _tr


def to_tr_token(api_name: str):
    """API'den gelen ingilizce takım adını türkçe tokena çevirir; bulamazsa None."""
    return EN_NORM_TO_TR.get(normalize(api_name))


PLAYERS = ["emircan", "celil", "serhat", "erdem", "serdar", "ekin", "oguz", "baris"]


# ----------------------------------------------------------------------------
# Güncel FIFA ülke sıralaması (11 Haziran 2026 resmi) — tiebreaker madde 8
# küçük sayı = daha iyi sıra
# ----------------------------------------------------------------------------
FIFA_RANK = {
    "arjantin": 1, "ispanya": 2, "fransa": 3, "ingiltere": 4, "portekiz": 5,
    "brezilya": 6, "fas": 7, "hollanda": 8, "belçika": 9, "almanya": 10,
    "hırvatistan": 11, "kolombiya": 13, "meksika": 14, "senegal": 15, "uruguay": 16,
    "abd": 17, "japonya": 18, "isviçre": 19, "iran": 20, "türkiye": 22,
    "ekvador": 23, "avusturya": 24, "güney kore": 25, "avustralya": 27, "cezayir": 28,
    "mısır": 29, "kanada": 30, "norveç": 31, "fildişi": 33, "panama": 34,
    "isveç": 38, "çekya": 40, "paraguay": 41, "iskoçya": 42, "tunus": 45,
    "kongo": 46, "özbekistan": 50, "katar": 56, "ırak": 57, "güney afrika": 60,
    "suudi arabistan": 61, "ürdün": 63, "bosna": 64, "yeşil burun": 67, "gana": 73,
    "curaçao": 82, "haiti": 83, "yeni zelanda": 85,
}


# ----------------------------------------------------------------------------
# Bu turnuvada kesinleşen "en iyi 3." R32 slot atamaları (resmi bracket).
# openfootball bu slotları geç doldurduğu için köprü; kaynak gerçek ismi
# koyunca resolve() otomatik onu kullanır, burası devre dışı kalır.
# Slot kodu (openfootball placeholder) -> takım (türkçe token)
# ----------------------------------------------------------------------------
R32_THIRD_SLOT = {
    "3A/B/C/D/F": "paraguay",
    "3C/D/F/G/H": "isveç",
    "3C/E/F/H/I": "ekvador",
    "3E/H/I/J/K": "kongo",
    "3B/E/F/I/J": "bosna",
    "3A/E/H/I/J": "senegal",
    "3E/F/G/I/J": "cezayir",
    "3D/E/I/J/L": "gana",
}


# ----------------------------------------------------------------------------
# openfootball skoru geç girdiğinde elle köprü: maç no -> skor.
# SADECE kaynakta skor yoksa uygulanır; kaynak skoru girince otomatik devre dışı.
# ----------------------------------------------------------------------------
MANUAL_SCORES = {
    104: {"ft": [0, 0], "et": [1, 0]},   # Final: İspanya 1-0 Arjantin (uzatma, Torres 106')
}
