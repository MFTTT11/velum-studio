# SCALE // ZERO — 100% Otonom, 0 TL Faceless YouTube İmparatorluğu

**Visual Comparisons • Hidden Systems • Extreme Reality**  
Netflix / Vox / Bloomberg Telemetry estetiğinde, YouTube'un "AI çöpü" (AI slop) filtresini aşmak için sıfırdan mühendislikle tasarlanmış, **%100 otonom ve 0 TL maliyetli** YouTube üretim, yayın, yorum ve büyüme sistemi.

---

## Hızlı Başlangıç (Tek Komut)

```bash
python autopilot.py
```

Bulut / GitHub Actions tek seferlik mod:
```bash
python autopilot.py --run-once
```

---

## Public Repo Güvenlik Kilidi (Sıfır Sızıntı Mimarisi)
- `.gitignore` ilk dosya olarak şu yolları kalıcı yasaklar: `client_secrets.json`, `token.json`, `.env`, `*.key`, `*.pem`, `secrets/`, `output/`, `*.mp4`.
- Hiçbir kaynak kodda, log çıktısında veya `state.db` içinde gerçek API anahtarı, token, şifre veya e-posta tutulmaz.
- Tüm kimlik bilgileri yalnızca ortam değişkenlerinden (`os.getenv`) veya **GitHub Secrets** üzerinden okunur; geçici oluşturulan `client_secrets.json` ve `token.json` dosyaları işlem biter bitmez sıfırlanarak diskten silinir (`secure_delete_file` + GitHub Actions `if: always()` `rm -rf`).

---

## Sınırsız Ücretsiz Public GitHub Actions Kurulumu
1. Bu klasörü **Public** bir GitHub reposuna yükleyin (`.gitignore` tüm gizli ve medya dosyalarını otomatik korur).
2. GitHub Repo → **Settings → Secrets and variables → Actions → New repository secret** kısmına şu iki anahtarı ekleyin:
   - `YOUTUBE_CLIENT_SECRETS`: Google Cloud Console'dan aldığınız OAuth `client_secrets.json` içeriği (ham JSON veya base64).
   - `YOUTUBE_TOKEN`: OAuth yetkili `token.json` içeriği (ham JSON veya base64).
   - *(Opsiyonel 0 TL hızlandırıcılar)*: `GEMINI_API_KEY`, `GROQ_API_KEY`, `PEXELS_API_KEY` (eklenmese bile yerleşik motor %100 otonom çalışır).
3. `.github/workflows/autopilot.yml` günde 3 kez (`06:00`, `14:00`, `22:00 UTC`) otomatik çalışır, videoyu üretip QA'den geçirir, 7 günlük warm-up takvimine göre zamanlayıp yükler, çok dilli `.srt` altyazıları ekler, yorumları yanıtlar, düşük performanslı videoların A/B başlık & thumbnail'ını günceller ve sadece temiz `state.db` dosyasını repoya geri kaydeder.

---

## Mimari Dizin Yapısı
- `/brand_kit/`: `brand.json`, `profile_800x800.png`, `banner_2560x1440.png`, `watermark_150x150.png`
- `/prompts/`: `idea_scorer.md` (85+ viral baraj), `retention_script.md`, `omni_seo.md`, `multilang_reply.md`
- `/engine/`: `idea_engine.py`, `script_engine.py`, `voice_engine.py` (Edge-TTS + `silenceremove` + `faster-whisper`), `sfx_music_engine.py`, `media_fetcher.py`, `hud_renderer.py`, `video_composer.py` (1080p 60fps), `thumbnail_engine.py` (3x A/B/C), `qa_gate.py`
- `/publisher/`: `omni_seo.py` (VSEO/SEO/GEO/AEO + 5 dil `.srt`), `youtube_uploader.py` (7 günlük warm-up), `comment_responder.py` (15–45 dk gecikmeli çok dilli bot), `growth_mutator.py` (A/B mutasyon + kazanan format klonlama)
- `autopilot.py`: Ana orkestratör
