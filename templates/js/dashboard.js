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

    fetch("/add-site", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            url: url,
            site_name: site_name,
            interval_minutes: interval
        })
    }).then(() => location.reload());
}

function removeSite(job_id) {
    fetch("/remove-site/" + job_id, {
        method: "DELETE"
    }).then(() => location.reload());
}

function dismissAlert(siteName) {
  fetch(`/dismiss-alert/${siteName}`, {
    method: "POST"
  }).then(() => location.reload());
}

function toggleHistory(siteName) {
    const section = document.getElementById(`history-${siteName}`);
    if (section.style.display === "none") {
        section.style.display = "block";
    } else {
        section.style.display = "none";
    }
}
