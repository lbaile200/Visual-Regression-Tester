console.log("dashboard.js loaded");
function showLightbox(src) {
  const lightbox = document.getElementById("lightbox");
  const img = document.getElementById("lightbox-img");
  img.src = src;
  lightbox.classList.add("show");
}

function closeLightbox(event) {
  // only close if you click outside the image
  if (event.target.id === "lightbox") {
    const lightbox = document.getElementById("lightbox");
    lightbox.classList.remove("show");
    document.getElementById("lightbox-img").src = "";
  }
}

function addSite() {
    const url = document.getElementById("url").value;
    const site_name = document.getElementById("site_name").value;
    const interval = parseInt(document.getElementById("interval").value);
    const width = parseInt(document.getElementById("viewport_width").value) || 1366;
    const height = parseInt(document.getElementById("viewport_height").value) || 768;

    fetch("/add-site", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            url,
            site_name,
            interval_minutes: interval,
            viewport: [width, height]
        })
    }).then(() => location.reload());
}

function removeSite(job_id) {
    fetch("/remove-site/" + job_id, {
        method: "DELETE"
    }).then(() => location.reload());
}

function dismissAlert(siteName, buttonEl) {
  fetch(`/dismiss-alert/${siteName}`, {
    method: "POST"
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === "dismissed") {
      const alertBox = buttonEl.closest(".alert");
      if (alertBox) alertBox.remove();
    } else {
      alert("Dismiss failed: " + (data.error || "unknown"));
    }
  })
  .catch(err => {
    console.error("Fetch error:", err);
    alert("Network or server error occurred");
  });
}


function toggleHistory(siteName) {
    const section = document.getElementById(`history-${siteName}`);
    if (section.style.display === "none") {
        section.style.display = "block";
    } else {
        section.style.display = "none";
    }
}
