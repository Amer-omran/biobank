# AI-Powered Detection of Health Rumors and Misinformation Using NLP
### An Applied Study in the Digital Health Sector — bilingual (Arabic / English) research platform

> **Research predictions only — not medical advice and not definitive fact-checks.** Results require
> evidence verification and may require expert review. A claim is never labelled false merely because no
> supporting source was found.

[العربية ↓](#ar)

## Simplest path (prototype) — see [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md)

1. **Run locally:** `./start.sh` (macOS/Linux) or `start.bat` (Windows) → http://localhost:3000
2. **Train for free:** open `notebooks/train_and_deploy_colab.ipynb` in Google Colab (T4 GPU) and run all cells
3. **Public link for free:** the last notebook cell deploys to a Hugging Face Space

## Current status (honest summary)

| Component | Status |
| --- | --- |
| Backend API, DB, migrations, auth, reviews, reports | ✅ working, 56 tests (SQLite + PostgreSQL 16) |
| Bilingual frontend (RTL/LTR), all controls wired | ✅ working, 11 unit tests + 14-step browser e2e |
| Dataset pipeline (adapters, dedup, grouping, mapping, verified splits) | ✅ working on real AraFacts / AraCOVID19-MFH files |
| Training / calibration / evaluation / model cards | ✅ code complete, smoke-tested with a tiny **random** network on **synthetic** data |
| **Trained AraBERT / XLM-R models** | ❌ **none** — no measured results exist |
| Eligible training data | ❌ 0 / 3,000 Arabic, 0 / 3,000 English — see [`docs/DATA_STATUS.md`](docs/DATA_STATUS.md) |

Why no model yet: the label mappings await approval by a named researcher, AraFacts' health subset cannot
support a valid 3-class split on its own (28 SUPPORTED / 3 NEEDS_REVIEW vs 709 MISLEADING under the
proposed mapping), AraCOVID19-MFH ships tweet IDs without text or license, PUBHEALTH and the Hugging Face
weights were not downloadable from the build environment. Until a model is trained, evaluated and
registered, the platform shows an explicit **model-not-trained** state and still provides similar
fact-checked claims and the full review workflow.

## Repository layout

```
health-misinfo/
  backend/              FastAPI + SQLAlchemy + Alembic + pipeline + training (package `healthmisinfo`)
    healthmisinfo/api/  routes, schemas, auth deps          healthmisinfo/data/  adapters, dedup, split
    healthmisinfo/ml/   train, metrics, calibration, registry, model cards
    healthmisinfo/inference/  model serving + similar-claim retrieval
    alembic/            migrations                            tests/  pytest suite + SYNTHETIC fixtures
  frontend/             Next.js 16 + TypeScript + Tailwind 4 (ar RTL / en LTR)
  data/registry/        sources.json (provenance & licenses), label_mappings/*.json (proposed/approved)
  data/raw|manual|processed/   gitignored data folders      models/  gitignored checkpoints
  docs/                 ARCHITECTURE, METHODOLOGY, DATA_STATUS, ANNOTATION_GUIDELINES, PRIVACY_SECURITY, API, openapi.json
  scripts/              fetch_datasets.sh, smoke_test.sh
  docker-compose.yml    .env.example
```

## Quick start — Docker

```bash
cp .env.example .env   # set POSTGRES_PASSWORD and HMD_SECRET_KEY (>= 32 chars)
```

```bash
docker compose up --build -d
```

```bash
docker compose exec api python -m healthmisinfo.cli create-user --email you@your-org.org --name "Your Name" --role admin
```

Open http://localhost:3000. Set `INSTALL_ML=1` in `.env` to include CPU PyTorch in the API image (needed to
serve trained models). *Note: the compose file was validated with `docker compose config` but not run in
the build environment, which has no Docker daemon.*

## Quick start — local development

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli init-db
```

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli create-user --email you@your-org.org --name "You" --role admin
```

```bash
cd backend && .venv/bin/uvicorn healthmisinfo.main:app --reload --port 8000
```

```bash
cd frontend && npm ci && npm run dev
```

Without `HMD_DATABASE_URL` a SQLite file (`backend/healthmisinfo_dev.db`) is used; set
`HMD_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db` for PostgreSQL. API docs: http://localhost:8000/docs.

## Research workflow

```bash
./scripts/fetch_datasets.sh          # AraFacts + AraCOVID19-MFH at audited revisions, SHA-256 verified
```

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli import-arafacts --file "../data/raw/arafacts/Dataset/AraFacts 2/AraFacts 2.csv" --name arafacts-health --version v2-2024-06-23
```

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli import-pubhealth --dir ../data/manual/pubhealth --name pubhealth --version v1.0
```

Approve label mappings yourself (records your name and date in the JSON), then refresh and split:

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli approve-mapping --source arafacts --approved-by "Your Name" --entries low-ambiguity
```

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli refresh-dataset --id 1
```

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli build-splits --language ar --version v1 --seed 42
```

Train (GPU recommended; needs access to huggingface.co), then register and activate:

```bash
cd backend && .venv/bin/python -m healthmisinfo.ml.train --language ar --split-dir ../data/processed/ar/v1 --seed 42
```

```bash
cd backend && .venv/bin/python -m healthmisinfo.cli register-model --run-dir ../models/ar/<run_tag> --activate
```

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
```

```bash
cd backend && HMD_TEST_USE_POSTGRES=1 HMD_TEST_POSTGRES_URL=postgresql+psycopg://user:pass@localhost:5432/hmd_test .venv/bin/python -m pytest -q
```

```bash
cd frontend && npm test && npx tsc --noEmit && npm run build
```

```bash
./scripts/smoke_test.sh              # add E2E_BASE_URL=http://localhost:3000 for the browser e2e
```

Synthetic fixtures live in `backend/tests/fixtures/` (each text starts with `[SYNTHETIC]`); the code refuses
to mix them into real datasets, splits or registered models.

## Data sources & licenses (summary — full registry in `data/registry/sources.json`)

| Source | License (verified?) | Text | Training use |
| --- | --- | --- | --- |
| AraFacts (Sheikh Ali et al., WANLP 2021) | CC BY-NC 4.0 (verified from LICENSE file) | ✅ | after mapping approval |
| AraCOVID19-MFH (Hadj Ameur & Aliane, 2021) | **no license file — needs review** | ❌ IDs only | blocked |
| PUBHEALTH (Kotonya & Toni, EMNLP 2020) | MIT for repo; data license **unclear** | ✅ (manual download) | after license review |
| Saudi MOH open data / WHO / PubMed | not verified here | — | evidence references only |

Please cite the datasets as listed in the registry.

---

<div dir="rtl" lang="ar" id="ar">

## الكشف عن الشائعات والمعلومات الصحية المضللة باستخدام الذكاء الاصطناعي ومعالجة اللغة الطبيعية
### دراسة تطبيقية في قطاع الصحة الرقمية — منصة بحثية ثنائية اللغة (عربي / إنجليزي)

> **المخرجات تنبؤات بحثية فقط — ليست نصيحة طبية ولا تحققاً نهائياً.** تتطلب النتائج التحقق من الأدلة وقد
> تحتاج إلى مراجعة خبير. لا يُصنَّف أي ادعاء كاذباً لمجرد عدم العثور على مصدر يدعمه.

### الوضع الحالي بصراحة

* الواجهة الخلفية وقاعدة البيانات والترحيلات والمصادقة وسير المراجعة والتقارير: **تعمل** (56 اختباراً على SQLite وPostgreSQL).
* الواجهة الأمامية ثنائية اللغة (من اليمين لليسار ومن اليسار لليمين) وكل الأزرار مرتبطة بالخادم: **تعمل** (11 اختبار وحدة + 14 خطوة اختبار متصفح).
* خط معالجة البيانات (المحوّلات، كشف التكرار، التجميع، المواءمة، التقسيم المتحقق منه): **يعمل** على ملفات AraFacts وAraCOVID19-MFH الحقيقية.
* التدريب والمعايرة والتقييم وبطاقات النماذج: **مكتملة برمجياً** ومختبرة بشبكة **عشوائية** صغيرة على بيانات **اصطناعية**.
* **لا يوجد أي نموذج مدرَّب (AraBERT أو XLM-R) ولا توجد أي نتائج مقيسة.**
* العينات المؤهلة للتدريب: 0 من 3,000 عربي و0 من 3,000 إنجليزي — التفاصيل في `docs/DATA_STATUS.md`.

**السبب:** مواءمات التصنيفات بانتظار اعتماد باحث مسمّى، ومجموعة AraFacts الصحية وحدها لا تسمح بتقسيم صالح
للفئات الثلاث (28 مدعوم و3 يحتاج مراجعة مقابل 709 مضلل وفق المواءمة المقترحة)، وAraCOVID19-MFH تحتوي معرّفات
تغريدات فقط بلا نص ولا ترخيص، ولم يكن تنزيل PUBHEALTH وأوزان Hugging Face ممكناً من بيئة البناء. وحتى يُدرَّب
نموذج ويُقيَّم ويُسجَّل، تعرض المنصة حالة صريحة **«النموذج غير مدرَّب»** مع الاستمرار في عرض ادعاءات مشابهة تم
التحقق منها وسير عمل المراجعة كاملاً.

### الطريق الأبسط (نموذج تطبيقي) — راجع `docs/DEMO_GUIDE.md`

1. **على جهازك:** `./start.sh` (ماك/لينكس) أو `start.bat` (ويندوز) ← http://localhost:3000
2. **التدريب مجاناً:** افتح `notebooks/train_and_deploy_colab.ipynb` في Google Colab وشغّل الخلايا
3. **رابط عام مجاني:** الخلية الأخيرة في الدفتر تنشر الموقع على Hugging Face Spaces

### التشغيل عبر Docker

1. انسخ `.env.example` إلى `.env` وعيّن `POSTGRES_PASSWORD` و`HMD_SECRET_KEY` (32 حرفاً على الأقل).
2. نفّذ `docker compose up --build -d`.
3. أنشئ حساب المسؤول: `docker compose exec api python -m healthmisinfo.cli create-user --email you@your-org.org --name "الاسم" --role admin`.
4. افتح http://localhost:3000 (الواجهة تبدأ بالعربية، ويمكن التبديل إلى الإنجليزية).

### التشغيل المحلي للتطوير

* الخادم: `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt` ثم
  `.venv/bin/python -m healthmisinfo.cli init-db` ثم `.venv/bin/uvicorn healthmisinfo.main:app --port 8000`.
* الواجهة: `cd frontend && npm ci && npm run dev`.
* بدون `HMD_DATABASE_URL` تُستخدم SQLite للتطوير؛ وفي الإنتاج PostgreSQL.

### سير العمل البحثي

1. تنزيل البيانات بالمراجعات والبصمات المعتمدة: `./scripts/fetch_datasets.sh`.
2. الاستيراد: `python -m healthmisinfo.cli import-arafacts ...` (التفاصيل في القسم الإنجليزي).
3. **اعتماد المواءمة بنفسك** (يُسجَّل اسمك والتاريخ): `approve-mapping --source arafacts --approved-by "اسمك"`.
4. إعادة التطبيق ثم التقسيم: `refresh-dataset` ثم `build-splits` — يُرفض التقسيم إذا افتقد أي جزء إحدى الفئات.
5. التدريب (يُفضَّل GPU ويتطلب الوصول إلى huggingface.co) ثم التسجيل والتفعيل.

### الاختبارات

`pytest` للخادم، و`npm test` للواجهة، و`scripts/smoke_test.sh` للاختبار الشامل. البيانات الاصطناعية مُعلَّمة
بـ `[SYNTHETIC]` ولا تُخلط أبداً بالبيانات الحقيقية.

### الوثائق

`docs/ARCHITECTURE.md` (المعمارية وقائمة المهام)، `docs/METHODOLOGY.md` (المنهجية)، `docs/DATA_STATUS.md`
(وضع البيانات المقيس)، `docs/ANNOTATION_GUIDELINES.md` (إرشادات التوسيم)، `docs/PRIVACY_SECURITY.md`
(الخصوصية والأمان)، `docs/API.md` (واجهة البرمجة).

</div>
