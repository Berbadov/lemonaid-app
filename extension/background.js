async function requestAnalysis(adMetadata) {
  const endpoint = "http://127.0.0.1:8000/analyze";
  const payload = {
    listing_url: adMetadata.url,
    ad_metadata: adMetadata
  };

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Analysis request failed");
  }

  return response.json();
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
