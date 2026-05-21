import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import os
import time

session = requests.Session()

session.headers.update({
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
})

api_url = "https://greenwaymyanmar.com/api/web/forum/requirements"
data = session.get(api_url).json()

agri_cats = data.get("agri_cats", [])

base_folder = "raw/posts"
os.makedirs(base_folder, exist_ok=True)


def extract_max_page(html):
    soup = BeautifulSoup(html, "html.parser")
    pages = []

    for a in soup.select("a.page-link"):
        txt = a.get_text(strip=True)
        if txt.isdigit():
            pages.append(int(txt))

    return max(pages) if pages else 1


for cat in agri_cats:
    cat_name = cat["text"]
    encoded = quote(cat_name)

    base_url = f"https://greenwaymyanmar.com/categories/{encoded}"

    print("\n======================")
    print("Category:", cat_name)

    safe_name = cat_name.replace("/", "_")

    total_pages = 1
    fetched_pages = set()

    page = 1

    while True:
        url = base_url if page == 1 else f"{base_url}?page={page}"

        print("Fetching:", url)

        r = session.get(url)
        html = r.text

        # save
        file_path = f"{base_folder}/{safe_name}_page{page}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        print("Saved:", file_path)

        fetched_pages.add(page)

        # 🔥 dynamically detect max page from THIS page
        detected_max = extract_max_page(html)

        if detected_max > total_pages:
            print(f"Updating total_pages: {total_pages} → {detected_max}")
            total_pages = detected_max

        # stop condition
        if page >= total_pages:
            break

        page += 1
        time.sleep(1)