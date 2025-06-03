from flask import Flask, request, jsonify, render_template
from scheduler import schedule_job, remove_job, scheduler
from visual_capture import capture_job
import json, os
import glob

def get_recent_screenshots(site_name, count=6):
    folder = f'screenshots/{site_name}'
    meta_path = f'{folder}/metadata.json'
    images = []
    change_flag = False

    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            metadata = json.load(f)
        recent = sorted(metadata, key=lambda x: x['timestamp'], reverse=True)[:count]
        images = [entry['path'].replace('screenshots/', '/static/screenshots/') for entry in recent]
        if recent and recent[0].get("is_significant_change", False):
            change_flag = True

    return images, change_flag

app = Flask(__name__)
scheduler.start()

DATA_FILE = "sites.json"

def load_sites():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_sites(sites):
    with open(DATA_FILE, "w") as f:
        json.dump(sites, f, indent=2)

monitored_sites = load_sites()

# Rehydrate on startup
for job_id, site in monitored_sites.items():
    schedule_job(job_id, lambda url=site['url'], name=site['site_name']: capture_job(url, name), site['interval_minutes'])

def load_changes(site_name):
    path = f"screenshots/{site_name}/changes/change_log.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []

def load_dismissed_timestamp(site_name):
    path = f"screenshots/{site_name}/dismissed.json"
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f).get("last_dismissed")
    return None

@app.route("/")
def dashboard():
    sites_with_images = {}
    for job_id, site in monitored_sites.items():
        images, change_flag = get_recent_screenshots(site["site_name"])
        changes = load_changes(site["site_name"])
        last_dismissed = load_dismissed_timestamp(site["site_name"])
        sites_with_images[job_id] = {
            **site,
            "images": images,
            "change_detected": change_flag,
            "changes": changes,
            "last_dismissed": last_dismissed
        }
    return render_template("dashboard.html", sites=sites_with_images)


from flask import send_from_directory
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

    schedule_job(job_id, lambda: capture_job(data['url'], data['site_name']), data['interval_minutes'])
    monitored_sites[job_id] = data
    save_sites(monitored_sites)
    return jsonify({"status": "scheduled"})

@app.route("/remove-site/<job_id>", methods=["DELETE"])
def remove_site(job_id):
    remove_job(job_id)
    if job_id in monitored_sites:
        monitored_sites.pop(job_id)
        save_sites(monitored_sites)
    return jsonify({"status": "removed"})

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/dismiss-alert/<site_name>", methods=["POST"])
def dismiss_alert(site_name):
    folder = f'screenshots/{site_name}'
    change_log_path = os.path.join(folder, 'changes/change_log.json')
    dismissed_path = os.path.join(folder, 'dismissed.json')

    if not os.path.exists(change_log_path):
        return jsonify({"error": "No changes logged"}), 400

    with open(change_log_path, 'r') as f:
        changes = json.load(f)

    if changes:
        last_ts = changes[-1]["timestamp"]
        with open(dismissed_path, 'w') as f:
            json.dump({"last_dismissed": last_ts}, f)

    return jsonify({"status": "dismissed"})
