from flask import Flask, request, jsonify, render_template, send_from_directory
from scheduler import schedule_job, remove_job, scheduler
from visual_capture import capture_job
import json, os, glob

app = Flask(__name__)
scheduler.start()

DATA_FILE = "sites.json"
CHANGE_DIR = "changes"

# --------------------
# Utility Functions
# --------------------
def load_sites():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("[ERROR] Invalid sites.json")
    return {}

def save_sites(sites):
    with open(DATA_FILE, "w") as f:
        json.dump(sites, f, indent=2)

monitored_sites = load_sites()

# --------------------
# Screenshot Loading
# --------------------
def get_recent_screenshots(site_name, count=6):
    folder = f'screenshots/{site_name}'
    if not os.path.exists(folder):
        return [], False

    images = sorted(glob.glob(f"{folder}/*.png"), reverse=True)
    images = [img.replace("screenshots/", "/static/screenshots/") for img in images[:count]]

    change_flag = False
    meta_path = os.path.join(folder, 'metadata.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            try:
                metadata = json.load(f)
                recent = sorted(metadata, key=lambda x: x['timestamp'], reverse=True)[:count]
                if recent and recent[0].get("is_significant_change", False):
                    change_flag = True
            except json.JSONDecodeError:
                print(f"[!] Skipping invalid metadata file: {meta_path}")
    return images, change_flag

def load_changes(site_name):
    path = f"screenshots/{site_name}/changes"
    if not os.path.exists(path):
        return []
    changes = []
    for json_file in sorted(os.listdir(path), reverse=True):
        if json_file.endswith(".json"):
            try:
                with open(os.path.join(path, json_file), "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        changes.extend(data)
                    elif isinstance(data, dict):
                        changes.append(data)
            except Exception as e:
                print(f"[!] Failed to load change file {json_file}: {e}")
    return changes

# --------------------
# Flask Routes
# --------------------
@app.route("/")
def dashboard():
    sites_with_images = {}
    for job_id, site in monitored_sites.items():
        site_name = site["site_name"]
        images, _ = get_recent_screenshots(site_name)
        changes = load_changes(site_name)
        last_dismissed = site.get("last_dismissed")
        latest_ts = changes[-1]["timestamp"] if changes else None
        change_detected = latest_ts and latest_ts != last_dismissed

        sites_with_images[job_id] = {
            **site,
            "images": images,
            "changes": changes,
            "last_dismissed": last_dismissed,
            "change_detected": change_detected
        }

    return render_template("dashboard.html", sites=sites_with_images)

@app.route('/static/screenshots/<path:filename>')
def serve_screenshot(filename):
    return send_from_directory('screenshots', filename)

@app.route('/css/<path:filename>')
def custom_css(filename):
    return send_from_directory('templates/css', filename)

@app.route('/js/<path:filename>')
def custom_js(filename):
    return send_from_directory('templates/js', filename)

@app.route("/add-site", methods=["POST"])
def add_site():
    data = request.json
    job_id = f"site_{data['site_name']}"
    url = data['url']
    site_name = data['site_name']
    interval = data['interval_minutes']

    def job():
        changed, before, after = capture_job(url, site_name)
        if changed:
            print(f"[VISUAL CHANGE] Change detected for {site_name} at {after}")
            ts = os.path.basename(after).replace(".png", "")
            change_dir = f"screenshots/{site_name}/changes"
            os.makedirs(change_dir, exist_ok=True)
            metadata = {
                "timestamp": ts,
                "prev": before.replace("screenshots/", "/static/screenshots/"),
                "curr": after.replace("screenshots/", "/static/screenshots/")
            }
            with open(f"{change_dir}/{ts}.json", "w") as f:
                json.dump(metadata, f, indent=2)

    schedule_job(job_id, job, interval)

    monitored_sites[job_id] = {
        "url": url,
        "site_name": site_name,
        "interval_minutes": interval
    }

    save_sites(monitored_sites)
    return jsonify({"status": "scheduled"})

@app.route("/remove-site/<job_id>", methods=["DELETE"])
def remove_site(job_id):
    remove_job(job_id)
    if job_id in monitored_sites:
        monitored_sites.pop(job_id)
        save_sites(monitored_sites)
    return jsonify({"status": "removed"})

@app.route("/dismiss-alert/<site_name>", methods=["POST"])
def dismiss_alert(site_name):
    for job_id, site in monitored_sites.items():
        if site["site_name"] == site_name:
            change_log_path = f"screenshots/{site_name}/changes/change_log.json"
            if os.path.exists(change_log_path):
                with open(change_log_path, "r") as f:
                    try:
                        changes = json.load(f)
                        if isinstance(changes, list) and changes:
                            latest_ts = changes[-1]["timestamp"]
                            site["last_dismissed"] = latest_ts
                            print(f"[INFO] Dismissed alert for {site_name} at {latest_ts}")
                            save_sites(monitored_sites)
                            return jsonify({"status": "dismissed"})
                        else:
                            print(f"[ERROR] change_log.json for {site_name} is not a valid list")
                    except json.JSONDecodeError:
                        print(f"[ERROR] Invalid JSON in change_log.json for {site_name}")
            break
    return jsonify({"status": "error"})

# --------------------
# Scheduler Bootstrap
# --------------------
for job_id, site in monitored_sites.items():
    schedule_job(job_id, lambda url=site['url'], name=site['site_name']: capture_job(url, name), site['interval_minutes'])

if __name__ == "__main__":
    app.run(host='0.0.0.0')
