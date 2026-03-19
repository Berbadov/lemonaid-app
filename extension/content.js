function textBySelector(selector) {
  const node = document.querySelector(selector);
  return node ? node.textContent.trim() : null;
}

function numberFromText(value) {
  if (!value) {
    return null;
  }
  const normalized = value.replace(/[^\d]/g, "");
  return normalized ? Number(normalized) : null;
}

function extractSahibindenMetadata() {
  const title = textBySelector("h1");
  const priceText = textBySelector(".classified-price-wrapper, .classifiedInfo h3");
  const description = textBySelector("#classifiedDescription") || textBySelector(".classifiedDescription");

  return {
    source: "sahibinden.com",
    url: window.location.href,
    title,
    price_amount: numberFromText(priceText),
    currency: priceText && priceText.includes("TL") ? "TRY" : null,
    description
  };
}

function extractGenericMetadata() {
  const title = document.title || textBySelector("h1");
  const description =
    document.querySelector("meta[name='description']")?.getAttribute("content") || null;

  return {
    source: window.location.hostname,
    url: window.location.href,
    title,
    description
  };
}

function buildMetadata() {
  const host = window.location.hostname;
  if (host.includes("sahibinden.com")) {
    return extractSahibindenMetadata();
  }
  return extractGenericMetadata();
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type !== "GET_AD_METADATA") {
    return;
  }

  sendResponse({ ok: true, payload: buildMetadata() });
});
