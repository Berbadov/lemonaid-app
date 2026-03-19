const DEFAULT_API_BASES = ["http://127.0.0.1:8000", "http://127.0.0.1:8765"];

function _normalizeBaseUrl(value) {
  if (!value || typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) {
    return null;
  }

  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return `http://${trimmed}`;
  }

  return trimmed;
}

async function _getApiCandidates() {
  const fromStorage = await chrome.storage.local.get(["lemonaidApiBaseUrl"]);
  const customBase = _normalizeBaseUrl(fromStorage.lemonaidApiBaseUrl);

  const candidates = [];
  if (customBase) {
    candidates.push(`${customBase}/analyze`);
  }

  for (const base of DEFAULT_API_BASES) {
    candidates.push(`${base}/analyze`);
  }

  return [...new Set(candidates)];
}

async function requestAnalysis(adMetadata) {
  const payload = {
    listing_url: adMetadata.url,
    ad_metadata: adMetadata
  };

  const endpoints = await _getApiCandidates();
  const errors = [];

  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const message = await response.text();
        errors.push(`${endpoint} -> ${message || "HTTP error"}`);
        continue;
      }

      return response.json();
    } catch (error) {
      const message = error?.message || "Network error";
      errors.push(`${endpoint} -> ${message}`);
    }
  }

  throw new Error(
    `Analyzer API request failed on all endpoints. Tried: ${errors.join(" | ")}`
  );
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type !== "ANALYZE_AD") {
    return;
  }

  requestAnalysis(request.payload)
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});
