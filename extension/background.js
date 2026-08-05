const BACKEND_URL = "http://localhost:8008/verify";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "MEDVERIFY_CHECK") return false;

  fetch(BACKEND_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: message.text,
      max_claims: 8,
      evidence_per_claim: 5,
    }),
  })
    .then((res) => {
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      return res.json();
    })
    .then((data) => {
      sendResponse({ ok: true, data });
    })
    .catch((err) => {
      sendResponse({ ok: false, error: err.message });
    });

  // Required to keep the message channel open for the async fetch above
  return true;
});
