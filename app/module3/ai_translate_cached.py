import os
import json
import hashlib

try:
    from .groqai_client import get_ai_client
except ImportError:  # pragma: no cover - fallback for direct execution from module3/
    from groqai_client import get_ai_client

MODEL = "llama-3.3-70b-versatile"
BASE_CACHE = "cache"
DEFECT_TRANSLATION_CACHE_VERSION = "v2"
REPORT_TRANSLATION_CACHE_VERSION = "v2"
REMARK_TRANSLATION_CACHE_VERSION = "v3"

# =========================
# UTILITIES
# =========================
def _extract_json(text):
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return None
    return text[start:end+1]


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _hash_json(data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _hash_text(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _cache_path(category, key):
    folder = os.path.join(BASE_CACHE, category)
    _ensure_dir(folder)
    return os.path.join(folder, f"{key}.cache")

def _normalise_defects(defects):
    clean = []
    for d in defects:
        clean.append({
            "id": d.get("id"),
            "unit": d.get("unit"),
            "desc": d.get("desc", "").strip().lower(),
            "remarks": d.get("remarks", "").strip().lower(),
            "priority": d.get("priority"),
        })
    return clean

# =========================
# DEFECT TRANSLATION (JSON)
# =========================
def translate_defects_cached(defects, language="ms", role="Homeowner"):
    if not defects or language not in ("ms", "en"):
        return defects

    safe_defects = []
    for d in defects:
        safe_defects.append({
            "id": d.get("id"),
            "unit": d.get("unit"),
            "desc": d.get("desc", ""),
            "priority": d.get("priority"),
        })

    key = f"{DEFECT_TRANSLATION_CACHE_VERSION}_{language}_{role}_{_hash_json(safe_defects)}"
    cache_file = _cache_path("defects", key)

    translated = None

    # 🔁 LOAD CACHE
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if data:
                    translated = json.loads(data)
        except Exception:
            translated = None

    # 🔹 CALL AI ONLY IF NO CACHE
    if translated is None:
        client = get_ai_client()

        target = (
            "Bahasa Malaysia formal pentadbiran Tribunal"
            if language == "ms"
            else "Formal English for Consumer Tribunal documents"
        )

        prompt = f"""
Translate the JSON data below into {target}.

MANDATORY RULES:
1. JSON structure MUST remain unchanged
2. Do NOT add or remove fields
3. Do NOT change id, numbers, dates, unit, status
4. Translate ONLY descriptive text (desc, priority)
5. Output JSON ONLY
6. Do NOT leave source-language words in translated fields unless they are proper nouns, model numbers, or standard acronyms

DATA:
{json.dumps(safe_defects, ensure_ascii=False)}
"""

        res = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are an official tribunal document translator."},
                {"role": "user", "content": prompt}
            ]
        )

        raw = res.choices[0].message.content.strip()
        json_text = _extract_json(raw)
        if not json_text:
            return defects

        try:
            translated = json.loads(json_text)
        except Exception:
            return defects

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)

    # 🔹 MERGE RESULT
    translated_map = {d["id"]: d for d in translated}

    for d in defects:
        t = translated_map.get(d["id"])
        if t:
            d["desc"] = t.get("desc", d.get("desc"))
            d["priority"] = t.get("priority", d.get("priority"))

    # TERMINOLOGY FIX
    TERM_FIX = {
        "retros": "retakan",
        "Retros": "Retakan",
    }

    for d in defects:
        if d.get("desc"):
            for wrong, correct in TERM_FIX.items():
                d["desc"] = d["desc"].replace(wrong, correct)

    # PRIORITY NORMALISATION (DONT USE AI)
    PRIORITY_MAP = {
        "ms": {
            "High": "Tinggi",
            "Medium": "Sederhana",
            "Low": "Rendah",
        },
        "en": {
            "Tinggi": "High",
            "Sederhana": "Medium",
            "Rendah": "Low",
        }
    }

    for d in defects:
        if d.get("priority"):
            d["priority"] = PRIORITY_MAP.get(language, {}).get(
                d["priority"],
                d["priority"]
            )

    return defects

# =========================
# AI REPORT TRANSLATION
# =========================
def translate_report_cached(report_text, language="ms", role="Homeowner"):
    if not report_text or language not in ("ms", "en"):
        return report_text

    key = f"{REPORT_TRANSLATION_CACHE_VERSION}_{language}_{role}_{_hash_text(report_text)}"
    cache_file = _cache_path("reports", key)

    # 🔁 cache hit (SAFE)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if data:
                    return data
                else:
                    raise ValueError
        except Exception:
            pass


    client = get_ai_client()

    target = (
        "Bahasa Malaysia formal Tribunal"
        if language == "ms"
        else "Formal English for Consumer Tribunal documents"
    )

    prompt = f"""
Translate the text below into {target}.
ALL content must be translated into the target language.
Do NOT leave any original language text.
    Keep proper nouns, IDs, and standard acronyms unchanged.

TEXT:
{report_text}
"""

    res = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "You are an official tribunal document translator."},
            {"role": "user", "content": prompt}
        ]
    )

    translated = res.choices[0].message.content.strip()

    # ❗ zero AI  → use original report
    if not translated:
        return report_text

    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(translated)

    return translated


def translate_remark_cached(remark_text, language="ms", role="Homeowner"):
    if not remark_text or language not in ("ms", "en"):
        return remark_text

    key = f"{REMARK_TRANSLATION_CACHE_VERSION}_remark_{language}_{role}_{_hash_text(remark_text)}"
    cache_file = _cache_path("remarks", key)

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if data:
                    return data
        except Exception:
            pass

    client = get_ai_client()
    target = "Bahasa Malaysia" if language == "ms" else "English"

    prompt = f"""
Translate this single user remark into {target}.

STRICT RULES:
1. Keep the meaning exactly the same
2. Keep sentence count and order the same
3. Do NOT summarize, elaborate, or rewrite style
4. Keep punctuation and numbers where possible
5. Output plain translated text only
6. Do NOT leave source-language words unless they are names, IDs, model numbers, or common acronyms

REMARK:
{remark_text}
"""

    res = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a precise legal translator. Translate literally and do not paraphrase."},
            {"role": "user", "content": prompt}
        ]
    )

    translated = (res.choices[0].message.content or "").strip()
    if not translated:
        return remark_text

    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(translated)

    return translated
