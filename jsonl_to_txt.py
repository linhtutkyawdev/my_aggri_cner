import json
import os
import re

CLEAN_JSONL = "output/cleaned_unique.jsonl"
INPUT_FILE = "output/posts.jsonl"
OUTPUT_DIR = "raw/categories"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# -------------------------------------------------
# Filename safety
# -------------------------------------------------
def safe_filename(name):
    name = name.strip()
    return re.sub(r'[<>:"/\\|?*]', "_", name)

def to_multiline(text):
    # split by full stops, Myanmar danda, or newline hints
    parts = re.split(r"(?<=[။။။\.])\s+", text)

    return "\n".join(p.strip() for p in parts if p.strip())

# -------------------------------------------------
# Content cleaner
# -------------------------------------------------
def clean_content(text):
    if not text:
        return ""

    # Normalize invisible characters
    text = text.replace("\u00A0", " ")
    text = re.sub(r"[\u200b-\u200f\uFEFF]", "", text)

    # -------------------------------------------------
    # Remove ad block
    # -------------------------------------------------
    text = re.sub(
        r"ကြော်ငြာ.*?Read more\s+ဆွေးနွေးချက်များ\s+ဆွေးနွေးရန်",
        "",
        text,
        flags=re.DOTALL
    )

    # -------------------------------------------------
    # Remove Farm Link
    # -------------------------------------------------
    text = re.sub(
        r"Farm Link Co\.,?\s*Ltd",
        "",
        text,
        flags=re.IGNORECASE
    )

    # -------------------------------------------------
    # REMOVE ANY SOURCE LINES (FINAL FIX)
    # catches:
    # Source - ACARE
    # Source – ...
    # Source-ACARE
    # even with hidden chars
    # -------------------------------------------------
    text = re.sub(
        r"(?im)^.*\bsource\b.*$",
        "",
        text
    )

    # -------------------------------------------------
    # Clean multiple blank lines
    # -------------------------------------------------
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()


# -------------------------------------------------
# Deduplication by route
# -------------------------------------------------
seen_routes = set()


with open(INPUT_FILE, "r", encoding="utf-8") as infile, \
     open(CLEAN_JSONL, "w", encoding="utf-8") as clean_out:

    for line_number, line in enumerate(infile, start=1):

        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)

            # -----------------------------------
            # DEDUPE BY ROUTE
            # -----------------------------------
            route = obj.get("route", [])
            route_key = tuple(route)

            if route_key in seen_routes:
                print(f"[SKIP DUP] line {line_number}: {route}")
                continue

            seen_routes.add(route_key)

            # -----------------------------------
            # CLEAN CONTENT
            # -----------------------------------
            content = to_multiline(clean_content(obj.get("content", "")))

            if not content:
                continue

            obj["content"] = content

            # -----------------------------------
            # WRITE CLEAN JSONL
            # -----------------------------------
            clean_out.write(
                json.dumps(obj, ensure_ascii=False) + "\n"
            )

            # -----------------------------------
            # WRITE TO CATEGORY FILE
            # -----------------------------------
            category = obj.get("category", "unknown")
            filename = safe_filename(category) + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            with open(filepath, "a", encoding="utf-8") as out:
                out.write(content)
                out.write("\n")

        except Exception as e:
            print(f"[ERROR] line {line_number}: {e}")