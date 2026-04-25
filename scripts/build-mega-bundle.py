#!/usr/bin/env python3
"""
Builds the mega kaomoji bundle by merging:
  1. The App's built-in bundle (../表情精靈/android/app/src/main/assets/kaomoji.json)
  2. ekohrt/emoticon_kaomoji_dataset (62,149 entries, English emotion tags)
  3. 6/kaomoji-json (4,727 entries, Japanese annotations)

Output: kaomoji-bundle.json (this repo's CDN payload)

Filtering rules:
  - Drop entries already present in App's built-in (by exact text match)
  - Drop empty / 1-char entries
  - Drop ultra-long ASCII art (>120 chars) — they break grid layout
  - Drop entries containing only ASCII / Western emoticons (we want kaomoji-style)
  - Dedupe by exact text within the new bundle

Category mapping: maps English emotion tags from ekohrt → our category IDs.
Untagged or unmappable entries → "misc".

Usage:
  python3 scripts/build-mega-bundle.py
"""

import json
import re
import hashlib
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_BUILTIN = ROOT.parent / "表情精靈" / "android" / "app" / "src" / "main" / "assets" / "kaomoji.json"
EKOHRT = Path("/tmp/emoticon_dict.json")
KAO_UTF8 = Path("/tmp/kao-utf8.json")
OUT = ROOT / "kaomoji-bundle.json"

# English tag → our category id. Order matters: first match wins.
TAG_MAP = [
    # Strong emotions first so they take priority over generic ones
    (["crying", "sob", "sobbing", "tears", "weeping"], "cry"),
    (["sad", "depressed", "lonely", "hurt", "disappointed"], "sad"),
    (["angry", "mad", "rage", "furious", "annoyed", "irritated"], "angry"),
    (["table", "flip", "flipping"], "flip"),
    (["scared", "afraid", "fear", "frightened", "terrified", "spook"], "scared"),
    (["shocked", "surprised", "astonished", "amazed", "shock"], "shocked"),
    (["embarrassed", "shy", "blush", "bashful"], "shy"),
    (["love", "heart", "kiss", "kissing", "kissed", "romance", "smitten", "infatuated"], "love"),
    (["laughing", "laugh", "haha", "lol", "giggle"], "laugh"),
    (["happy", "joy", "smiling", "smile", "cheerful", "excited", "glad", "elated", "pleased"], "happy"),
    (["cute", "kawaii", "adorable"], "cute"),
    (["angel", "innocent"], "cute"),
    (["dizzy", "confused", "perplexed", "puzzled"], "dizzy"),
    (["worried", "anxious", "nervous"], "helpless"),
    (["meh", "shrug", "indifferent", "shrugging", "whatever", "bored", "tired", "weary", "exhausted"], "helpless"),
    (["awkward", "facepalm", "regret", "fail"], "awkward"),
    (["smug", "smirk", "proud", "pleased", "confident"], "proud"),
    (["tsundere"], "tsundere"),
    (["sleeping", "sleep", "tired", "exhausted", "snoring", "yawn"], "sleep"),
    (["bye", "wave", "waving", "goodbye", "farewell"], "bye"),
    (["greeting", "hello", "hi", "salute"], "interact"),
    (["hugging", "hug", "hugs"], "interact"),
    (["food", "eating", "hungry", "drink", "tea", "coffee", "yum", "tasty"], "eat"),
    (["cat", "kitty", "neko"], "animal"),
    (["dog", "puppy", "doggo"], "animal"),
    (["bear", "bear-like"], "animal"),
    (["rabbit", "bunny"], "animal"),
    (["pig", "piglet"], "animal"),
    (["bird", "chick"], "animal"),
    (["fish", "shark", "whale"], "animal"),
    (["mouse", "rat", "spider", "monkey", "cow", "horse", "sheep"], "animal"),
    (["animal", "creature"], "animal"),
    (["thumbs up", "approve", "good job", "praise", "celebrate", "victory", "win"], "praise"),
    (["sorry", "apology", "apologizing", "bow", "kowtow", "dogeza"], "apology"),
    (["wink", "winking", "flirt"], "mischief"),
    (["lenny", "mischievous", "sly", "cheeky", "smug-mischief"], "mischief"),
    (["dance", "dancing", "music", "musical", "singing"], "happy"),
    (["festival", "party", "celebration", "birthday", "christmas"], "festival"),
    (["pain", "ouch", "hurt", "injured", "sick", "ill"], "sad"),
    (["dead", "died", "skull", "ghost"], "scared"),
    (["thinking", "ponder", "thought"], "misc"),
    (["wtf", "huh", "what"], "dizzy"),
    (["evil", "demon", "devil"], "mischief"),
    (["nosebleed", "nose"], "misc"),
    (["weapons", "gun", "sword", "fight", "fighting"], "angry"),
    (["sunglasses", "cool"], "proud"),
    (["mustache"], "misc"),
    (["hide", "hiding", "peek"], "shy"),
    (["random"], "misc"),
]

# English tag → Traditional Chinese keyword (for our 'k' search tags)
TAG_TO_ZH = {
    "happy": "開心", "joy": "開心", "smiling": "微笑", "smile": "微笑", "cheerful": "愉快",
    "excited": "興奮", "glad": "高興", "laughing": "大笑", "laugh": "笑", "haha": "哈哈",
    "lol": "笑", "giggle": "傻笑",
    "sad": "難過", "depressed": "沮喪", "lonely": "孤單", "hurt": "受傷", "disappointed": "失望",
    "crying": "哭", "sob": "啜泣", "sobbing": "大哭", "tears": "淚", "weeping": "哭泣",
    "angry": "生氣", "mad": "憤怒", "rage": "暴怒", "furious": "盛怒", "annoyed": "煩",
    "irritated": "惱火",
    "scared": "害怕", "afraid": "恐懼", "fear": "懼", "frightened": "驚嚇", "terrified": "驚恐",
    "spook": "嚇",
    "shocked": "震驚", "surprised": "驚訝", "astonished": "驚奇", "amazed": "驚嘆",
    "embarrassed": "尷尬", "shy": "害羞", "blush": "臉紅", "bashful": "靦腆",
    "love": "愛", "heart": "愛心", "kiss": "親親", "kissing": "親吻", "kissed": "被親",
    "romance": "戀愛", "smitten": "迷戀", "infatuated": "陶醉",
    "cute": "可愛", "kawaii": "卡哇伊", "adorable": "萌",
    "angel": "天使", "innocent": "純真",
    "dizzy": "頭暈", "confused": "困惑", "perplexed": "困惑", "puzzled": "疑惑",
    "worried": "擔心", "anxious": "焦慮", "nervous": "緊張",
    "meh": "無感", "shrug": "聳肩", "indifferent": "冷淡", "bored": "無聊", "tired": "累",
    "weary": "疲憊", "exhausted": "累壞",
    "awkward": "尷尬", "facepalm": "扶額", "regret": "後悔", "fail": "失敗",
    "smug": "得意", "smirk": "竊喜", "proud": "驕傲", "confident": "自信",
    "tsundere": "傲嬌",
    "sleeping": "睡覺", "sleep": "睡", "snoring": "打呼", "yawn": "打哈欠",
    "bye": "再見", "wave": "揮手", "waving": "揮手", "goodbye": "再見", "farewell": "告別",
    "hello": "你好", "hi": "嗨", "greeting": "打招呼", "salute": "敬禮",
    "hugging": "擁抱", "hug": "抱抱", "hugs": "擁抱",
    "food": "食物", "eating": "吃", "hungry": "餓", "drink": "喝", "tea": "茶", "coffee": "咖啡",
    "yum": "美味", "tasty": "好吃",
    "cat": "貓", "kitty": "貓咪", "neko": "貓", "dog": "狗", "puppy": "小狗", "doggo": "汪",
    "bear": "熊", "rabbit": "兔", "bunny": "兔子", "pig": "豬", "piglet": "小豬",
    "bird": "鳥", "chick": "雞", "fish": "魚", "shark": "鯊魚", "whale": "鯨魚",
    "mouse": "鼠", "rat": "鼠", "spider": "蜘蛛", "monkey": "猴", "cow": "牛",
    "horse": "馬", "sheep": "羊", "animal": "動物", "creature": "生物",
    "thumbs up": "讚", "approve": "同意", "praise": "讚賞", "celebrate": "慶祝",
    "victory": "勝利", "win": "贏",
    "sorry": "抱歉", "apology": "道歉", "bow": "鞠躬",
    "wink": "眨眼", "winking": "眨眼", "flirt": "調情",
    "lenny": "壞笑", "mischievous": "調皮", "sly": "狡猾", "cheeky": "厚臉皮",
    "dance": "跳舞", "dancing": "跳舞", "music": "音樂", "singing": "唱歌",
    "festival": "節日", "party": "派對", "celebration": "慶祝",
    "birthday": "生日", "christmas": "聖誕",
    "pain": "痛", "ouch": "痛", "injured": "受傷", "sick": "生病", "ill": "病",
    "dead": "死", "skull": "骷髏", "ghost": "鬼",
    "thinking": "思考", "ponder": "思索", "thought": "想",
    "wtf": "什麼鬼", "huh": "蛤", "what": "什麼",
    "evil": "邪惡", "demon": "惡魔", "devil": "魔鬼",
    "nosebleed": "流鼻血",
    "fight": "打架", "fighting": "戰鬥",
    "sunglasses": "墨鏡", "cool": "酷", "mustache": "鬍子",
    "hide": "躲", "hiding": "躲藏", "peek": "偷看",
    "table": "翻桌", "flip": "翻", "flipping": "翻",
    "popular": "熱門",
}


def categorize(tags: list[str]) -> str:
    tag_set = {t.lower() for t in tags}
    for matchers, cat_id in TAG_MAP:
        if any(m in tag_set for m in matchers):
            return cat_id
        # Also check substrings
        for matcher in matchers:
            for t in tag_set:
                if matcher in t:
                    return cat_id
    return "misc"


def to_zh_tags(tags: list[str]) -> list[str]:
    out = []
    seen = set()
    for t in tags:
        zh = TAG_TO_ZH.get(t.lower())
        if zh and zh not in seen:
            out.append(zh)
            seen.add(zh)
    return out[:6]  # cap to keep search index tight


def is_acceptable(text: str) -> bool:
    """Filter for kaomoji that render well in our 2-line grid cell.

    Targets: 3–50 chars, multi-script (must contain CJK or symbol that signals
    'kaomoji-style'), no whitespace-padded ASCII art, no multi-line.
    """
    if not text:
        return False
    n = len(text)
    if n < 3 or n > 50:
        return False
    if "\n" in text or "\r" in text:
        return False
    # Reject pure Western emoticons (must contain at least one non-ASCII char)
    if all(ord(c) < 128 for c in text):
        # allow short pure-ASCII like Orz, OTL, ¯\_(ツ)_/¯ — those have non-ASCII anyway
        return False
    # Reject excessive repeated-char filler ("━━━━━━━━━" alone)
    if len(set(text)) < 3:
        return False
    return True


# Per-category caps for the **initial release** (immediately visible).
# Aim: ~10,000 total kaomojis distributed across 27 categories.
CATEGORY_CAP = 420
MISC_CAP = 700

# Schedule for the rest: spread evenly across WEEKLY_DROP_WEEKS weeks,
# starting from the first Monday >= today + 7 days.
# Each kaomoji gets an `availableFrom` date so the App auto-unveils on schedule.
# 10 years × 52 weeks = 520 weekly drops.
WEEKLY_DROP_WEEKS = 520


def main():
    print("Loading App's built-in bundle...")
    builtin = json.loads(APP_BUILTIN.read_text())
    builtin_texts = {k["t"] for k in builtin["kaomojis"]}
    builtin_categories = builtin["categories"]
    print(f"  built-in: {len(builtin['kaomojis'])} kaomojis, {len(builtin_categories)} categories")

    print("Loading ekohrt 62k dataset...")
    ekohrt = json.loads(EKOHRT.read_text())
    print(f"  ekohrt: {len(ekohrt)} entries")

    print("Loading 6/kaomoji-json 4.7k dataset...")
    kao_utf8 = json.loads(KAO_UTF8.read_text())
    print(f"  6/kaomoji-json: {len(kao_utf8)} entries")

    # Build the merged set
    seen_texts = set(builtin_texts)
    out_kaomojis = []
    rejected_short = rejected_long = rejected_western = rejected_dup = 0

    # ekohrt: rich English tagging → drives most of categorization
    for text, info in ekohrt.items():
        if not is_acceptable(text):
            n = len(text)
            if n < 2:
                rejected_short += 1
            elif n > 80:
                rejected_long += 1
            else:
                rejected_western += 1
            continue
        if text in seen_texts:
            rejected_dup += 1
            continue
        seen_texts.add(text)

        all_tags = (info.get("new_tags") or []) + (info.get("original_tags") or [])
        cat = categorize(all_tags)
        zh_tags = to_zh_tags(all_tags)

        out_kaomojis.append({
            "text": text,
            "categoryId": cat,
            "tags": zh_tags,
        })

    # 6/kaomoji-json: Japanese annotations, no emotion tags
    # We use them to enrich the pool but categorize them as 'misc' unless we detect keywords
    for entry in kao_utf8:
        text = entry.get("face", "")
        annotation = entry.get("annotation", "")
        if not is_acceptable(text):
            continue
        if text in seen_texts:
            rejected_dup += 1
            continue
        seen_texts.add(text)

        # Lightweight Japanese-keyword categorization
        ann_lower = annotation.lower() if annotation else ""
        cat = "misc"
        if any(w in annotation for w in ["怒", "ムカ", "イラ"]):
            cat = "angry"
        elif any(w in annotation for w in ["泣", "涙"]):
            cat = "cry"
        elif any(w in annotation for w in ["悲", "つら"]):
            cat = "sad"
        elif any(w in annotation for w in ["嬉", "喜", "楽", "笑"]):
            cat = "happy"
        elif any(w in annotation for w in ["愛", "好き", "ハート", "キス"]):
            cat = "love"
        elif any(w in annotation for w in ["照", "恥"]):
            cat = "shy"
        elif any(w in annotation for w in ["驚"]):
            cat = "shocked"
        elif any(w in annotation for w in ["寝", "眠"]):
            cat = "sleep"
        elif any(w in annotation for w in ["猫", "ねこ", "ニャ"]):
            cat = "animal"
        elif any(w in annotation for w in ["犬", "いぬ", "ワン"]):
            cat = "animal"

        out_kaomojis.append({
            "text": text,
            "categoryId": cat,
            "tags": [annotation] if annotation else [],
        })

    print(f"\nFiltering report:")
    print(f"  Rejected too-short:  {rejected_short}")
    print(f"  Rejected too-long:   {rejected_long}")
    print(f"  Rejected non-kaomoji:{rejected_western}")
    print(f"  Rejected duplicates: {rejected_dup}")
    print(f"  Accepted new entries: {len(out_kaomojis)}")

    # Apply per-category caps to balance the bundle.
    # Within each category, prefer entries with more tags (better search coverage)
    # and shorter length (better grid rendering).
    from collections import defaultdict
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for item in out_kaomojis:
        by_cat[item["categoryId"]].append(item)

    capped: list[dict] = []      # availableFrom = None (immediate)
    scheduled: list[dict] = []   # availableFrom = future Mondays
    for cat, items in by_cat.items():
        # Score: more tags = higher; shorter text = higher; ties broken by text.
        # Top-N go to immediate release; the rest are scheduled across weekly drops.
        items.sort(key=lambda x: (-len(x["tags"]), len(x["text"]), x["text"]))
        cap = MISC_CAP if cat == "misc" else CATEGORY_CAP
        capped.extend(items[:cap])
        scheduled.extend(items[cap:])

    # Compute weekly drop dates: first Monday >= today + 7 days, then +7d each step.
    today = datetime.date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7  # at least 7 days out
    first_drop = today + datetime.timedelta(days=days_until_monday)
    drop_dates: list[str] = [
        (first_drop + datetime.timedelta(weeks=i)).isoformat()
        for i in range(WEEKLY_DROP_WEEKS)
    ]

    # Distribute scheduled entries round-robin across drop dates so every week gets
    # a balanced mix of categories (not 90 happy then 90 sad).
    # Shuffle within each category by hash of id for determinism.
    scheduled.sort(key=lambda x: hashlib.sha1(x["text"].encode("utf-8")).hexdigest())
    weekly_count = max(1, len(scheduled) // WEEKLY_DROP_WEEKS)
    for idx, item in enumerate(scheduled):
        week_idx = min(idx // weekly_count, len(drop_dates) - 1)
        item["availableFrom"] = drop_dates[week_idx]
    print(f"\nScheduled drops:")
    print(f"  First drop date: {drop_dates[0]}")
    print(f"  Last drop date:  {drop_dates[-1]}")
    print(f"  Weeks of content: {WEEKLY_DROP_WEEKS}")
    print(f"  Avg per week: ~{len(scheduled) // max(WEEKLY_DROP_WEEKS, 1)}")

    # Stable IDs based on hash of text — survives reorderings, hash collisions astronomically unlikely.
    # Combine immediate + scheduled into a single output list. The App's gated() filter
    # honors availableFrom client-side, so a single bundle is enough.
    final = []
    used_ids = set()
    all_items = capped + scheduled
    for item in all_items:
        h = hashlib.sha1(item["text"].encode("utf-8")).hexdigest()[:10]
        kid = f"e{h}"
        if kid in used_ids:
            continue
        used_ids.add(kid)
        entry = {
            "id": kid,
            "t": item["text"],
            "c": item["categoryId"],
            "k": item["tags"],
        }
        if "availableFrom" in item:
            entry["availableFrom"] = item["availableFrom"]
        final.append(entry)

    # Per-category breakdown
    from collections import Counter
    cat_counts = Counter(k["c"] for k in final)
    print(f"\nCategory distribution:")
    for cat in sorted(cat_counts, key=lambda c: -cat_counts[c]):
        print(f"  {cat:12s}  {cat_counts[cat]:>5}")

    # Ensure we cover any category id used by an entry. Inherit the App's built-in
    # categories, then append any extras (e.g. festival, internet from v2) that
    # aren't there yet, sourced from the existing bundle if it exists.
    cats_by_id = {c["id"]: c for c in builtin_categories}
    extra_cats = [
        {"id": "festival", "name": "節日",   "icon": "🎉", "order": 25},
        {"id": "internet", "name": "網路梗", "icon": "🌐", "order": 26},
    ]
    for c in extra_cats:
        if c["id"] not in cats_by_id:
            cats_by_id[c["id"]] = c
    # Push misc to the end if present
    if "misc" in cats_by_id:
        cats_by_id["misc"]["order"] = 99
    final_categories = sorted(cats_by_id.values(), key=lambda c: c["order"])

    bundle = {
        "version": 3,
        "publishedAt": "2026-04-25",
        "categories": final_categories,
        "kaomojis": final,
    }

    OUT.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")

    # Stats
    immediate = sum(1 for k in final if "availableFrom" not in k)
    scheduled_count = len(final) - immediate
    print(f"\n✓ Wrote {OUT}")
    print(f"  Total kaomojis: {len(final)}")
    print(f"    Immediately visible: {immediate}")
    print(f"    Scheduled future:    {scheduled_count}")
    print(f"  Total categories: {len(final_categories)}")
    print(f"  File size: {OUT.stat().st_size / 1024 / 1024:.2f} MB")

    # ---------------------------------------------------------------------
    # APK builtin: 5,000 entries that ship inside the APK and are visible to
    # the FREE tier without any network access. Pro users see these PLUS the
    # full CDN bundle (deduplicated client-side by id).
    # ---------------------------------------------------------------------
    APK_TARGET = 5000
    builtin_immediate = [k for k in final if "availableFrom" not in k]
    apk_subset = builtin_immediate[:APK_TARGET]

    # Carry over the original 433 hand-curated entries (h001/c001 etc.) so the
    # free experience keeps the curated category exemplars even if their hash
    # IDs would also appear in the auto-generated set. We re-assert their
    # hand-picked tags to preserve search quality.
    curated = builtin["kaomojis"]
    curated_by_text = {k["t"]: k for k in curated}
    apk_final: list[dict] = list(curated)
    seen_text = set(curated_by_text.keys())
    for entry in apk_subset:
        if len(apk_final) >= APK_TARGET: break
        if entry["t"] in seen_text: continue
        apk_final.append(entry)
        seen_text.add(entry["t"])

    apk_bundle = {
        "version": 1,
        "categories": final_categories,
        "kaomojis": apk_final,
    }
    APP_BUILTIN.write_text(json.dumps(apk_bundle, ensure_ascii=False, indent=2) + "\n")
    print(f"\n✓ Wrote {APP_BUILTIN}")
    print(f"  APK builtin entries: {len(apk_final)} (target {APK_TARGET})")
    print(f"  File size: {APP_BUILTIN.stat().st_size / 1024 / 1024:.2f} MB")

    # Clean up reserve.json from the previous design (no longer used).
    legacy = ROOT / "reserve.json"
    if legacy.exists():
        legacy.unlink()
        print(f"  Removed legacy {legacy.name}")


if __name__ == "__main__":
    main()
