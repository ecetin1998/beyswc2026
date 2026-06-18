# BEYSWC2026 — Canlı Tahmin Ligi

8 kişilik Dünya Kupası 2026 tahmin ligi. Tahminler dosyada sabit; sonuçlar
**openfootball**'dan canlı çekilir (API key GEREKMEZ). Puan tablosu otomatik güncellenir.

## Kurulum
```bash
pip install -r requirements.txt
streamlit run app.py
```
Tarayıcı açılır, veriyi kendi çeker. Key, hesap, hiçbir şey gerekmez.

## Deploy (arkadaşlara link)
1. Bu klasörü olduğu gibi bir GitHub repo'suna at (app.py, config.py, tahminler.csv,
   requirements.txt ve **.streamlit/config.toml** — tema için bu dosya da gerekli).
2. https://share.streamlit.io → GitHub'la giriş → New app → repo + `app.py` seç → Deploy.
3. Çıkan `...streamlit.app` linkini paylaş. (Secret/key ayarı yok.)

## Puanlama (maks 1000)
- **Grup (360):** 1./2./3./4. doğru = 10/8/5/1, dördü birden = +6 bonus.
- **Knockout bloğu (400):** en iyi 3.ler her biri +2 · R32 kazananı +4 · R16 +8 ·
  Çeyrek +16 · Yarı +30 · Final kazananı +55 · Şampiyon bonusu +77.
- **Pair / eşleşme (240):** R32 +3 · R16 +7 · Çeyrek +13 · Yarı +22 · Final +40.

## Notlar
- Grup sıralaması maç skorlarından **hesaplanır**: puan > ikili maç (puan>averaj>gol) > genel averaj > genel gol
  (FIFA kriterleri). Daha derin eşitlikler (fair play, kura) nadirdir.
- Knockout kazananları set bazlı, pair'ler eşleşme bazlı. Takımlar belli oldukça dolar.
- Kaynak ~günlük güncellenir; saatlik canlı değildir. Daha taze isteyen olursa
  `DATA_URL`'i başka bir kaynakla değiştirebiliriz.
- Takım adları `config.py`'deki TR↔EN sözlüğünden eşleşir (48 takım eksiksiz).
