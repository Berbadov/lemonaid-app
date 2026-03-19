const statusNode = document.getElementById("status");
const resultNode = document.getElementById("result");
const analyzeButton = document.getElementById("analyze-btn");

function setStatus(message) {
  statusNode.textContent = message;
}

function clearResults() {
  resultNode.innerHTML = "";
}

function createRiskCard(risk) {
  const wrapper = document.createElement("article");
  wrapper.className = `risk-card ${risk.severity || "medium"}`;

  const title = document.createElement("p");
  title.className = "risk-title";
  title.textContent = risk.title || "Untitled Risk";

  const meta = document.createElement("p");
  meta.className = "risk-meta";
  const confidence = typeof risk.confidence === "number" ? risk.confidence.toFixed(2) : "n/a";
  meta.textContent = `${risk.domain || "general"} | severity: ${risk.severity || "medium"} | conf: ${confidence}`;

  const rationale = document.createElement("p");
  rationale.className = "risk-rationale";
  rationale.textContent = risk.rationale || "No rationale provided.";

  wrapper.appendChild(title);
  wrapper.appendChild(meta);
  wrapper.appendChild(rationale);
  return wrapper;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function getAdMetadata(tabId) {
  const response = await chrome.tabs.sendMessage(tabId, { type: "GET_AD_METADATA" });
  if (!response || !response.ok) {
    throw new Error("Unable to read ad metadata from this page.");
  }
  return response.payload;
}

async function requestAnalysis(metadata) {
  const response = await chrome.runtime.sendMessage({
    type: "ANALYZE_AD",
    payload: metadata
  });

  if (!response || !response.ok) {
    throw new Error(response?.error || "Analyzer API request failed");
  }

  return response.result;
}

analyzeButton.addEventListener("click", async () => {
  clearResults();
  setStatus("Collecting ad metadata...");

  try {
    const tab = await getActiveTab();
    if (!tab?.id) {
      throw new Error("No active tab found.");
    }

    const metadata = await getAdMetadata(tab.id);
    setStatus("Running issue analysis...");

    const result = await requestAnalysis(metadata);
    setStatus(result.summary || "Analysis completed.");

    const risks = Array.isArray(result.risks) ? result.risks : [];
    if (!risks.length) {
      const empty = document.createElement("p");
      empty.textContent = "No risk items returned by analyzer.";
      resultNode.appendChild(empty);
      return;
    }

    for (const risk of risks) {
      resultNode.appendChild(createRiskCard(risk));
    }
  } catch (error) {
    setStatus(error.message || "Unexpected error.");
  }
});
