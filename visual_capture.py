from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from datetime import datetime
import os
import shutil

#def capture_job(url, site_name):
#    options = Options()
#    options.add_argument('--headless')
#    driver = webdriver.Firefox(options=options)
#    driver.set_window_size(1366, 768)
#    driver.get(url)
#    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
#    folder = f'screenshots/{site_name}'
#    os.makedirs(folder, exist_ok=True)
#    driver.save_screenshot(f'{folder}/{ts}.png')
#    driver.quit()

from PIL import Image, ImageChops
from datetime import datetime, timedelta
import os, json

def capture_job(url, site_name):
    # Step 1: Take screenshot
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    driver.set_window_size(1366, 768)
    driver.get(url)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = f'screenshots/{site_name}'
    os.makedirs(folder, exist_ok=True)
    screenshot_path = f'{folder}/{ts}.png'
    driver.save_screenshot(screenshot_path)
    driver.quit()

   # Step 2: Diff with previous screenshot
    prev_img_path = None
    existing_images = sorted([f for f in os.listdir(folder) if f.endswith('.png')])
    if len(existing_images) >= 2:
        prev_img_path = os.path.join(folder, existing_images[-2])

    is_significant = False
    if prev_img_path and os.path.exists(prev_img_path):
        prev_img = Image.open(prev_img_path)
        curr_img = Image.open(screenshot_path)

    import cv2
    import numpy as np

    def mse(imageA, imageB):
        # Mean Squared Error
        err = np.mean((imageA.astype("float") - imageB.astype("float")) ** 2)
        return err

    def load_cv_image(path):
        return cv2.imread(path)

    img1 = load_cv_image(prev_img_path)
    img2 = load_cv_image(screenshot_path)

    if img1 is None or img2 is None:
        print("[ERROR] One of the images could not be loaded for comparison.")
    else:
        # Resize if necessary (not required if both screenshots are same size)
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

        error = mse(img1, img2)
        print(f"[DEBUG] MSE diff for {site_name} = {error}")

        # Lower = more similar. You can tune this.
        if error > 50:  # threshold can be lowered for sensitivity
            is_significant = True
            print(f"[VISUAL CHANGE] Change detected for {site_name} at {ts}")
        else:
            print(f"[NO CHANGE] Images are similar (MSE={error})")
        if is_significant:
            # Save both current and previous as permanent "change snapshots"
            changes_dir = f"{folder}/changes"
            os.makedirs(changes_dir, exist_ok=True)

            prev_copy = os.path.join(changes_dir, f"{ts}_prev.png")
            curr_copy = os.path.join(changes_dir, f"{ts}_curr.png")

            shutil.copyfile(prev_img_path, prev_copy)
            shutil.copyfile(screenshot_path, curr_copy)

            # Optionally log this in a separate JSON file
            change_log = os.path.join(changes_dir, "change_log.json")
            changes = []
            if os.path.exists(change_log):
                with open(change_log, "r") as f:
                    changes = json.load(f)

            changes.append({
                "timestamp": ts,
                "prev": f"/static/screenshots/{site_name}/changes/{ts}_prev.png",
                "curr": f"/static/screenshots/{site_name}/changes/{ts}_curr.png"
            })

            with open(change_log, "w") as f:
                json.dump(changes, f, indent=2)


    # Step 3: Save metadata
    meta_path = os.path.join(folder, 'metadata.json')
    metadata = []
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            metadata = json.load(f)

    metadata.append({
        "timestamp": ts,
        "site": site_name,
        "path": screenshot_path,
        "is_significant_change": is_significant
    })

    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    # Step 4: Cleanup old
    cleanup_old_screenshots(site_name)

def cleanup_old_screenshots(site_name, keep_minutes=1440):
    folder = f'screenshots/{site_name}'
    meta_path = f'{folder}/metadata.json'

    if not os.path.exists(meta_path):
        return

    with open(meta_path, 'r') as f:
        metadata = json.load(f)

    now = datetime.now()
    updated = []

    for item in metadata:
        ts = datetime.strptime(item['timestamp'], '%Y%m%d_%H%M%S')
        age = now - ts
        keep = item.get('is_significant_change', False) or age < timedelta(minutes=keep_minutes)
        if keep:
            updated.append(item)
        else:
            try:
                os.remove(item['path'])
            except FileNotFoundError:
                pass

    with open(meta_path, 'w') as f:
        json.dump(updated, f, indent=2)
