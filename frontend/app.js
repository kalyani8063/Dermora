const authScreen = document.getElementById("auth-screen");
const dashboardScreen = document.getElementById("dashboard-screen");

const registerForm = document.getElementById("register-form");
const loginForm = document.getElementById("login-form");
const registerStatus = document.getElementById("register-status");
const loginStatus = document.getElementById("login-status");

const userName = document.getElementById("user-name");
const userMeta = document.getElementById("user-meta");
const logoutButton = document.getElementById("logout-button");
const voiceGuideButton = document.getElementById("voice-guide-button");

const analyzeForm = document.getElementById("analyze-form");
const imageInput = document.getElementById("image-input");
const analyzeButton = document.getElementById("analyze-button");
const analyzeStatus = document.getElementById("analyze-status");
const previewWrapper = document.getElementById("preview-wrapper");
const previewImage = document.getElementById("preview-image");
const resultImage = document.getElementById("result-image");
const processedImage = document.getElementById("processed-image");

const healthLogForm = document.getElementById("health-log-form");
const healthStatus = document.getElementById("health-status");
const textLogForm = document.getElementById("text-log-form");
const textLogStatus = document.getElementById("text-log-status");
const recentLogs = document.getElementById("recent-logs");

const scoreValue = document.getElementById("score-value");
const summaryValue = document.getElementById("summary-value");
const confidenceValue = document.getElementById("confidence-value");
const acneCountValue = document.getElementById("acne-count-value");
const severityValue = document.getElementById("severity-value");
const pigmentationCoverageValue = document.getElementById("pigmentation-coverage-value");
const boxesCountValue = document.getElementById("boxes-count-value");
const previousAcneCountValue = document.getElementById("previous-acne-count-value");
const currentAcneCountValue = document.getElementById("current-acne-count-value");
const trendChangeValue = document.getElementById("trend-change-value");
const trendStatusValue = document.getElementById("trend-status-value");
const analysisDateValue = document.getElementById("analysis-date-value");
const predictionValue = document.getElementById("prediction-value");
const zonesList = document.getElementById("zones-list");
const insightsList = document.getElementById("insights-list");
const correlationsList = document.getElementById("correlations-list");
const recommendationsList = document.getElementById("recommendations-list");

const state = {
  token: localStorage.getItem("dermora_token") || "",
  user: null,
  logs: [],
};

function setMessage(target, message, isError = false) {
  target.textContent = message;
  target.style.color = isError ? "#9f2f19" : "";
}

function setAuthenticated(authenticated) {
  authScreen.classList.toggle("hidden", authenticated);
  dashboardScreen.classList.toggle("hidden", !authenticated);
}

function persistToken(token) {
  state.token = token;
  if (token) {
    localStorage.setItem("dermora_token", token);
  } else {
    localStorage.removeItem("dermora_token");
  }
}

async function apiFetch(path, options = {}, requiresAuth = true) {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (requiresAuth && state.token) {
    headers.set("Authorization", `Bearer ${state.token}`);
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = "Request failed.";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (error) {
      detail = detail;
    }
    throw new Error(detail);
  }

  return response.json();
}

function showPreview(file) {
  const reader = new FileReader();
  reader.onload = (event) => {
    previewImage.src = event.target.result;
    previewWrapper.classList.remove("hidden");
  };
  reader.readAsDataURL(file);
}

function formatZoneName(name) {
  return name.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderList(target, items, emptyMessage) {
  target.innerHTML = "";
  if (!items || items.length === 0) {
    const emptyNode = document.createElement("li");
    emptyNode.textContent = emptyMessage;
    target.appendChild(emptyNode);
    return;
  }

  items.forEach((item) => {
    const listItem = document.createElement("li");
    listItem.textContent = item;
    target.appendChild(listItem);
  });
}

function renderZones(zones = {}) {
  zonesList.innerHTML = "";
  Object.entries(zones).forEach(([zoneName, details]) => {
    const zoneItem = document.createElement("div");
    zoneItem.className = "zone-item";
    zoneItem.innerHTML = `<span>${formatZoneName(zoneName)}</span><strong>${details.count} - ${details.severity}</strong>`;
    zonesList.appendChild(zoneItem);
  });
}

function formatTrendChange(change) {
  if (change > 0) {
    return `+${change}`;
  }
  return `${change}`;
}

function renderUser() {
  if (!state.user) {
    return;
  }
  userName.textContent = state.user.name || "User";
  userMeta.textContent = `${state.user.skin_type || "Skin type not set"} | ${state.user.gender || "Gender not set"} | ${state.user.age || "Age not set"}`;
}

function renderRecentLogs() {
  recentLogs.innerHTML = "";
  if (state.logs.length === 0) {
    recentLogs.innerHTML = '<p class="muted-copy">No logs yet. Add a manual log or send a message above.</p>';
    return;
  }

  state.logs.forEach((log) => {
    const item = document.createElement("div");
    item.className = "log-chip";
    item.innerHTML = `<span>${log.date ? new Date(log.date).toLocaleString() : "New log"}</span><strong>${log.water_intake ?? "-"}L | ${log.sleep ?? "-"}h | ${log.stress || "stress n/a"}</strong>`;
    recentLogs.appendChild(item);
  });
}

function renderAnalysis(data) {
  resultImage.src = data.image_url;
  processedImage.src = data.processed_image_url;
  scoreValue.textContent = data.score;
  summaryValue.textContent = data.summary;
  confidenceValue.textContent = `${data.confidence}%`;
  acneCountValue.textContent = data.acne.count;
  severityValue.textContent = data.acne.severity;
  pigmentationCoverageValue.textContent = `${data.pigmentation.coverage}% ${data.pigmentation.intensity}`;
  boxesCountValue.textContent = data.acne.boxes.length;
  previousAcneCountValue.textContent = data.trend.previous_acne_count;
  currentAcneCountValue.textContent = data.acne.count;
  trendChangeValue.textContent = formatTrendChange(data.trend.change);
  trendStatusValue.textContent = data.trend.status;
  predictionValue.textContent = data.prediction;
  analysisDateValue.textContent = new Date(data.analysis_date).toLocaleString();

  renderZones(data.zones);
  renderList(insightsList, data.insights, "Insights will appear after analysis.");
  renderList(correlationsList, data.correlations, "Correlations will appear after more logs.");
  renderList(recommendationsList, data.recommendations, "Recommendations will appear after analysis.");
}

function speakGuide() {
  if (!("speechSynthesis" in window)) {
    setMessage(analyzeStatus, "Speech synthesis is not supported in this browser.", true);
    return;
  }

  const utterance = new SpeechSynthesisUtterance(
    "Align your face in the center of the frame. Keep your phone steady. Move closer to soft natural light if the image looks dim."
  );
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

async function completeAuth(payloadPromise, statusTarget) {
  try {
    const data = await payloadPromise;
    persistToken(data.access_token);
    state.user = data.user;
    state.logs = [];
    renderUser();
    renderRecentLogs();
    setAuthenticated(true);
    setMessage(statusTarget, "");
  } catch (error) {
    setMessage(statusTarget, error.message || "Authentication failed.", true);
  }
}

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(registerStatus, "Creating account...");

  const payload = {
    name: document.getElementById("register-name").value,
    email: document.getElementById("register-email").value,
    password: document.getElementById("register-password").value,
    age: document.getElementById("register-age").value ? Number(document.getElementById("register-age").value) : null,
    gender: document.getElementById("register-gender").value,
    skin_type: document.getElementById("register-skin-type").value,
    lifestyle: {},
    menstrual_health: {},
  };

  await completeAuth(
    apiFetch("/register", { method: "POST", body: JSON.stringify(payload) }, false),
    registerStatus,
  );
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(loginStatus, "Signing in...");

  const payload = {
    email: document.getElementById("login-email").value,
    password: document.getElementById("login-password").value,
  };

  await completeAuth(
    apiFetch("/login", { method: "POST", body: JSON.stringify(payload) }, false),
    loginStatus,
  );
});

imageInput.addEventListener("change", () => {
  const [file] = imageInput.files;
  if (!file) {
    previewWrapper.classList.add("hidden");
    return;
  }
  showPreview(file);
  setMessage(analyzeStatus, "");
});

analyzeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const [file] = imageInput.files;
  if (!file) {
    setMessage(analyzeStatus, "Please choose an image first.", true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  analyzeButton.disabled = true;
  setMessage(analyzeStatus, "Analyzing skin and generating intelligence...");

  try {
    const data = await apiFetch("/analyze", { method: "POST", body: formData });
    renderAnalysis(data);
    setMessage(analyzeStatus, "Analysis complete.");
  } catch (error) {
    setMessage(analyzeStatus, error.message || "Analysis failed.", true);
  } finally {
    analyzeButton.disabled = false;
  }
});

healthLogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(healthStatus, "Saving health log...");

  const payload = {
    water_intake: document.getElementById("water-input").value ? Number(document.getElementById("water-input").value) : null,
    activity: document.getElementById("activity-input").value,
    diet: document.getElementById("diet-input").value,
    sleep: document.getElementById("sleep-input").value ? Number(document.getElementById("sleep-input").value) : null,
    stress: document.getElementById("stress-input").value,
    menstrual_cycle: document.getElementById("menstrual-input").value,
  };

  try {
    const data = await apiFetch("/log-health", { method: "POST", body: JSON.stringify(payload) });
    state.logs.unshift(data.log);
    state.logs = state.logs.slice(0, 5);
    renderRecentLogs();
    healthLogForm.reset();
    setMessage(healthStatus, data.message);
  } catch (error) {
    setMessage(healthStatus, error.message || "Could not save health log.", true);
  }
});

textLogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setMessage(textLogStatus, "Parsing text log...");

  const payload = {
    message: document.getElementById("text-log-input").value,
  };

  try {
    const data = await apiFetch("/log-text", { method: "POST", body: JSON.stringify(payload) });
    state.logs.unshift(data.log);
    state.logs = state.logs.slice(0, 5);
    renderRecentLogs();
    textLogForm.reset();
    setMessage(textLogStatus, data.message);
  } catch (error) {
    setMessage(textLogStatus, error.message || "Could not parse text log.", true);
  }
});

logoutButton.addEventListener("click", () => {
  persistToken("");
  state.user = null;
  state.logs = [];
  setAuthenticated(false);
});

voiceGuideButton.addEventListener("click", speakGuide);

async function bootstrapSession() {
  if (!state.token) {
    setAuthenticated(false);
    return;
  }

  try {
    const data = await apiFetch("/me");
    state.user = data.user;
    renderUser();
    renderRecentLogs();
    setAuthenticated(true);
  } catch (error) {
    persistToken("");
    setAuthenticated(false);
  }
}

bootstrapSession();
