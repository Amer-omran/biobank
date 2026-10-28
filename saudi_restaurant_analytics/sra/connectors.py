"""موصلات بيانات وسائل التواصل الاجتماعي عبر الواجهات الرسمية فقط.

قواعد ملزمة في هذا المشروع:
- لا يوجد أي كشط (scraping) لصفحات الويب، ولا تجاوز لحدود الاستخدام أو صلاحيات الوصول.
- المفاتيح تُقرأ من متغيرات البيئة فقط ولا تُكتب في الكود أو قاعدة البيانات.
- لا نحفظ اسم المستخدم أو معرفه أو صورته؛ نحفظ النص والتاريخ والمصدر فقط.
- على المستخدم التأكد من أن شروط المنصة وفئة اشتراكه تسمح بالبحث وبتخزين المحتوى
  لأغراض بحثية، وبالالتزام بطلبات الحذف.

البديل الأبسط والموصى به: تصدير البيانات من أداة المنصة الرسمية (مثل لوحة تقييمات
النشاط التجاري) إلى CSV ثم استيرادها من صفحة «استيراد البيانات».
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Callable

import pandas as pd

from . import config
from .text_processing import mask_personal_info


class ConnectorError(RuntimeError):
    pass


class BaseConnector(ABC):
    """كل موصل يُرجع DataFrame بأعمدة: text, review_date, source (وrestaurant_name اختياريًا)."""

    source_name = "unknown"

    @abstractmethod
    def fetch(self) -> pd.DataFrame:  # pragma: no cover - واجهة مجردة
        ...


class XRecentSearchConnector(BaseConnector):
    """البحث الحديث في X (تويتر سابقًا) عبر API v2 الرسمي.

    يتطلب Bearer Token في متغير البيئة X_BEARER_TOKEN، وفئة اشتراك تسمح بنقطة
    /2/tweets/search/recent. لا يجلب بيانات المؤلفين.
    """

    source_name = "X API v2 (recent search)"
    endpoint = "https://api.x.com/2/tweets/search/recent"

    def __init__(self, query: str, max_results: int = 50, restaurant_name: str | None = None,
                 bearer_token: str | None = None, http_get: Callable | None = None):
        if not query or not query.strip():
            raise ConnectorError("يجب كتابة عبارة بحث.")
        self.query = query.strip()
        self.max_results = max(10, min(int(max_results), 100))  # الحدود التي تقبلها الواجهة
        self.restaurant_name = restaurant_name
        self.bearer_token = bearer_token or os.environ.get(config.X_BEARER_TOKEN_ENV)
        if not self.bearer_token:
            raise ConnectorError(
                f"لم يُعثر على المفتاح. عرّف متغير البيئة {config.X_BEARER_TOKEN_ENV} قبل تشغيل المنصة "
                "(لا تكتب المفتاح داخل الكود)."
            )
        self.http_get = http_get or self._http_get

    def _http_get(self, url: str, headers: dict) -> tuple[int, dict]:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                body = {}
            return exc.code, body

    def fetch(self) -> pd.DataFrame:
        params = {
            # استبعاد إعادة النشر، وطلب العربية فقط
            "query": f"({self.query}) lang:ar -is:retweet",
            "max_results": str(self.max_results),
            "tweet.fields": "created_at,lang",
        }
        url = self.endpoint + "?" + urllib.parse.urlencode(params)
        status, body = self.http_get(url, {"Authorization": f"Bearer {self.bearer_token}"})
        if status == 429:
            raise ConnectorError("تجاوزت حد الطلبات المسموح من المنصة. انتظر ثم أعد المحاولة.")
        if status in (401, 403):
            raise ConnectorError("المفتاح غير صالح أو أن فئة اشتراكك لا تسمح بهذه العملية.")
        if status != 200:
            raise ConnectorError(f"استجابة غير متوقعة من الواجهة (رمز {status}).")
        rows = []
        for item in body.get("data", []) or []:
            rows.append({
                "text": mask_personal_info(item.get("text", "")),
                "review_date": (item.get("created_at") or "")[:10] or None,
                "source": self.source_name,
                "restaurant_name": self.restaurant_name,
            })
        return pd.DataFrame(rows, columns=["text", "review_date", "source", "restaurant_name"])


def connector_status() -> dict[str, bool]:
    """هل المفاتيح المطلوبة معرفة؟ (دون عرض قيمتها)."""
    return {"X API": bool(os.environ.get(config.X_BEARER_TOKEN_ENV))}
