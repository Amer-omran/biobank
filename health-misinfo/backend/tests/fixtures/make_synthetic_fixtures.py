"""Generate the SYNTHETIC test fixtures in this directory (deterministic).

These sentences are template-generated for SOFTWARE TESTS ONLY. They are not real claims, carry no
medical meaning, are marked "[SYNTHETIC]" in the text and is_synthetic=true, and the platform
refuses to train real models on them or mix them into real datasets.

    python tests/fixtures/make_synthetic_fixtures.py
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

HERE = Path(__file__).parent

EN = {
    "SUPPORTED": [
        "regular handwashing with soap lowers the spread of {x}",
        "health authorities recommend vaccination schedules for {x}",
        "drinking clean water reduces the risk of {x}",
    ],
    "MISLEADING": [
        "a secret kitchen spice instantly cures {x} overnight",
        "mobile phone towers cause {x} in every city",
        "doctors are hiding that lemon water removes {x} forever",
    ],
    "NEEDS_REVIEW": [
        "a new unpublished study suggests a herb may affect {x}",
        "some people report that a supplement changes {x} symptoms",
        "an unverified post claims a clinic found a link with {x}",
    ],
}
AR = {
    "SUPPORTED": [
        "غسل اليدين بالماء والصابون يقلل انتشار {x}",
        "توصي الجهات الصحية بجدول التطعيم ضد {x}",
        "شرب الماء النظيف يقلل خطر الإصابة بـ {x}",
    ],
    "MISLEADING": [
        "توابل سرية في المطبخ تعالج {x} خلال ليلة واحدة",
        "أبراج الهاتف المحمول تسبب {x} في كل مدينة",
        "الأطباء يخفون أن ماء الليمون يزيل {x} نهائيا",
    ],
    "NEEDS_REVIEW": [
        "دراسة جديدة غير منشورة تشير إلى أن عشبة قد تؤثر في {x}",
        "يقول بعض الناس إن مكملا غذائيا يغير أعراض {x}",
        "منشور غير موثق يزعم أن عيادة وجدت علاقة مع {x}",
    ],
}
TOPICS_EN = ["influenza", "measles", "cholera", "diabetes", "malaria", "hepatitis", "asthma"]
TOPICS_AR = ["الإنفلونزا", "الحصبة", "الكوليرا", "السكري", "الملاريا", "التهاب الكبد", "الربو"]


def build(templates, topics, prefix, seed):
    rng = random.Random(seed)
    rows = []
    i = 0
    for label, temps in templates.items():
        for t_idx, t in enumerate(temps):
            for x in topics:
                i += 1
                rows.append(
                    {
                        "id": f"{prefix}-{i:03d}",
                        "text": f"[SYNTHETIC] {t.format(x=x)}",
                        "label": label,
                        "is_synthetic": "true",
                        "group_key": f"{prefix}-{label}-{t_idx}-{x}",
                    }
                )
    rng.shuffle(rows)
    return rows


def write(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "text", "label", "is_synthetic", "group_key"])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    write(HERE / "synthetic_claims_en.csv", build(EN, TOPICS_EN, "SYN-EN", 1))
    write(HERE / "synthetic_claims_ar.csv", build(AR, TOPICS_AR, "SYN-AR", 2))
    print("wrote synthetic fixtures")
