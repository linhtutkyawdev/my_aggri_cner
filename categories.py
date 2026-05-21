import requests
from urllib.parse import quote
import os
import time

session = requests.Session()

session.headers.update({
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
})

# Step 1: Get agri categories
response = session.get(
    "https://greenwaymyanmar.com/api/web/forum/requirements"
)

data = response.json()

agri_cats = data.get("agri_cats", [])

print(f"Found {len(agri_cats)} agri categories")

# Create output folder
os.makedirs("raw/categories", exist_ok=True)

# Step 2: Visit each category page
for cat in agri_cats:
    cat_name = cat["text"]

    # URL encode Myanmar text
    encoded_name = quote(cat_name)

    url = f"https://greenwaymyanmar.com/categories/{encoded_name}"

    print(f"\nFetching: {cat_name}")
    print(url)

    try:
        page_response = session.get(url)

        print("Status:", page_response.status_code)

        # Save HTML
        file_path = f"raw/categories/{cat_name}.html"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(page_response.text)

        print(f"Saved -> {file_path}")

        # optional delay
        time.sleep(1)

    except Exception as e:
        print("Error:", e)