from flask import Flask, request, jsonify, render_template, send_from_directory
from scheduler import schedule_job, remove_job, scheduler
from visual_capture import capture_job
import json, os, glob
from cleanup import cleanup_screenshots
app = Flask(__name__)
#scheduler.start()
#DATA_FILE is where all the sites are stored.  Ideally this could be a database if you wanted to scale.  For my homelab, no point.
DATA_FILE = "sites.json"
CHANGE_DIR = "changes"

# --------------------
# Utility Functions 
# --------------------
#if DATA_FILE exists, return full JSON array
def load_sites():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("[ERROR] Invalid sites.json")
    return {}
#dump returned data on 'sites' to sites.json
def save_sites(sites):
    with open(DATA_FILE, "w") as f:
        json.dump(sites, f, indent=2)

monitored_sites = load_sites()

# --------------------
# Screenshot Loading
# --------------------
def get_recent_screenshots(site_name, count=6):
    folder = f'screenshots/{site_name}'
    images = sorted(
        glob.glob(f"{folder}/*.png"),
        key=lambda x: os.path.getmtime(x),
        reverse=True
    )
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

### Read /changes folder latest JSON for changes
def load_changes(site_name):
    log_path = f"screenshots/{site_name}/changes/change_log.json"
    if not os.path.exists(log_path):
        return []

    try:
        with open(log_path, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                changes = data
            else:
                changes = [data]
    except Exception as e:
        print(f"[!] Failed to load change_log.json: {e}")
        return []

    # Validate image paths
    validated = []
    for change in changes:
        prev_path = change.get("prev", "").replace("/static/", "")
        curr_path = change.get("curr", "").replace("/static/", "")
        if os.path.exists(prev_path) and os.path.exists(curr_path):
            validated.append(change)

    validated.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
    return validated

# --------------------
# Flask Routes
# --------------------
### The dashboard
@app.route("/")
def dashboard():
    sites_with_images = {}
    for job_id, site in monitored_sites.items():
        site_name = site["site_name"]

        try:
            images, _ = get_recent_screenshots(site_name)
        except Exception as e:
            print(f"[!] Failed to load screenshots for {site_name}: {e}")
            images = []

        try:
            changes = load_changes(site_name)
        except Exception as e:
            print(f"[!] Failed to load changes for {site_name}: {e}")
            changes = []

        last_dismissed = site.get("last_dismissed")
        latest_ts = max((c["timestamp"] for c in changes if "timestamp" in c), default=None)
        change_detected = latest_ts and latest_ts != last_dismissed

        sites_with_images[job_id] = {
            **site,
            "images": images,
            "changes": changes,
            "last_dismissed": last_dismissed,
            "change_detected": change_detected
        }

    return render_template("dashboard.html", sites=sites_with_images)

###The individual site, filmstrip, etc
@app.route("/site/<site_name>")
def site_detail(site_name):
    job_id = f"site_{site_name}"
    if job_id not in monitored_sites:
        return "Site not found", 404

    site = monitored_sites[job_id]

    #Provide a default viewport if it's missing
    if "viewport" not in site or not isinstance(site["viewport"], list) or len(site["viewport"]) != 2:
        site["viewport"] = [1366, 768]

    images, _ = get_recent_screenshots(site_name)
    changes = load_changes(site_name)
    last_dismissed = site.get("last_dismissed")
    latest_ts = max((c.get("timestamp") for c in changes if "timestamp" in c), default=None)
    change_detected = latest_ts and latest_ts != last_dismissed

    return render_template("site_detail.html", site={
        **site,
        "images": images,
        "changes": changes,
        "last_dismissed": last_dismissed,
        "change_detected": change_detected
    })

### passback for editing
@app.route("/edit-site/<site_name>", methods=["POST"])
def edit_site(site_name):
    job_id = f"site_{site_name}"
    if job_id not in monitored_sites:
        return jsonify({"error": "Site not found"}), 404

    data = request.json
    site = monitored_sites[job_id]

    # Make sure "site_name" is always included
    site["site_name"] = site.get("site_name", site_name)

    # Assign safe values for all editable fields
    site["url"] = data.get("url", site.get("url", ""))
    site["interval_minutes"] = data.get("interval_minutes", site.get("interval_minutes", 10))
    site["viewport"] = data.get("viewport", site.get("viewport", [1366, 768]))
    site["cookie_accept_selector"] = data.get("cookie_accept_selector", site.get("cookie_accept_selector", None))
    site["wait_time"] = float(data.get("wait_time", site.get("wait_time", 2)))

    # Save updated site info
    monitored_sites[job_id] = site
    save_sites(monitored_sites)

    # Pull safe values for the scheduled job
    url = site["url"]
    name = site["site_name"]
    interval = site["interval_minutes"]
    viewport = site["viewport"]
    selector = site.get("cookie_accept_selector")
    wait_time = site.get("wait_time", 4000)

    remove_job(job_id)
    schedule_job(
        job_id,
        lambda url=url, name=name, viewport=viewport, selector=selector, wait_time=wait_time:
            capture_job(url, name, viewport, selector, wait_time),
        interval
    )

    return jsonify({"status": "Site updated"})

### pause and resume.  I used chatGPT for this bc was in a hurry...
from flask import abort

@app.route("/pause-site/<site_name>", methods=["POST"])
def pause_site(site_name):
    job_id = f"site_{site_name}"
    if job_id not in monitored_sites:
        return jsonify({"error": "Site not found"}), 404

    remove_job(job_id)
    monitored_sites[job_id]["paused"] = True
    save_sites(monitored_sites)
    return jsonify({"status": "paused"})


@app.route("/resume-site/<site_name>", methods=["POST"])
def resume_site(site_name):
    job_id = f"site_{site_name}"
    if job_id not in monitored_sites:
        return jsonify({"error": "Site not found"}), 404

    site = monitored_sites[job_id]
    if not site.get("paused"):
        return jsonify({"error": "Site is not paused"}), 400

    # Re-schedule the job
    url = site["url"]
    name = site["site_name"]
    interval = site["interval_minutes"]
    viewport = site.get("viewport", [1366, 768])
    selector = site.get("cookie_accept_selector")
    wait_time = site.get("wait_time", 2)

    schedule_job(
        job_id,
        lambda url=url, name=name, viewport=viewport, selector=selector, wait=wait_time:
            capture_job(url, name, viewport, selector, wait),
        interval
    )

    site["paused"] = False
    monitored_sites[job_id] = site
    save_sites(monitored_sites)

    return jsonify({"status": "resumed"})

### Literally all this for a favicon.  Flask is not perfect.
@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'gptFavicon.png', mimetype='image/png')

### let us view screenshots in browser (and lightbox, and filmstrip)
@app.route('/static/screenshots/<path:filename>')
def serve_screenshot(filename):
    return send_from_directory('screenshots', filename)

### Literally all this for CSS and JS.  Again, flask is not perfect.
@app.route('/css/<path:filename>')
def custom_css(filename):
    return send_from_directory('templates/css', filename)

@app.route('/js/<path:filename>')
def custom_js(filename):
    return send_from_directory('templates/js', filename)

###how we add a site, basically this just writes to a .json file that other jobs read from to do their thing.  For better scale and multiuser we should make this a database one day.  
@app.route("/add-site", methods=["POST"])
def add_site():
    data = request.json
    job_id = f"site_{data['site_name']}"
    url = data['url']
    site_name = data['site_name']
    interval = data['interval_minutes']
    viewport = data.get('viewport', [1366, 768])  # default fallback
    cookie_selector = data.get('cookie_accept_selector', None)
    wait_time = data.get('wait_time', 2)  # default to 2 seconds

    def job():
        if monitored_sites.get(job_id, {}).get("paused"):
            print(f"[⏸] Skipping {job_id} — site is paused.")
            return

        changed, before, after = capture_job(url, site_name, viewport)

        if changed:
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
        "interval_minutes": interval,
        "viewport": viewport,
        "cookie_accept_selector": cookie_selector,
        "wait_time": wait_time
    }

    save_sites(monitored_sites)
    return jsonify({"status": "scheduled"})

### passback for removal
@app.route("/remove-site/<job_id>", methods=["DELETE"])
def remove_site(job_id):
    remove_job(job_id)
    if job_id in monitored_sites:
        monitored_sites.pop(job_id)
        save_sites(monitored_sites)
    return jsonify({"status": "removed"})

### passback for calls to dismiss alerts.  This could use some work I think...
@app.route("/dismiss-alert/<site_name>", methods=["POST"])
def dismiss_alert(site_name):
    print(f"[✓] Dismiss request received for: {site_name}")

    job_id = f"site_{site_name}"
    if job_id not in monitored_sites:
        print(f"[✗] Job ID not found: {job_id}")
        return jsonify({"error": "Site not found"}), 404

    site = monitored_sites[job_id]
    changes = load_changes(site_name)

    if not changes:
        print("[!] No changes to dismiss.")
        return jsonify({"error": "No changes to dismiss"}), 400

    # Get latest change by timestamp
    latest = sorted(changes, key=lambda c: c.get("timestamp", ""), reverse=True)[0]
    ts = latest["timestamp"]
    json_path = f"screenshots/{site_name}/changes/{ts}.json"

    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["dismissed"] = True
        elif isinstance(data, list):
            if data:
                data[0]["dismissed"] = True

        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)

        # Optionally: track dismissal timestamp
        site["last_dismissed"] = ts
        monitored_sites[job_id] = site
        save_sites(monitored_sites)

        print("[✓] Dismissal saved to file and memory.")
        return jsonify({"status": "dismissed"})

    except Exception as e:
        print(f"[!] Failed to update change file: {e}")
        return jsonify({"error": "Failed to dismiss"}), 500


#prtg, uptime kuma (or other monitoring) status page, displays site names and alert status
@app.route("/status")
def status_page():
    names = []
    statuses = []

    for site in monitored_sites.values():
        site_name = site.get("site_name", "unknown")
        if site.get("paused"):
            statuses.append("[0]")
            names.append(site_name)
            continue
        site_name = site["site_name"]
        names.append(site_name)

        changes = load_changes(site_name)
        last_dismissed = site.get("last_dismissed")
        latest_ts = max((c.get("timestamp") for c in changes if "timestamp" in c), default=None)
        has_alert = latest_ts and latest_ts != last_dismissed
        statuses.append("[1]" if has_alert else "[0]")

    response = f"{' | '.join(names)}\n{''.join(statuses)}"
    return response, 200, {'Content-Type': 'text/plain; charset=utf-8'}
###20250831_Lucas
# dismiss all
@app.route("/dismiss-all", methods=["POST"])
def dismiss_all_alerts():
    for job_id, site in monitored_sites.items():
        site_name = site["site_name"]
        changes = load_changes(site_name)
        latest_ts = max((c.get("timestamp") for c in changes if "timestamp" in c), default=None)

        if latest_ts:
            site["last_dismissed"] = latest_ts
            monitored_sites[job_id] = site

    save_sites(monitored_sites)
    return jsonify({"status": "all dismissed"})

# --------------------
# Scheduler Bootstrap
# --------------------
from apscheduler.triggers.interval import IntervalTrigger
#define our variables for various sites we've added.
for job_id, site in monitored_sites.items():
    url = site["url"]
    name = site["site_name"]
    interval = site["interval_minutes"]
    viewport = site.get("viewport", [1366, 768])
    cookie_selector = site.get("cookie_accept_selector")
    wait_time = site.get("wait_time", 2)
    is_paused = site.get("paused", False)

    def make_job(url, name, viewport, selector, wait, paused, job_id):
        def job():
            if paused:
                print(f"[⏸] Skipping {job_id} — site is paused.")
                return
            capture_job(url, name, viewport, selector, wait)
        return job

    schedule_job(
        job_id,
        make_job(url, name, viewport, cookie_selector, wait_time, is_paused, job_id),
        interval
    )

# Schedule screenshot cleanup every hour, see cleanup.py for config there.
scheduler.add_job(
    func=cleanup_screenshots,
    trigger=IntervalTrigger(hours=1),
    id='cleanup-job',
    name='Clean up old screenshots',
    replace_existing=True
)
#define how flask runs and on what port.  0.0.0.0 is listening everywhere, can also specify specific IP to listen on.
if __name__ == "__main__":
    scheduler.start()
    app.run(host='0.0.0.0', port=5006)
