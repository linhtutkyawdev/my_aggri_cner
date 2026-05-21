import requests
import time
from pathlib import Path
import json

BASE_URL = "https://greenwaymyanmar.com/api/web/forum"

def main():
    session = requests.Session()

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    Path("raw/forum").mkdir(parents=True, exist_ok=True)

    page = 1

    while True:
        url = f"{BASE_URL}?page={page}&filter="

        r = session.get(url, headers=headers)

        data = r.json()

        with open(f"raw/forum/page_{page}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.close()

        print(f"saved page {page}")

        # pagination logic
        if not data.get("data"):
            break

        page += 1
        time.sleep(1)


if __name__ == "__main__":
    main()
