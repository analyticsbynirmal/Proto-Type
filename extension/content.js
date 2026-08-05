// MedVerify content script
// Injects a "Verify" button under each ChatGPT assistant message.
// ChatGPT's DOM changes over time; this targets the [data-message-author-role="assistant"]
// attribute, which has been relatively stable. If it stops matching, update SELECTOR below.

const SELECTOR = '[data-message-author-role="assistant"]';
const PROCESSED_ATTR = "data-medverify-attached";

const VERDICT_COLORS = {
  "Supported": "#1a7f37",
  "Contradicted": "#cf222e",
  "No Evidence / Insufficient": "#9a6700",
  "No Evidence Found": "#57606a",
};

function createVerifyButton(messageEl) {
  const btn = document.createElement("button");
  btn.textContent = "🩺 Verify with MedVerify";
  btn.className = "medverify-btn";
  btn.addEventListener("click", () => runVerification(messageEl, btn));
  return btn;
}

function runVerification(messageEl, btn) {
  const text = messageEl.innerText.trim();
  if (!text) return;

  btn.disabled = true;
  btn.textContent = "Checking claims…";

  chrome.runtime.sendMessage({ type: "MEDVERIFY_CHECK", text }, (response) => {
    btn.disabled = false;
    btn.textContent = "🩺 Verify with MedVerify";

    if (chrome.runtime.lastError) {
      renderError(messageEl, "Extension error: " + chrome.runtime.lastError.message);
      return;
    }
    if (!response || !response.ok) {
      renderError(messageEl, "Backend error: " + (response ? response.error : "unknown") +
        ". Is the local server running on port 8008?");
      return;
    }
    renderResults(messageEl, response.data);
  });
}

function renderError(messageEl, msg) {
  removeExistingPanel(messageEl);
  const panel = document.createElement("div");
  panel.className = "medverify-panel medverify-error";
  panel.textContent = "⚠️ " + msg;
  messageEl.appendChild(panel);
}

function removeExistingPanel(messageEl) {
  const existing = messageEl.querySelector(".medverify-panel");
  if (existing) existing.remove();
}

function renderResults(messageEl, data) {
  removeExistingPanel(messageEl);

  const panel = document.createElement("div");
  panel.className = "medverify-panel";

  const header = document.createElement("div");
  header.className = "medverify-header";
  header.textContent = `MedVerify: ${data.claims_checked} medical claim(s) checked (of ${data.total_sentences_seen} sentences)`;
  panel.appendChild(header);

  data.results.forEach((r) => {
    const card = document.createElement("div");
    card.className = "medverify-claim-card";

    const color = VERDICT_COLORS[r.verdict] || "#57606a";

    const claimRow = document.createElement("div");
    claimRow.className = "medverify-claim-text";
    claimRow.textContent = r.claim;
    card.appendChild(claimRow);

    const verdictRow = document.createElement("div");
    verdictRow.className = "medverify-verdict";
    verdictRow.style.color = color;
    verdictRow.style.borderColor = color;
    verdictRow.textContent = `${r.verdict} · trust ${(r.trust_score * 100).toFixed(0)}%`;
    card.appendChild(verdictRow);

    if (r.evidence && r.evidence.length > 0) {
      const evList = document.createElement("ul");
      evList.className = "medverify-evidence-list";
      r.evidence.forEach((ev) => {
        const li = document.createElement("li");
        const snippet = ev.text.length > 180 ? ev.text.slice(0, 180) + "…" : ev.text;
        const pmidLink = ev.pmid
          ? `<a href="https://pubmed.ncbi.nlm.nih.gov/${ev.pmid}/" target="_blank">PMID ${ev.pmid}</a>`
          : "";
        li.innerHTML = `<span class="medverify-nli-label">[${ev.nli_label}]</span> ${snippet} ${pmidLink}`;
        evList.appendChild(li);
      });
      card.appendChild(evList);
    }

    panel.appendChild(card);
  });

  messageEl.appendChild(panel);
}

function attachButtons() {
  document.querySelectorAll(SELECTOR).forEach((el) => {
    if (el.getAttribute(PROCESSED_ATTR)) return;
    el.setAttribute(PROCESSED_ATTR, "true");
    el.appendChild(createVerifyButton(el));
  });
}

// ChatGPT streams messages in dynamically; observe DOM changes.
const observer = new MutationObserver(() => attachButtons());
observer.observe(document.body, { childList: true, subtree: true });

attachButtons();
