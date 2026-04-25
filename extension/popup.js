/**
 * Supply Chain Disruption Predictor — Chrome Extension Logic
 * ==========================================================
 * Handles form submission, API communication with Flask backend,
 * rendering of multi-step reasoning chain, final output panel,
 * localStorage session persistence, and step replay.
 */

const API_BASE = "http://localhost:5001";
const STORAGE_KEY = "scdp_last_session";

// ── DOM References ──────────────────────────────────────────
const form = document.getElementById("analyzeForm");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusBadge = document.getElementById("statusBadge");

const inputSection = document.getElementById("inputSection");
const loadingSection = document.getElementById("loadingSection");
const loadingText = document.getElementById("loadingText");
const progressBar = document.getElementById("progressBar");
const resultsSection = document.getElementById("resultsSection");
const errorSection = document.getElementById("errorSection");
const errorText = document.getElementById("errorText");

const stepsContainer = document.getElementById("stepsContainer");
const stepCounter = document.getElementById("stepCounter");
const finalOutput = document.getElementById("finalOutput");
const outputContent = document.getElementById("outputContent");

const replayBtn = document.getElementById("replayBtn");
const newAnalysisBtn = document.getElementById("newAnalysisBtn");
const retryBtn = document.getElementById("retryBtn");

// ── State ───────────────────────────────────────────────────
let currentResult = null;

// ── Event Listeners ─────────────────────────────────────────
form.addEventListener("submit", handleSubmit);
replayBtn.addEventListener("click", handleReplay);
newAnalysisBtn.addEventListener("click", resetToInput);
retryBtn.addEventListener("click", resetToInput);

// ── Check for saved session on load ─────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const session = JSON.parse(saved);
      currentResult = session.result;
      // Populate form with last inputs
      if (session.inputs) {
        document.getElementById("productId").value = session.inputs.product_id || "";
        document.getElementById("regions").value = (session.inputs.regions || []).join(", ");
        document.getElementById("routes").value = (session.inputs.routes || []).join(", ");
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }
});

// ── Main Submit Handler ─────────────────────────────────────
async function handleSubmit(e) {
  e.preventDefault();

  const productId = document.getElementById("productId").value.trim();
  const regionsRaw = document.getElementById("regions").value.trim();
  const routesRaw = document.getElementById("routes").value.trim();

  if (!productId || !regionsRaw || !routesRaw) return;

  const regions = regionsRaw.split(",").map((r) => r.trim()).filter(Boolean);
  const routes = routesRaw.split(",").map((r) => r.trim()).filter(Boolean);

  const payload = { product_id: productId, regions, routes };

  showLoading();

  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.error || `Server error: ${response.status}`);
    }

    const result = await response.json();
    currentResult = result;

    // Save to localStorage
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ inputs: payload, result, savedAt: new Date().toISOString() })
    );

    showResults(result);
  } catch (err) {
    showError(err.message);
  }
}

// ── UI State Transitions ────────────────────────────────────
function showLoading() {
  inputSection.classList.add("hidden");
  loadingSection.classList.remove("hidden");
  resultsSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  setStatus("running", "Analyzing...");
  animateProgress();
}

function showResults(result) {
  loadingSection.classList.add("hidden");
  resultsSection.classList.remove("hidden");
  errorSection.classList.add("hidden");
  inputSection.classList.add("hidden");
  setStatus("ready", "Complete");
  renderSteps(result.steps);
  renderFinalOutput(result.final_answer);
}

function showError(message) {
  loadingSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
  errorSection.classList.remove("hidden");
  inputSection.classList.add("hidden");
  errorText.textContent = message;
  setStatus("error", "Error");
}

function resetToInput() {
  inputSection.classList.remove("hidden");
  loadingSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  setStatus("ready", "Ready");
}

function setStatus(state, text) {
  statusBadge.className = "status-badge " + state;
  statusBadge.querySelector(".status-text").textContent = text;
}

// ── Progress Animation ──────────────────────────────────────
function animateProgress() {
  let progress = 0;
  const messages = [
    "Initializing multi-step reasoning chain",
    "Querying supplier database...",
    "Scanning regional news feeds...",
    "Analyzing weather disruptions...",
    "Optimizing shipping routes...",
    "Synthesizing risk assessment...",
  ];
  let msgIndex = 0;

  const interval = setInterval(() => {
    if (progress >= 90 || !loadingSection.classList.contains("hidden") === false) {
      clearInterval(interval);
      return;
    }
    progress += Math.random() * 12 + 3;
    progress = Math.min(progress, 92);
    progressBar.style.width = progress + "%";

    if (progress > (msgIndex + 1) * 15 && msgIndex < messages.length - 1) {
      msgIndex++;
      loadingText.textContent = messages[msgIndex];
    }
  }, 800);

  // Store interval for cleanup
  window._progressInterval = interval;
}

// ── Render Reasoning Steps ──────────────────────────────────
function renderSteps(steps) {
  stepsContainer.innerHTML = "";
  stepCounter.textContent = `${steps.length} steps`;

  steps.forEach((step, index) => {
    const card = createStepCard(step, index);
    stepsContainer.appendChild(card);
  });
}

function createStepCard(step, index) {
  const card = document.createElement("div");
  card.className = "step-card";
  card.style.animationDelay = `${index * 0.08}s`;

  const isFinal = !!step.final_answer;
  const toolName = step.action && step.action !== "NONE" ? step.action : null;
  const timestamp = step.timestamp
    ? new Date(step.timestamp).toLocaleTimeString()
    : "";

  card.innerHTML = `
    <div class="step-header">
      <div class="step-number">${step.step || index + 1}</div>
      <div class="step-title-group">
        <span class="step-tool-badge ${isFinal ? "final" : ""}">
          ${isFinal ? "✓ Final Answer" : toolName ? `⚡ ${formatToolName(toolName)}` : "💭 Reasoning"}
        </span>
        <div class="step-thought">${escapeHtml(step.thought || "")}</div>
      </div>
      ${timestamp ? `<span class="step-timestamp">${timestamp}</span>` : ""}
      <svg class="step-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </div>
    <div class="step-details">
      ${renderThoughtBlock(step)}
      ${toolName ? renderToolInputBlock(step) : ""}
      ${step.observation ? renderObservationBlock(step) : ""}
      ${isFinal ? "" : ""}
    </div>
  `;

  // Toggle expand/collapse
  card.querySelector(".step-header").addEventListener("click", () => {
    card.classList.toggle("expanded");
  });

  return card;
}

function renderThoughtBlock(step) {
  return `
    <div class="detail-block">
      <div class="detail-label">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
        </svg>
        Thought Process
      </div>
      <div class="detail-content">${escapeHtml(step.thought || "No thought recorded")}</div>
    </div>
  `;
}

function renderToolInputBlock(step) {
  const input = step.action_input
    ? JSON.stringify(step.action_input, null, 2)
    : "null";

  return `
    <div class="detail-block">
      <div class="detail-label">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>
        </svg>
        Tool: ${formatToolName(step.action)} — Input
      </div>
      <div class="detail-content"><pre>${escapeHtml(input)}</pre></div>
    </div>
  `;
}

function renderObservationBlock(step) {
  const obs =
    typeof step.observation === "object"
      ? JSON.stringify(step.observation, null, 2)
      : String(step.observation);

  return `
    <div class="detail-block">
      <div class="detail-label">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
        Observation (Tool Result)
      </div>
      <div class="detail-content"><pre>${escapeHtml(obs)}</pre></div>
    </div>
  `;
}

// ── Render Final Output ─────────────────────────────────────
function renderFinalOutput(answer) {
  if (!answer) {
    finalOutput.classList.add("hidden");
    return;
  }

  finalOutput.classList.remove("hidden");

  const riskLevel = (answer.risk_level || "MEDIUM").toLowerCase();
  const confidence = answer.confidence_score || 0;
  const disruptions = answer.disruptions_detected || [];
  const actions = answer.recommended_actions || [];

  outputContent.innerHTML = `
    <!-- Risk Header -->
    <div class="risk-header">
      <div class="risk-header-bg" style="background: ${getRiskGradient(riskLevel)}"></div>
      <div class="risk-header-content">
        <div class="risk-level-badge ${riskLevel}">
          ${getRiskIcon(riskLevel)}
          ${riskLevel.toUpperCase()} RISK
        </div>
        <div class="confidence-meter">
          <span class="confidence-label">Confidence</span>
          <span class="confidence-value">${confidence}</span>
          <div class="confidence-bar-track">
            <div class="confidence-bar-fill" style="width: ${confidence}%"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="output-body">
      <!-- Summary -->
      <div class="output-block">
        <div class="output-block-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          Risk Summary
        </div>
        <div class="risk-summary-text">${escapeHtml(answer.risk_summary || "No summary available")}</div>
      </div>

      <!-- Disruptions -->
      ${
        disruptions.length
          ? `
        <div class="output-block">
          <div class="output-block-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-rose)" stroke-width="2">
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
            Disruptions Detected (${disruptions.length})
          </div>
          <ul class="disruption-list">
            ${disruptions.map((d) => `<li class="disruption-item">${escapeHtml(d)}</li>`).join("")}
          </ul>
        </div>
      `
          : ""
      }

      <!-- Recommendations -->
      ${
        actions.length
          ? `
        <div class="output-block">
          <div class="output-block-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--accent-emerald)" stroke-width="2">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            Recommended Actions (${actions.length})
          </div>
          <ul class="recommendation-list">
            ${actions.map((a) => `<li class="recommendation-item">${escapeHtml(a)}</li>`).join("")}
          </ul>
        </div>
      `
          : ""
      }
    </div>
  `;
}

// ── Replay Feature ──────────────────────────────────────────
async function handleReplay() {
  if (!currentResult || !currentResult.steps) return;

  const cards = stepsContainer.querySelectorAll(".step-card");
  cards.forEach((c) => {
    c.style.opacity = "0.2";
    c.classList.remove("expanded");
  });
  finalOutput.style.opacity = "0.2";

  for (let i = 0; i < cards.length; i++) {
    await delay(600);
    cards[i].style.opacity = "1";
    cards[i].classList.add("replaying", "expanded");

    // Auto-scroll into view
    cards[i].scrollIntoView({ behavior: "smooth", block: "nearest" });

    await delay(200);
    cards[i].classList.remove("replaying");
  }

  await delay(400);
  finalOutput.style.opacity = "1";
  finalOutput.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ── Helpers ─────────────────────────────────────────────────
function formatToolName(name) {
  if (!name) return "Unknown";
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function delay(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

function getRiskGradient(level) {
  const gradients = {
    critical: "linear-gradient(135deg, rgba(244,63,94,0.2), rgba(239,68,68,0.1))",
    high: "linear-gradient(135deg, rgba(245,158,11,0.2), rgba(239,68,68,0.1))",
    medium: "linear-gradient(135deg, rgba(99,102,241,0.2), rgba(6,182,212,0.1))",
    low: "linear-gradient(135deg, rgba(16,185,129,0.2), rgba(6,182,212,0.1))",
  };
  return gradients[level] || gradients.medium;
}

function getRiskIcon(level) {
  const icons = {
    critical: "🔴",
    high: "🟠",
    medium: "🟡",
    low: "🟢",
  };
  return icons[level] || "⚪";
}
