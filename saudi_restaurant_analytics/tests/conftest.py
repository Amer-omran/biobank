"""إعدادات مشتركة للاختبارات: قاعدة بيانات مؤقتة لكل اختبار حتى لا نلمس بيانات المستخدم."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sra import database  # noqa: E402
from sra.dishes import DishExtractor  # noqa: E402
from sra.sentiment import LexiconSentimentAnalyzer  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    connection = database.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def analyzer():
    return LexiconSentimentAnalyzer(DishExtractor.from_csv())


@pytest.fixture(scope="session")
def extractor():
    return DishExtractor.from_csv()
