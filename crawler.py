import requests
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
import os
import time
import json
from collections import defaultdict

BASE = "https://greenwaymyanmar.com"

session = requests.Session()

# 🔥 IMPORTANT: mimic real browser (based on your curl)
session.headers.update({
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9,my;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/148.0.0.0 Safari/537.36",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
})

# -----------------------------
# STEP 1: BOOTSTRAP SESSION
# -----------------------------
def bootstrap():
    print("[BOOTSTRAP] Visiting homepage to get cookies...")
    r = session.get(BASE, timeout=30)
    if r.status_code != 200:
        raise Exception("Failed to bootstrap session")
    return r.text


# -----------------------------
# STEP 2: GET CATEGORIES API
# -----------------------------
def get_categories():
    api = f"{BASE}/api/web/forum/requirements"
    r = session.get(api, timeout=30)
    data = r.json()
    return data.get("agri_cats", [])


# -----------------------------
# STEP 3: EXTRACT MAX PAGE
# -----------------------------
def extract_max_page(html):
    soup = BeautifulSoup(html, "html.parser")
    pages = []

    for a in soup.select("a.page-link"):
        txt = a.get_text(strip=True)
        if txt.isdigit():
            pages.append(int(txt))

    return max(pages) if pages else 1


# -----------------------------
# STEP 4: EXTRACT POSTS
# -----------------------------
def extract_posts(html, category):
    soup = BeautifulSoup(html, "html.parser")

    posts = []

    for card in soup.select("div.col-md-3"):
        a = card.select_one("a[href*='/posts/']")
        title = card.select_one("h5.card-title")
        img = card.select_one("img")

        if not a or not title:
            continue

        posts.append({
            "category": category,
            "title": title.get_text(strip=True),
            "url": a["href"],
            "image": img["src"] if img else None
        })

    return posts


# -----------------------------
# STEP 5: FETCH CATEGORY WITH PAGINATION
# -----------------------------
def fetch_category(cat_name):
    encoded = quote(cat_name)
    base_url = f"{BASE}/categories/{encoded}"

    safe_name = cat_name.replace("/", "_")
    out_dir = f"raw/{safe_name}"
    os.makedirs(out_dir, exist_ok=True)

    page = 1
    total_pages = 1
    seen = set()

    all_posts = []

    while True:
        url = base_url if page == 1 else f"{base_url}?page={page}"

        print(f"\n[FETCH] {cat_name} | page {page}")
        r = session.get(url, timeout=30)

        if r.status_code != 200:
            print("BAD STATUS:", r.status_code)
            break

        html = r.text

        # save raw html
        file_path = f"{out_dir}/page_{page}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        # extract posts
        posts = extract_posts(html, cat_name)
        all_posts.extend(posts)

        # dynamic pagination detection
        detected_max = extract_max_page(html)
        if detected_max > total_pages:
            total_pages = detected_max
            print(f"[UPDATE] total_pages -> {total_pages}")

        seen.add(page)

        if page >= total_pages:
            break

        page += 1
        time.sleep(1)

    return all_posts


# -----------------------------
# MAIN RUNNER
# -----------------------------
def main():
    bootstrap()

    cats = get_categories()
    print(f"\nFound categories: {len(cats)}")

    output = defaultdict(list)

    for cat in cats:
        name = cat["text"]
        try:
            posts = fetch_category(name)
            output[name] = posts
        except Exception as e:
            print("[ERROR]", name, e)

    # save structured dataset
    with open("scraped_posts.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nDONE → scraped_posts.json")


if __name__ == "__main__":
    main()