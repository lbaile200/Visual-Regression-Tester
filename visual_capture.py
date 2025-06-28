from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from datetime import datetime, timedelta
from PIL import Image
import os, json, shutil
import cv2
import numpy as np

def capture_job(url, site_name, viewport=(1366, 768), cookie_selector=None, wait_time=2):
    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    # Fix for issue where viewport sometimes comes in a little small. This sets the *outer* window size to ensure viewport matches exactly
    from selenium.webdriver.common.window import WindowTypes
    driver.set_window_rect(0, 0, viewport[0], viewport[1])
    import time
    driver.get(url)
    time.sleep(wait_time)
    if cookie_selector:
        try:
            # Wait for element and click it
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            WebDriverWait(driver, wait_time).until(EC.element_to_be_clickable((By.CSS_SELECTOR, cookie_selector))).click()
            print(f"[✓] Accepted cookies for {site_name}")
        except Exception as e:
            print(f"[!] Cookie accept not found or failed for {site_name}: {e}")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = f'screenshots/{site_name}'
    os.makedirs(folder, exist_ok=True)
    screenshot_path = f'{folder}/{ts}.png'
    driver.save_screenshot(screenshot_path)
    driver.quit()

    existing_images = sorted([f for f in os.listdir(folder) if f.endswith('.png')])
    prev_img_path = os.path.join(folder, existing_images[-2]) if len(existing_images) >= 2 else None
    if not prev_img_path:
        return False, None, screenshot_path

    def mse(imageA, imageB):
        return np.mean((imageA.astype("float") - imageB.astype("float")) ** 2)

    def load_cv_image(path):
        return cv2.imread(path)

    img1 = load_cv_image(prev_img_path)
    img2 = load_cv_image(screenshot_path)
    is_significant = False

    if img1 is None or img2 is None:
        print("[ERROR] One of the images could not be loaded.")
    else:
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        error = mse(img1, img2)
        print(f"[DEBUG] MSE for {site_name}: {error}")
        if error > 50:
            is_significant = True
            print(f"[VISUAL CHANGE] Detected for {site_name} at {ts}")
            changes_dir = f"{folder}/changes"
            os.makedirs(changes_dir, exist_ok=True)

            # --- Generate and save a visual diff image ---
            diff_image = cv2.absdiff(img1, img2)
            gray_diff = cv2.cvtColor(diff_image, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
            highlighted = img2.copy()
            highlighted[thresh > 0] = [0, 0, 255]  # Highlight changed pixels in red

            diff_path = os.path.join(changes_dir, f"{ts}_diff.png")
            cv2.imwrite(diff_path, highlighted)
            print(f"[✓] Saved visual diff at: {diff_path}")
        if is_significant:
            changes_dir = f"{folder}/changes"
            os.makedirs(changes_dir, exist_ok=True)

            prev_copy = os.path.join(changes_dir, f"{ts}_prev.png")
            curr_copy = os.path.join(changes_dir, f"{ts}_curr.png")
            shutil.copyfile(prev_img_path, prev_copy)
            shutil.copyfile(screenshot_path, curr_copy)

            change_record = {
                "timestamp": ts,
                "prev": f"/static/screenshots/{site_name}/changes/{ts}_prev.png",
                "curr": f"/static/screenshots/{site_name}/changes/{ts}_curr.png",
                "diff": f"/static/screenshots/{site_name}/changes/{ts}_diff.png",
                "is_significant_change": True,
                "dismissed": False
            }

            change_log = os.path.join(changes_dir, "change_log.json")
            changes = []
            if os.path.exists(change_log):
                with open(change_log, "r") as f:
                    try:
                        changes = json.load(f)
                    except json.JSONDecodeError:
                        print(f"[!] Invalid change_log.json")
            changes.append(change_record)
            with open(change_log, "w") as f:
                json.dump(changes, f, indent=2)

            with open(os.path.join(changes_dir, f"{ts}.json"), "w") as f:
                json.dump(change_record, f, indent=2)
                print(f"[✓] Saved individual change JSON at: {changes_dir}/{ts}.json")

            try:
                from app import monitored_sites, save_sites
                job_id = f"site_{site_name}"
                site = monitored_sites.get(job_id, {})
                site["change_detected"] = True
                monitored_sites[job_id] = site
                save_sites(monitored_sites)
                print(f"[✓] Updated monitored_sites for {job_id}")
            except Exception as e:
                print(f"[!] Failed to update monitored_sites: {e}")

    meta_path = os.path.join(folder, 'metadata.json')
    metadata = []
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                print(f"[!] Invalid metadata file: {f.name}")
    metadata.append({
        "timestamp": ts,
        "site": site_name,
        "path": screenshot_path,
        "is_significant_change": is_significant
    })
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    cleanup_old_screenshots(site_name)

    return is_significant, prev_img_path, screenshot_path

def cleanup_old_screenshots(site_name, keep_minutes=1440):
    folder = f'screenshots/{site_name}'
    meta_path = f'{folder}/metadata.json'
    if not os.path.exists(meta_path):
        return

    with open(meta_path, 'r') as f:
        try:
            metadata = json.load(f)
        except json.JSONDecodeError:
            print(f"[!] Invalid metadata in {meta_path}")
            return

    now = datetime.now()
    updated = []
    for item in metadata:
        path = item.get('path', '')

        # Protect anything inside the /changes/ directory
        if "/changes/" in path:
            updated.append(item)
            continue

        try:
            ts = datetime.strptime(item['timestamp'], '%Y%m%d_%H%M%S')
        except ValueError:
            print(f"[!] Skipping malformed timestamp: {item.get('timestamp')}")
            continue

        age = now - ts
        keep = item.get('is_significant_change', False) or age < timedelta(minutes=keep_minutes)
        if keep:
            updated.append(item)
        else:
            try:
                os.remove(path)
                print(f"[🗑] Deleted old screenshot: {path}")
            except FileNotFoundError:
                pass

    with open(meta_path, 'w') as f:
        json.dump(updated, f, indent=2)
