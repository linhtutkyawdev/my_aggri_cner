import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
import time
import hashlib
import chardet
from collections import deque, defaultdict

BASE = "https://greenwaymyanmar.com"

# ----------------------------
# SESSION (IMPORTANT)
# ----------------------------
session = requests.Session()
session.headers.update({
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64)",
    "accept": "text/html,application/xhtml+xml"
})

# ----------------------------
# OUTPUT FILES
# ----------------------------
os.makedirs("output", exist_ok=True)

POST_FILE = "output/posts.jsonl"
TREE_FILE = "output/url_tree.json"

# ----------------------------
# STATE
# ----------------------------
visited = set()
queue = deque([BASE])

url_tree = {}

# ----------------------------
# HELPERS
# ----------------------------

def is_valid(url):
    return urlparse(url).netloc == urlparse(BASE).netloc


def classify(url):
    path = urlparse(url).path

    if "/posts/" in path and path != "/posts":
        return "post"
    if "/categories" in path:
        return "category"
    if "/posts" in path:
        return "post_list"
    return "other"


def merge_tree(tree, parts):
    cur = tree
    for i, p in enumerate(parts):
        if not p:
            continue
        if i == len(parts) - 1:
            cur.setdefault(p, "__leaf__")
        else:
            cur.setdefault(p, {})
            if isinstance(cur[p], str):
                cur[p] = {}
            cur = cur[p]


def build_route(url):
    path = urlparse(url).path.strip("/")
    if not path:
        return []

    parts = path.split("/")
    merge_tree(url_tree, parts)
    return parts


# ----------------------------
# SAFE FETCH (NO CRASH)
# ----------------------------

def fetch(url):
    try:
        r = session.get(url, timeout=15, allow_redirects=True)

        ctype = r.headers.get("content-type", "")

        # skip non-html
        if "text/html" not in ctype:
            print("SKIP (non-html):", url)
            return None

        encoding = r.encoding or chardet.detect(r.content)["encoding"]

        html = r.content.decode(encoding or "utf-8", errors="ignore")

        if "<html" not in html.lower():
            print("SKIP (invalid html):", url)
            return None

        return html

    except Exception as e:
        print("ERROR:", url, e)
        return None


# ----------------------------
# SAVE POSTS (REAL-TIME)
# ----------------------------

def save_post(post):
    with open(POST_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(post, ensure_ascii=False) + "\n")


# ----------------------------
# PARSE POST
# ----------------------------

def parse_post(url, html):
    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("h1.page-title")
    title = title.text.strip() if title else None

    category = soup.select_one(".page-meta a")
    category = category.text.strip() if category else None

    image = soup.select_one(".page-cover img")
    image = image["src"] if image else None

    content_div = soup.select_one(".page-content")
    content = content_div.get_text(" ", strip=True) if content_div else ""

    links = []
    if content_div:
        for a in content_div.find_all("a", href=True):
            links.append(urljoin(BASE, a["href"]))

    route = build_route(url)

    return {
        "url": url,
        "title": title,
        "category": category,
        "image": image,
        "content": content,
        "internal_links": list(set(links)),
        "route": route
    }


# ----------------------------
# EXTRACT LINKS
# ----------------------------

def extract_links(soup, base_url):
    links = set()

    for a in soup.find_all("a", href=True):
        u = urljoin(base_url, a["href"])
        if is_valid(u):
            links.add(u)

    return links


# ----------------------------
# MAIN CRAWLER
# ----------------------------

while queue:
    url = queue.popleft()

    if url in visited:
        continue

    visited.add(url)

    print("\n================================================")
    print("Fetching:", url)

    html = fetch(url)
    if not html:
        continue

    soup = BeautifulSoup(html, "html.parser")
    page_type = classify(url)

    # ---------------- POST PAGE ----------------
    if page_type == "post":
        post = parse_post(url, html)
        save_post(post)

        print("POST:", post["title"])

    # ---------------- LINK DISCOVERY ----------------
    links = extract_links(soup, url)
    print("Discovered:", len(links))

    for link in links:
        if link not in visited:
            queue.append(link)

    time.sleep(0.3)


# ----------------------------
# SAVE TREE STRUCTURE
# ----------------------------

with open(TREE_FILE, "w", encoding="utf-8") as f:
    json.dump(url_tree, f, ensure_ascii=False, indent=2)

print("\nDONE")
print("Visited:", len(visited))
print("Posts saved:", sum(1 for _ in open(POST_FILE, "r", encoding="utf-8")))