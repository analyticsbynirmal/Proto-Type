const statusEl = document.getElementById("status");

fetch("http://localhost:8008/health")
  .then((res) => res.json())
  .then((data) => {
    statusEl.innerHTML = '<span class="dot" style="background:#1a7f37"></span>Backend connected';
  })
  .catch(() => {
    statusEl.innerHTML = '<span class="dot" style="background:#cf222e"></span>Backend not running (start uvicorn on port 8008)';
  });
