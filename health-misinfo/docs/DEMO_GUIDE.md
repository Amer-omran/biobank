# دليل النموذج التطبيقي — Prototype guide

ثلاثة طرق بسيطة ومجانية. لا تحتاج خادماً ولا Docker ولا دفعاً.

## أ) تشغيل الموقع على جهازك (للعرض والمناقشة)
المتطلبات: Python 3.11+ و Node.js 20+.

* **ماك / لينكس:** من مجلد `health-misinfo` نفّذ `./start.sh`
* **ويندوز:** انقر مرتين على `start.bat`

في أول تشغيل يُطلب منك بريد وكلمة مرور المسؤول (كلمة المرور 10 أحرف على الأقل وتمزج حروفاً وأرقاماً ورموزاً).
بعدها يفتح الموقع على http://localhost:3000. التشغيل الأول يستغرق بضع دقائق للتثبيت، والتشغيلات التالية سريعة.
البيانات تُحفظ في `backend/healthmisinfo_dev.db`.

## ب) تدريب النموذج مجاناً على Google Colab
1. افتح https://colab.research.google.com ثم File → Upload notebook واختر `notebooks/train_and_deploy_colab.ipynb`.
2. Runtime → Change runtime type → **T4 GPU**.
3. شغّل الخلايا بالترتيب. في الخلية 4 راجع جدول المواءمة، واكتب اسمك، وفعّل `I_CONFIRM` — **هذا اعتمادك العلمي**.
4. يستغرق التدريب عادة 15–30 دقيقة. ثم تظهر النتائج الحقيقية وبطاقة النموذج.
5. الخلية 8 تنزّل `results.zip`. فكّه داخل `health-misinfo/` على جهازك، ثم أعد تشغيل `start.sh` فيُسجَّل النموذج تلقائياً.
6. احفظ ملف `data/registry/label_mappings/arafacts.json` المعتمد في GitHub، فهو توثيق قرارك.

إذا كان المستودع خاصاً، ستحتاج رمز GitHub للقراءة في الخلية 1.

## ج) رابط عام مؤقت ومجاني من Colab (Cloudflare Tunnel)
> **تحديث (2026-11-23):** Hugging Face أصبح يطلب اشتراك PRO لتشغيل Docker Spaces (خطأ 402)، لذلك لم يعد خيار
> Spaces مجانياً. البديل المجاني: تشغيل الموقع داخل Colab ونشره برابط `https://...trycloudflare.com`. الرابط يعمل
> طالما جلسة Colab مفتوحة، ويتغير في كل تشغيل.

## د) رابط دائم عبر Hugging Face Spaces (يتطلب اشتراك PRO)
1. أنشئ حساباً على https://huggingface.co
2. أنشئ رمز **Write** من https://huggingface.co/settings/tokens
3. شغّل الخلية الأخيرة في دفتر Colab (أو من جهازك:
   `python scripts/deploy_hf_space.py --space <اسمك>/health-claims-ai --admin-email <بريدك> --models-dir models`).
4. انتظر 10–15 دقيقة للبناء، ثم افتح الرابط المباشر `https://<اسمك>-health-claims-ai.hf.space`.
   استخدم الرابط المباشر، لأن تسجيل الدخول لا يعمل داخل الإطار المضمَّن في صفحة Hugging Face.

ملاحظات الرابط العام:
* كلمة مرور المسؤول ومفتاح الجلسات تُحفظ كـ **Secrets** في إعدادات الـ Space، ولا تُرفع في الملفات.
* في النسخة المجانية يُحذف السجل والمراجعات عند إعادة تشغيل الـ Space (قاعدة SQLite مؤقتة). للحفظ الدائم أضف
  قاعدة PostgreSQL مجانية (مثل Neon) عبر `--database-url`.
* يمكن نشر الموقع قبل التدريب؛ سيظهر «النموذج غير مدرَّب» حتى ترفع نموذجاً.
* بيانات AraFacts بترخيص CC BY-NC 4.0 (غير تجاري مع النسب)، والنسب ظاهر أسفل كل صفحة.

## صيغة التصنيف في النموذج التطبيقي
يُدرَّب النموذج على فئتين (**مدعوم** و**مضلل**). وتظهر فئة **يحتاج مراجعة** عندما تقل الثقة المعايَرة عن عتبة
اختيرت على بيانات التحقق، فيُحال الادعاء إلى الخبراء. يمكن العودة إلى ثلاث فئات حين تتوفر بيانات كافية.

**قيد يجب ذكره في الرسالة:** مع AraFacts وحدها يحتوي التقسيم على 20 / 4 / 4 ادعاءات «مدعوم» فقط
(تدريب / تحقق / اختبار) مقابل أكثر من 500 «مضلل». لذلك تكون مقاييس فئة «مدعوم» غير مستقرة إحصائياً،
وتُعرض كنتائج أولية لنموذج تطبيقي.

---

### English summary
* **Local:** `./start.sh` (macOS/Linux) or `start.bat` (Windows) → http://localhost:3000.
* **Train free:** upload `notebooks/train_and_deploy_colab.ipynb` to Colab (T4 GPU) and run all cells; you approve the label mapping in cell 4.
* **Public link free:** last notebook cell, or `scripts/deploy_hf_space.py`, deploys to a Hugging Face Docker Space.
* Prototype scheme: 2 classes + calibrated abstention → NEEDS_REVIEW. With AraFacts only, SUPPORTED has 20/4/4 claims in train/validation/test, so its metrics are unstable; report them as preliminary.
* `start.bat` was written for Windows but could not be executed in the build environment (Linux).
