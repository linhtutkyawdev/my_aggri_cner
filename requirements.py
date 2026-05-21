import requests
import json

session = requests.Session()

session.headers.update({
    "accept": "application/json",
    "user-agent": "Mozilla/5.0",
})

response = session.get(
    "https://greenwaymyanmar.com/api/web/forum/requirements"
)

print("Status:", response.status_code)

data = response.json()

# Save response to JSON file
with open("forum_requirements.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("Saved to forum_requirements.json")