import os
import json
from collections import defaultdict

# Folder containing JSON files
INPUT_DIR = "raw/forum"

# Output folder
OUTPUT_DIR = "raw/forum_txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Store text grouped by category.type
grouped_bodies = defaultdict(list)

# Read all JSON files
for filename in os.listdir(INPUT_DIR):

    if not filename.endswith(".json"):
        continue

    filepath = os.path.join(INPUT_DIR, filename)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        # Your files contain an array in "data"
        posts = json_data.get("data", [])

        for post in posts:

            # Group by category.type
            category_type = (
                post.get("category", {}).get("type", "unknown")
            )

            # Main post body
            body = post.get("body")
            if body:
                grouped_bodies[category_type].append(
                    body.strip()
                )

            # Replies bodies
            for reply in post.get("replies", []):
                reply_body = reply.get("body")

                if reply_body:
                    grouped_bodies[category_type].append(
                        reply_body.strip()
                    )

    except Exception as e:
        print(f"Error reading {filename}: {e}")

# Save grouped txt files
for category_type, bodies in grouped_bodies.items():

    safe_name = "".join(
        c if c.isalnum() or c in ("_", "-", " ")
        else "_"
        for c in category_type
    ).strip()

    output_file = os.path.join(
        OUTPUT_DIR,
        f"{safe_name}.txt"
    )

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(bodies))

    print(f"Saved: {output_file}")

print("Done.")