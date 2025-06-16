import os
import time
from datetime import datetime, timedelta

### when to remove based on your needs.  This config requires about 400MB (persistent) per-site.
SCREENSHOT_BASE = "screenshots"
KEEP_SCREENSHOTS_FOR_HOURS = 4
KEEP_CHANGES_FOR_DAYS = 7

def cleanup_screenshots():
    now = time.time()
    cutoff_main = now - (KEEP_SCREENSHOTS_FOR_HOURS * 3600)
    cutoff_changes = now - (KEEP_CHANGES_FOR_DAYS * 86400)

    for site in os.listdir(SCREENSHOT_BASE):
        site_path = os.path.join(SCREENSHOT_BASE, site)
        if not os.path.isdir(site_path):
            continue

        # 1. Clean regular screenshots
        for file in os.listdir(site_path):
            file_path = os.path.join(site_path, file)
            if os.path.isfile(file_path) and file.endswith(".png"):
                if os.path.getmtime(file_path) < cutoff_main:
                    print(f"🗑️ Deleting old screenshot: {file_path}")
                    os.remove(file_path)

        # 2. Clean /changes subfolder (if exists)
        changes_path = os.path.join(site_path, "changes")
        if os.path.exists(changes_path):
            for file in os.listdir(changes_path):
                file_path = os.path.join(changes_path, file)
                if os.path.isfile(file_path) and file.endswith(".png"):
                    if os.path.getmtime(file_path) < cutoff_changes:
                        print(f"🗑️ Deleting old change image: {file_path}")
                        os.remove(file_path)

if __name__ == "__main__":
    cleanup_screenshots()