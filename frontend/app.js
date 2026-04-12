const page = document.body?.dataset.page || "landing";
const rotatingTaglines = [
  "AI-powered skin insights",
  "Track your skin patterns",
  "Understand your skin better",
  "Personalized skin intelligence",
];

const onboardingQuestions = [
  {
    key: "acne_type",
    title: "Acne Type",
    subtitle: "Select all that apply.",
    multi: true,
    options: ["Whiteheads", "Blackheads", "Papules", "Pustules", "Nodules", "Cystic acne"],
  },
  {
    key: "stress_level",
    title: "Stress Level",
    subtitle: "How stressed have you been recently?",
    multi: false,
    options: ["Low", "Moderate", "High"],
  },
  {
    key: "hormonal_issues",
    title: "Hormonal Issues",
    subtitle: "Choose what best describes you.",
    multi: false,
    options: ["None", "PCOS/PCOD", "Irregular cycles", "Other"],
  },
  {
    key: "diet_type",
    title: "Diet Type",
    subtitle: "Pick the closest option.",
    multi: false,
    options: ["Healthy home-cooked", "Occasional junk", "High sugar/carbs", "Frequent junk food"],
  },
  {
    key: "activity_level",
    title: "Physical Activity",
    subtitle: "How active is your week?",
    multi: false,
    options: ["None", "Light", "Moderate", "Active"],
  },
];

const appState = {
  token: localStorage.getItem("dermora_token") || "",
  user: null,
  logs: [],
  voiceGuideAvailable: false,
  voiceGuideMessage: "",
  latestReport: null,
  analysisResults: [],
  activeAnalysisIndex: -1,
  analysisViewMode: "all",
  onboardingStep: 0,
  onboardingAnswers: {
    acne_type: [],
    stress_level: "",
    hormonal_issues: "",
    diet_type: "",
    activity_level: "",
  },
};

function byId(id) {
  return document.getElementById(id);
}

function setMessage(target, message, stateName = "") {
  if (!target) {
    return;
  }

  target.textContent = message;
  if (message && stateName) {
    target.dataset.state = stateName;
    return;
  }
  delete target.dataset.state;
}

function setButtonLoading(button, isLoading, loadingLabel) {
  if (!button) {
    return;
  }

  if (!button.dataset.defaultLabel) {
    button.dataset.defaultLabel = button.textContent;
  }

  button.disabled = isLoading;
  button.textContent = isLoading ? loadingLabel : button.dataset.defaultLabel;
}

function persistToken(token) {
  appState.token = token;
  if (token) {
    localStorage.setItem("dermora_token", token);
  } else {
    localStorage.removeItem("dermora_token");
  }
}

function redirectTo(path) {
  if (window.location.pathname !== path) {
    window.location.assign(path);
  }
}

function normalizeEmail(value) {
  return String(value || "").trim().toLowerCase();
}

function isValidEmail(value) {
  const email = normalizeEmail(value);
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

async function apiFetch(path, options = {}, requiresAuth = true) {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (requiresAuth && appState.token) {
    headers.set("Authorization", `Bearer ${appState.token}`);
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

async function fetchCurrentUser() {
  if (!appState.token) {
    return null;
  }

  try {
    const payload = await apiFetch("/me");
    return payload.user;
  } catch (error) {
    persistToken("");
    return null;
  }
}

async function fetchHealthLogs(limit = 12) {
  const query = new URLSearchParams({ limit: String(limit) });
  const payload = await apiFetch(`/health-logs-data?${query.toString()}`);
  return payload.logs || [];
}

function setReportButtonState(button, statusNode, report) {
  appState.latestReport = report || null;
  if (!button) {
    return;
  }

  const isReady = Boolean(report?.report_id);
  button.disabled = !isReady;
  button.setAttribute("aria-disabled", String(!isReady));
  button.title = isReady ? "Download the latest generated report." : "Run an analysis to generate a downloadable report.";
  button.dataset.reportId = isReady ? report.report_id : "";
  button.dataset.filename = isReady ? report.filename || "Dermora_Report.pdf" : "";

  if (statusNode) {
    setMessage(statusNode, isReady ? `Latest report ready: ${report.filename}` : "Run an analysis to generate a downloadable clinical-reference report.", isReady ? "success" : "");
  }
}

async function downloadReportArtifact(button, statusNode) {
  const reportId = appState.latestReport?.report_id;
  if (!reportId) {
    setMessage(statusNode, "Run an analysis before downloading a report.", "error");
    return;
  }

  setButtonLoading(button, true, "Preparing...");
  setMessage(statusNode, "Preparing your report download...", "info");

  try {
    const response = await fetch(`/reports/${encodeURIComponent(reportId)}`, {
      headers: appState.token ? { Authorization: `Bearer ${appState.token}` } : {},
    });

    if (!response.ok) {
      let detail = "Could not download the report.";
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (error) {
        detail = detail;
      }
      throw new Error(detail);
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = appState.latestReport?.filename || button.dataset.filename || "Dermora_Report.pdf";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(downloadUrl);
    setMessage(statusNode, "Report downloaded successfully.", "success");
  } catch (error) {
    setMessage(statusNode, error.message || "Could not download the report.", "error");
  } finally {
    setButtonLoading(button, false, "Preparing...");
  }
}

function startTaglineRotation() {
  const tagline = byId("tagline-text");
  if (!tagline) {
    return;
  }

  let index = 0;
  tagline.textContent = rotatingTaglines[index];

  window.setInterval(() => {
    tagline.classList.add("is-transitioning");
    window.setTimeout(() => {
      index = (index + 1) % rotatingTaglines.length;
      tagline.textContent = rotatingTaglines[index];
      tagline.classList.remove("is-transitioning");
    }, 180);
  }, 2600);
}

function formatCountdown(seconds) {
  const mins = String(Math.floor(seconds / 60)).padStart(2, "0");
  const secs = String(seconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
}

function createOtpTimer(timerNode, resendButton) {
  let countdown = 0;
  let timerId = null;

  function update() {
    if (!timerNode || !resendButton) {
      return;
    }

    if (countdown <= 0) {
      timerNode.textContent = "You can request another OTP now.";
      resendButton.disabled = false;
      return;
    }

    timerNode.textContent = `Resend available in ${formatCountdown(countdown)}`;
    resendButton.disabled = true;
  }

  function start(seconds) {
    if (timerId) {
      window.clearInterval(timerId);
    }

    countdown = seconds;
    update();

    timerId = window.setInterval(() => {
      countdown -= 1;
      update();
      if (countdown <= 0) {
        window.clearInterval(timerId);
        timerId = null;
      }
    }, 1000);
  }

  return { start };
}

function setupOtpInputs(selector, verifyButton) {
  const otpInputs = Array.from(document.querySelectorAll(selector));

  function updateVerifyState() {
    if (!verifyButton) {
      return;
    }
    verifyButton.disabled = otpInputs.some((input) => input.value.trim() === "");
  }

  otpInputs.forEach((input, index) => {
    input.addEventListener("input", () => {
      input.value = input.value.replace(/\D/g, "").slice(-1);
      if (input.value && index < otpInputs.length - 1) {
        otpInputs[index + 1].focus();
      }
      updateVerifyState();
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !input.value && index > 0) {
        otpInputs[index - 1].focus();
      }
    });

    input.addEventListener("paste", (event) => {
      event.preventDefault();
      const pastedValue = (event.clipboardData?.getData("text") || "").replace(/\D/g, "").slice(0, otpInputs.length);
      pastedValue.split("").forEach((digit, digitIndex) => {
        otpInputs[digitIndex].value = digit;
      });
      const focusIndex = Math.min(pastedValue.length, otpInputs.length - 1);
      otpInputs[focusIndex].focus();
      updateVerifyState();
    });
  });

  updateVerifyState();

  return {
    getValue() {
      return otpInputs.map((input) => input.value.trim()).join("");
    },
    reset() {
      otpInputs.forEach((input) => {
        input.value = "";
      });
      otpInputs[0]?.focus();
      updateVerifyState();
    },
    count() {
      return otpInputs.length;
    },
  };
}

async function initLoginPage() {
  const existingUser = await fetchCurrentUser();
  if (existingUser) {
    redirectTo("/dashboard");
    return;
  }

  const loginForm = byId("login-form");
  const loginEmail = byId("login-email");
  const loginPassword = byId("login-password");
  const loginSubmit = byId("login-submit");
  const loginStatus = byId("login-status");

  function clearStatus() {
    setMessage(loginStatus, "");
  }

  loginEmail?.addEventListener("input", clearStatus);
  loginPassword?.addEventListener("input", clearStatus);

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!isValidEmail(loginEmail.value)) {
      setMessage(loginStatus, "Please enter a valid email address.", "error");
      return;
    }

    setButtonLoading(loginSubmit, true, "Signing in...");
    setMessage(loginStatus, "Signing in...", "info");

    try {
      const payload = await apiFetch(
        "/login",
        {
          method: "POST",
          body: JSON.stringify({
            email: normalizeEmail(loginEmail.value),
            password: loginPassword.value,
          }),
        },
        false,
      );
      persistToken(payload.access_token);
      redirectTo("/dashboard");
    } catch (error) {
      setMessage(loginStatus, error.message || "Login failed.", "error");
    } finally {
      setButtonLoading(loginSubmit, false, "Signing in...");
    }
  });
}

async function initRegisterPage() {
  const existingUser = await fetchCurrentUser();
  if (existingUser) {
    redirectTo("/dashboard");
    return;
  }

  const registerForm = byId("register-form");
  const registerStatus = byId("register-status");
  const nameInput = byId("register-name");
  const emailInput = byId("register-email");
  const passwordInput = byId("register-password");
  const ageInput = byId("register-age");
  const genderInput = byId("register-gender");
  const birthdateInput = byId("register-birthdate");

  const sendOtpButton = byId("register-send-otp");
  const otpPanel = byId("register-otp-panel");
  const verifyOtpButton = byId("register-verify-otp");
  const resendOtpButton = byId("register-resend-otp");
  const registerSubmit = byId("register-submit");
  const devHint = byId("register-otp-dev-hint");
  const otpTimer = createOtpTimer(byId("register-otp-timer"), resendOtpButton);
  const otpController = setupOtpInputs("[data-register-otp-input]", verifyOtpButton);

  let emailVerified = false;

  function enablePostVerifyFields(enabled) {
    passwordInput.disabled = !enabled;
    ageInput.disabled = !enabled;
    genderInput.disabled = !enabled;
    birthdateInput.disabled = !enabled;
    registerSubmit.disabled = !enabled;
  }

  function clearStatus() {
    setMessage(registerStatus, "");
  }

  function invalidateVerificationState() {
    emailVerified = false;
    enablePostVerifyFields(false);
  }

  nameInput?.addEventListener("input", () => {
    clearStatus();
    invalidateVerificationState();
  });
  emailInput?.addEventListener("input", () => {
    clearStatus();
    invalidateVerificationState();
  });

  async function sendRegisterOtp(isResend = false) {
    const name = nameInput.value.trim();
    const email = normalizeEmail(emailInput.value);

    if (!name || !email) {
      setMessage(registerStatus, "Enter full name and email before requesting OTP.", "error");
      return;
    }
    if (!isValidEmail(email)) {
      setMessage(registerStatus, "Please enter a valid email address.", "error");
      return;
    }

    const activeButton = isResend ? resendOtpButton : sendOtpButton;
    setButtonLoading(activeButton, true, "Sending...");
    setMessage(registerStatus, "Sending OTP...", "info");

    try {
      const payload = await apiFetch(
        "/auth/register/send-otp",
        {
          method: "POST",
          body: JSON.stringify({ name, email }),
        },
        false,
      );

      otpPanel.classList.remove("hidden");
      otpController.reset();
      otpTimer.start(payload.resend_in_seconds || 30);
      setMessage(registerStatus, payload.message || "OTP sent.", "success");

      if (payload.development_code) {
        devHint.textContent = `Development OTP: ${payload.development_code}`;
        devHint.classList.remove("hidden");
      } else {
        devHint.classList.add("hidden");
      }
    } catch (error) {
      setMessage(registerStatus, error.message || "Could not send OTP.", "error");
    } finally {
      setButtonLoading(activeButton, false, "Sending...");
    }
  }

  sendOtpButton?.addEventListener("click", async () => {
    await sendRegisterOtp(false);
  });

  resendOtpButton?.addEventListener("click", async () => {
    await sendRegisterOtp(true);
  });

  verifyOtpButton?.addEventListener("click", async () => {
    const email = normalizeEmail(emailInput.value);
    if (!isValidEmail(email)) {
      setMessage(registerStatus, "Please enter a valid email address.", "error");
      return;
    }

    const otp = otpController.getValue();
    if (otp.length !== otpController.count()) {
      setMessage(registerStatus, "Enter the full 6-digit OTP.", "error");
      return;
    }

    setButtonLoading(verifyOtpButton, true, "Verifying...");
    setMessage(registerStatus, "Verifying OTP...", "info");

    try {
      await apiFetch(
        "/auth/register/verify-otp",
        {
          method: "POST",
          body: JSON.stringify({ email, otp }),
        },
        false,
      );
      emailVerified = true;
      enablePostVerifyFields(true);
      setMessage(registerStatus, "Email verified. Complete remaining fields.", "success");
    } catch (error) {
      setMessage(registerStatus, error.message || "OTP verification failed.", "error");
    } finally {
      setButtonLoading(verifyOtpButton, false, "Verifying...");
    }
  });

  registerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!emailVerified) {
      setMessage(registerStatus, "Please verify OTP before creating your account.", "error");
      return;
    }

    if (!isValidEmail(emailInput.value)) {
      setMessage(registerStatus, "Please enter a valid email address.", "error");
      return;
    }

    if (passwordInput.value.trim().length < 8) {
      setMessage(registerStatus, "Password must be at least 8 characters.", "error");
      return;
    }

    setButtonLoading(registerSubmit, true, "Creating...");
    setMessage(registerStatus, "Creating your account...", "info");

    const payload = {
      name: nameInput.value.trim(),
      email: normalizeEmail(emailInput.value),
      password: passwordInput.value,
      age: ageInput.value ? Number(ageInput.value) : null,
      gender: genderInput.value,
      birthdate: birthdateInput.value || null,
      skin_type: "",
      lifestyle: {},
      menstrual_health: {},
    };

    try {
      const data = await apiFetch("/register", { method: "POST", body: JSON.stringify(payload) }, false);
      persistToken(data.access_token);
      redirectTo("/dashboard");
    } catch (error) {
      setMessage(registerStatus, error.message || "Could not create account.", "error");
    } finally {
      setButtonLoading(registerSubmit, false, "Creating...");
    }
  });
}

async function initResetPasswordPage() {
  const existingUser = await fetchCurrentUser();
  if (existingUser) {
    redirectTo("/dashboard");
    return;
  }

  const form = byId("reset-password-form");
  const statusNode = byId("reset-status");
  const emailInput = byId("reset-email");
  const sendOtpButton = byId("reset-send-otp");
  const otpPanel = byId("reset-otp-panel");
  const verifyButton = byId("reset-verify-otp");
  const resendButton = byId("reset-resend-otp");
  const confirmButton = byId("reset-confirm");
  const newPasswordInput = byId("reset-new-password");
  const devHint = byId("reset-otp-dev-hint");
  const otpTimer = createOtpTimer(byId("reset-otp-timer"), resendButton);
  const otpController = setupOtpInputs("[data-reset-otp-input]", verifyButton);

  let otpVerified = false;

  function clearStatus() {
    setMessage(statusNode, "");
  }

  function invalidateResetVerification() {
    otpVerified = false;
    newPasswordInput.disabled = true;
    confirmButton.disabled = true;
  }

  emailInput?.addEventListener("input", () => {
    clearStatus();
    invalidateResetVerification();
  });

  async function sendResetOtp(isResend = false) {
    const email = normalizeEmail(emailInput.value);
    if (!email) {
      setMessage(statusNode, "Enter your email first.", "error");
      return;
    }
    if (!isValidEmail(email)) {
      setMessage(statusNode, "Please enter a valid email address.", "error");
      return;
    }

    const activeButton = isResend ? resendButton : sendOtpButton;
    setButtonLoading(activeButton, true, "Sending...");
    setMessage(statusNode, "Sending OTP...", "info");

    try {
      const payload = await apiFetch(
        "/auth/password-reset/send-otp",
        {
          method: "POST",
          body: JSON.stringify({ email }),
        },
        false,
      );

      otpPanel.classList.remove("hidden");
      otpController.reset();
      otpTimer.start(payload.resend_in_seconds || 30);
      setMessage(statusNode, payload.message || "OTP sent.", "success");

      if (payload.development_code) {
        devHint.textContent = `Development OTP: ${payload.development_code}`;
        devHint.classList.remove("hidden");
      } else {
        devHint.classList.add("hidden");
      }
    } catch (error) {
      setMessage(statusNode, error.message || "Could not send OTP.", "error");
    } finally {
      setButtonLoading(activeButton, false, "Sending...");
    }
  }

  sendOtpButton?.addEventListener("click", async () => {
    await sendResetOtp(false);
  });

  resendButton?.addEventListener("click", async () => {
    await sendResetOtp(true);
  });

  verifyButton?.addEventListener("click", async () => {
    const email = normalizeEmail(emailInput.value);
    if (!isValidEmail(email)) {
      setMessage(statusNode, "Please enter a valid email address.", "error");
      return;
    }

    const otp = otpController.getValue();
    if (otp.length !== otpController.count()) {
      setMessage(statusNode, "Enter the full 6-digit OTP.", "error");
      return;
    }

    setButtonLoading(verifyButton, true, "Verifying...");
    setMessage(statusNode, "Verifying OTP...", "info");

    try {
      await apiFetch(
        "/auth/password-reset/verify-otp",
        {
          method: "POST",
          body: JSON.stringify({ email, otp }),
        },
        false,
      );
      otpVerified = true;
      newPasswordInput.disabled = false;
      confirmButton.disabled = false;
      setMessage(statusNode, "OTP verified. Set a new password.", "success");
    } catch (error) {
      setMessage(statusNode, error.message || "OTP verification failed.", "error");
    } finally {
      setButtonLoading(verifyButton, false, "Verifying...");
    }
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!isValidEmail(emailInput.value)) {
      setMessage(statusNode, "Please enter a valid email address.", "error");
      return;
    }

    if (!otpVerified) {
      setMessage(statusNode, "Verify OTP before updating password.", "error");
      return;
    }

    if (newPasswordInput.value.trim().length < 8) {
      setMessage(statusNode, "Password must be at least 8 characters.", "error");
      return;
    }

    setButtonLoading(confirmButton, true, "Updating...");
    setMessage(statusNode, "Updating password...", "info");

    try {
      const payload = await apiFetch(
        "/auth/password-reset/confirm",
        {
          method: "POST",
          body: JSON.stringify({
            email: normalizeEmail(emailInput.value),
            new_password: newPasswordInput.value,
          }),
        },
        false,
      );
      setMessage(statusNode, payload.message || "Password updated. Redirecting to login...", "success");
      window.setTimeout(() => redirectTo("/login"), 1000);
    } catch (error) {
      setMessage(statusNode, error.message || "Could not update password.", "error");
    } finally {
      setButtonLoading(confirmButton, false, "Updating...");
    }
  });
}
function formatZoneName(name) {
  return name.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatTrendChange(change) {
  if (change > 0) {
    return `+${change}`;
  }
  return `${change}`;
}

function renderList(target, items, emptyMessage) {
  if (!target) {
    return;
  }

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

function renderZones(target, zones = {}) {
  if (!target) {
    return;
  }

  target.innerHTML = "";
  const entries = Object.entries(zones);
  if (entries.length === 0) {
    const emptyState = document.createElement("div");
    emptyState.className = "zone-item";
    emptyState.textContent = "Zone details will appear after analysis.";
    target.appendChild(emptyState);
    return;
  }

  entries.forEach(([zoneName, details]) => {
    const zoneItem = document.createElement("div");
    zoneItem.className = "zone-item";

    const label = document.createElement("span");
    label.textContent = formatZoneName(zoneName);

    const value = document.createElement("strong");
    value.textContent = `${details.count} - ${details.severity}`;

    zoneItem.appendChild(label);
    zoneItem.appendChild(value);
    target.appendChild(zoneItem);
  });
}

function isFemaleUser() {
  const gender = String(appState.user?.gender || "").trim().toLowerCase();
  return gender === "female" || gender === "woman";
}

function getTodayInputValue() {
  const now = new Date();
  const offsetMs = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offsetMs).toISOString().slice(0, 10);
}

function formatEntryDate(value) {
  if (!value) {
    return "Today";
  }

  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const sugarFreePositivePatterns = [
  /sugar[ -]?free/i,
  /no added sugar/i,
  /no sugar/i,
  /without sugar/i,
  /zero sugar/i,
  /cut out sugar/i,
  /skipped (?:dessert|sweets)/i,
];

const sugarFreeNegativePatterns = [
  /high sugar/i,
  /had sugar/i,
  /sugary/i,
  /\bdessert\b/i,
  /\bsweets?\b/i,
  /\bcandy\b/i,
  /\bcake\b/i,
  /\bice cream\b/i,
  /\bsoda\b/i,
  /\bchocolate\b/i,
];

function getLogEntryDate(log) {
  return log?.entry_date || (log?.date ? String(log.date).slice(0, 10) : "");
}

function parseDateKey(value) {
  if (!value) {
    return null;
  }

  const [year, month, day] = String(value).split("-").map(Number);
  if (!year || !month || !day) {
    return null;
  }

  return new Date(year, month - 1, day);
}

function getDayDifference(later, earlier) {
  if (!later || !earlier) {
    return null;
  }

  const laterUtc = Date.UTC(later.getFullYear(), later.getMonth(), later.getDate());
  const earlierUtc = Date.UTC(earlier.getFullYear(), earlier.getMonth(), earlier.getDate());
  return Math.round((laterUtc - earlierUtc) / 86400000);
}

function formatDayBadge(value) {
  const parsed = parseDateKey(value);
  const todayValue = getTodayInputValue();
  if (!parsed) {
    return value;
  }
  if (value === todayValue) {
    return "Today";
  }

  const today = parseDateKey(todayValue);
  if (today && getDayDifference(today, parsed) === 1) {
    return "Yesterday";
  }

  return parsed.toLocaleDateString(undefined, { weekday: "short" });
}

function getSugarFreeState(log) {
  if (typeof log?.sugar_free === "boolean") {
    return log.sugar_free;
  }

  const sourceBits = [
    log?.diet,
    log?.notes,
    log?.source_text,
    log?.additional_context?.source_text,
    Array.isArray(log?.tags) ? log.tags.join(" ") : "",
  ].filter(Boolean);
  const combinedText = sourceBits.join(" | ");

  if (!combinedText) {
    return null;
  }

  if (sugarFreeNegativePatterns.some((pattern) => pattern.test(combinedText))) {
    return false;
  }
  if (sugarFreePositivePatterns.some((pattern) => pattern.test(combinedText))) {
    return true;
  }
  return null;
}

function buildSugarFreeStreak(logs = []) {
  const statesByDate = new Map();
  const logsByRecency = [...logs].sort((left, right) => {
    const leftTime = left?.date ? new Date(left.date).getTime() : 0;
    const rightTime = right?.date ? new Date(right.date).getTime() : 0;
    return rightTime - leftTime;
  });

  logsByRecency.forEach((log) => {
    const dateKey = getLogEntryDate(log);
    if (!dateKey) {
      return;
    }

    const nextState = getSugarFreeState(log);
    const hasDate = statesByDate.has(dateKey);
    const currentState = statesByDate.get(dateKey);

    if (!hasDate) {
      statesByDate.set(dateKey, nextState);
      return;
    }

    if (currentState == null && typeof nextState === "boolean") {
      statesByDate.set(dateKey, nextState);
    }
  });

  const orderedDays = Array.from(statesByDate.entries()).sort((left, right) => left[0].localeCompare(right[0]));
  const latestDay = orderedDays[orderedDays.length - 1] || ["", null];
  const latestDate = latestDay[0] || "";
  const latestState = latestDay[1] ?? null;

  let bestStreak = 0;
  let runningStreak = 0;
  let previousDate = null;

  orderedDays.forEach(([dateKey, state]) => {
    const currentDate = parseDateKey(dateKey);
    const isConsecutive = previousDate && currentDate && getDayDifference(currentDate, previousDate) === 1;

    if (state === true) {
      runningStreak = isConsecutive && runningStreak > 0 ? runningStreak + 1 : 1;
      bestStreak = Math.max(bestStreak, runningStreak);
    } else {
      runningStreak = 0;
    }

    previousDate = currentDate;
  });

  let currentStreak = 0;
  if (latestState === true) {
    currentStreak = 1;
    let cursorDate = parseDateKey(latestDate);

    for (let index = orderedDays.length - 2; index >= 0; index -= 1) {
      const [dateKey, state] = orderedDays[index];
      const candidateDate = parseDateKey(dateKey);
      if (state !== true || !candidateDate || !cursorDate || getDayDifference(cursorDate, candidateDate) !== 1) {
        break;
      }
      currentStreak += 1;
      cursorDate = candidateDate;
    }
  }

  const totalSugarFreeDays = orderedDays.filter(([, state]) => state === true).length;
  const todayValue = getTodayInputValue();
  const today = parseDateKey(todayValue);
  const latestParsed = parseDateKey(latestDate);
  const latestGap = today && latestParsed ? getDayDifference(today, latestParsed) : null;
  const isFresh = latestState === true && latestDate === todayValue;
  const needsTodayCheckIn = latestState === true && latestGap === 1;
  const isStale = latestState === true && latestGap != null && latestGap > 1;

  const recentWeek = Array.from({ length: 7 }, (_, index) => {
    const day = new Date();
    day.setHours(0, 0, 0, 0);
    day.setDate(day.getDate() - (6 - index));
    const dateKey = [
      day.getFullYear(),
      String(day.getMonth() + 1).padStart(2, "0"),
      String(day.getDate()).padStart(2, "0"),
    ].join("-");
    return {
      dateKey,
      label: formatDayBadge(dateKey),
      dayNumber: String(day.getDate()).padStart(2, "0"),
      state: statesByDate.has(dateKey) ? statesByDate.get(dateKey) : null,
      isToday: dateKey === todayValue,
    };
  });

  return {
    currentStreak,
    bestStreak,
    totalSugarFreeDays,
    latestDate,
    latestState,
    needsTodayCheckIn,
    isFresh,
    isStale,
    recentWeek,
    loggedDays: orderedDays.length,
  };
}

function buildSugarFreeNarrative(summary) {
  if (!summary.loggedDays) {
    return {
      kicker: "Glow chain waiting",
      story: "Log a sugar-free day to start a fresh streak on your dashboard.",
    };
  }

  if (summary.currentStreak === 0) {
    if (summary.latestState === false) {
      return {
        kicker: "Fresh reset available",
        story: "Your latest log included sugar. The next sugar-free day starts a brand-new streak.",
      };
    }

    return {
      kicker: "No active run yet",
      story: "You have check-ins, but no current sugar-free chain. One intentional day lights it up.",
    };
  }

  if (summary.isFresh) {
    return {
      kicker: summary.currentStreak >= 7 ? "Glow chain strong" : "Streak is glowing",
      story: `You locked in ${summary.currentStreak} ${summary.currentStreak === 1 ? "day" : "days"} in a row with today's check-in.`,
    };
  }

  if (summary.needsTodayCheckIn) {
    return {
      kicker: "Carry it forward",
      story: `${summary.currentStreak} ${summary.currentStreak === 1 ? "day" : "days"} are confirmed through ${formatEntryDate(summary.latestDate)}. Log today to keep the lights on.`,
    };
  }

  if (summary.isStale) {
    return {
      kicker: "Recent streak on pause",
      story: `Your last sugar-free run reached ${summary.currentStreak} ${summary.currentStreak === 1 ? "day" : "days"}. Another check-in restarts the glow.`,
    };
  }

  return {
    kicker: "Rhythm in progress",
    story: `${summary.currentStreak} ${summary.currentStreak === 1 ? "day" : "days"} are currently recorded in a row.`,
  };
}

function renderSugarFreeStreak() {
  const streakValue = byId("sugar-streak-value");
  const streakStory = byId("sugar-streak-story");
  const streakWidget = byId("sugar-streak-widget");
  const keepButton = byId("sugar-streak-keep");
  const breakButton = byId("sugar-streak-break");

  if (!streakValue || !streakStory || !streakWidget || !keepButton || !breakButton) {
    return null;
  }

  const summary = buildSugarFreeStreak(appState.logs);
  const displayStreak = summary.isStale ? 0 : summary.currentStreak;
  const todayState = summary.recentWeek.find((day) => day.isToday)?.state ?? null;

  streakValue.textContent = `${displayStreak} ${displayStreak === 1 ? "day" : "days"}`;

  if (!summary.loggedDays) {
    streakStory.textContent = "Tap the streak to log today as sugar-free.";
  } else if (todayState === true) {
    streakStory.textContent = "Logged sugar-free today. Your streak is alive.";
  } else if (todayState === false) {
    streakStory.textContent = "Sugar logged today. The streak is broken for now.";
  } else if (displayStreak > 0) {
    streakStory.textContent = `Tap the streak to continue your ${displayStreak}-day run today.`;
  } else {
    streakStory.textContent = "Tap the streak to start a new sugar-free run.";
  }

  streakWidget.dataset.streakState = todayState === false ? "broken" : displayStreak > 0 ? "active" : "idle";
  keepButton.classList.toggle("is-active", todayState === true);
  keepButton.setAttribute("aria-pressed", String(todayState === true));
  breakButton.classList.toggle("is-active", todayState === false);
  breakButton.setAttribute("aria-pressed", String(todayState === false));

  return summary;
}

function renderRecentLogs(target) {
  if (!target) {
    return;
  }

  target.innerHTML = "";
  if (appState.logs.length === 0) {
    const emptyNode = document.createElement("p");
    emptyNode.className = "body-copy compact-copy";
    emptyNode.textContent = "No logs yet. Add a manual log or send a message above.";
    target.appendChild(emptyNode);
    return;
  }

  appState.logs.forEach((log) => {
    const item = document.createElement("div");
    item.className = "log-chip";

    const head = document.createElement("div");
    head.className = "log-head";

    const time = document.createElement("span");
    time.className = "log-time";
    time.textContent = formatEntryDate(getLogEntryDate(log));

    const savedAt = document.createElement("span");
    savedAt.className = "log-date-pill";
    savedAt.textContent = log.date ? new Date(log.date).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "Saved now";

    head.appendChild(time);
    head.appendChild(savedAt);

    const details = document.createElement("span");
    details.className = "log-supporting";
    const supportingBits = [log.activity, log.diet, log.stress && `Stress: ${log.stress}`].filter(Boolean);
    details.textContent = supportingBits.length ? supportingBits.join(" | ") : "Lifestyle note saved.";

    const metrics = document.createElement("div");
    metrics.className = "log-metrics";

    const metricLabels = [];
    const sugarFreeState = getSugarFreeState(log);

    if (sugarFreeState === true) {
      metricLabels.push({ text: "Sugar-free", tone: "success" });
    } else if (sugarFreeState === false) {
      metricLabels.push({ text: "Sugar logged", tone: "warning" });
    }
    if (log.water_intake != null) {
      metricLabels.push({ text: `${log.water_intake}L water` });
    }
    if (log.sleep != null) {
      metricLabels.push({ text: `${log.sleep}h sleep` });
    }
    if (log.stool_passages != null) {
      metricLabels.push({ text: `${log.stool_passages} stool ${log.stool_passages === 1 ? "pass" : "passes"}` });
    }
    if (log.stool_feel) {
      metricLabels.push({ text: log.stool_feel });
    }
    if (log.menstrual_cycle) {
      metricLabels.push({ text: log.menstrual_cycle, accent: true });
    }
    if (log.cycle_day != null) {
      metricLabels.push({ text: `Cycle day ${log.cycle_day}`, accent: true });
    }
    if (log.period_phase) {
      metricLabels.push({ text: log.period_phase, accent: true });
    }

    metricLabels.forEach((metric) => {
      const chip = document.createElement("span");
      chip.className = [
        "log-metric",
        metric.accent ? "log-metric-accent" : "",
        metric.tone ? `log-metric-${metric.tone}` : "",
      ].filter(Boolean).join(" ");
      chip.textContent = metric.text;
      metrics.appendChild(chip);
    });

    item.appendChild(head);
    item.appendChild(details);
    if (metricLabels.length) {
      item.appendChild(metrics);
    }
    target.appendChild(item);
  });
}

function bindLogout(button) {
  button?.addEventListener("click", () => {
    persistToken("");
    appState.user = null;
    appState.logs = [];
    redirectTo("/");
  });
}

function renderUserProfile() {
  if (!appState.user) {
    return;
  }

  const userName = byId("user-name");
  const userMeta = byId("user-meta");

  if (userName) {
    userName.textContent = appState.user.name || "User";
  }

  if (userMeta) {
    const parts = [];
    if (appState.user.gender) {
      parts.push(appState.user.gender);
    }
    if (appState.user.age) {
      parts.push(`${appState.user.age} years`);
    }
    if (appState.user.birthdate) {
      parts.push(`Born: ${appState.user.birthdate}`);
    }
    if (appState.user.stress_level) {
      parts.push(`Stress: ${appState.user.stress_level}`);
    }
    userMeta.textContent = parts.length ? parts.join(" | ") : "Complete onboarding for personalized insights.";
  }
}
function bindHealthLogForms() {
  const healthLogForm = byId("health-log-form");
  const healthStatus = byId("health-status");
  const healthSubmit = byId("health-submit");
  const textLogForm = byId("text-log-form");
  const textLogStatus = byId("text-log-status");
  const textLogSubmit = byId("text-log-submit");
  const recentLogs = byId("recent-logs");

  const entryDateInput = byId("entry-date-input");
  const waterInput = byId("water-input");
  const waterTotal = byId("water-total");
  const waterCaption = byId("water-caption");
  const hydrationFill = byId("hydration-fill");
  const hydrationButtons = Array.from(document.querySelectorAll("[data-water-glass]"));
  const stoolFeelInput = byId("stool-feel-input");
  const stoolSummary = byId("stool-summary");
  const stoolButtons = Array.from(document.querySelectorAll("[data-stool-count]"));
  const menstrualPanel = byId("menstrual-panel");
  const menstrualSummary = byId("menstrual-summary");
  const cycleDayInput = byId("cycle-day-input");
  const periodPhaseInput = byId("period-phase-input");
  const cycleButtons = Array.from(document.querySelectorAll("[data-cycle-value]"));
  const sugarSummary = byId("sugar-free-summary");
  const sugarButtons = Array.from(document.querySelectorAll("[data-sugar-choice]"));

  const litersPerGlass = 0.25;
  const hydrationMessages = [
    "Start the day with your first glass.",
    "Nice start. Keep the pace gentle.",
    "Hydration is building steadily.",
    "Halfway there. Your skin will thank you.",
    "Strong hydration day in progress.",
  ];

  let stoolCount = 0;
  let cycleValue = "";
  let sugarFreeState = null;

  function ensureEntryDate() {
    if (entryDateInput && !entryDateInput.value) {
      entryDateInput.value = getTodayInputValue();
    }
  }

  function setWaterCount(nextCount) {
    const count = Math.max(0, Math.min(hydrationButtons.length, Number(nextCount) || 0));
    const liters = count * litersPerGlass;
    if (waterInput) {
      waterInput.value = liters.toFixed(2);
    }
    hydrationButtons.forEach((button, index) => {
      button.classList.toggle("is-active", index < count);
    });
    if (hydrationFill) {
      hydrationFill.style.height = `${(count / Math.max(hydrationButtons.length, 1)) * 100}%`;
    }
    if (waterTotal) {
      waterTotal.textContent = `${liters.toFixed(2)} L`;
    }
    if (waterCaption) {
      const ratio = hydrationButtons.length ? count / hydrationButtons.length : 0;
      if (count === 0) {
        waterCaption.textContent = hydrationMessages[0];
      } else if (ratio < 0.35) {
        waterCaption.textContent = hydrationMessages[1];
      } else if (ratio < 0.6) {
        waterCaption.textContent = hydrationMessages[2];
      } else if (ratio < 0.85) {
        waterCaption.textContent = hydrationMessages[3];
      } else {
        waterCaption.textContent = hydrationMessages[4];
      }
    }
  }

  function updateSugarFreeSummary() {
    if (!sugarSummary) {
      return;
    }

    const selectedDate = formatEntryDate(entryDateInput?.value || getTodayInputValue());
    if (sugarFreeState === true) {
      sugarSummary.textContent = `${selectedDate} is marked sugar-free. This will extend your homepage streak.`;
      return;
    }
    if (sugarFreeState === false) {
      sugarSummary.textContent = `${selectedDate} is marked as a sugar day. Your streak will reset for that date.`;
      return;
    }

    sugarSummary.textContent = "Leave it blank if you are unsure. Mark it when you want the streak to update.";
  }

  function setSugarFreeState(nextState) {
    sugarFreeState = nextState;
    sugarButtons.forEach((button) => {
      const isMatch = (button.dataset.sugarChoice === "yes" && sugarFreeState === true)
        || (button.dataset.sugarChoice === "no" && sugarFreeState === false);
      button.classList.toggle("is-active", isMatch);
    });
    updateSugarFreeSummary();
  }

  function updateStoolSummary() {
    if (!stoolSummary) {
      return;
    }

    if (stoolCount === 0) {
      stoolSummary.textContent = "No stool passage logged yet.";
      return;
    }

    const feel = stoolFeelInput?.value ? ` Feeling: ${stoolFeelInput.value}.` : "";
    stoolSummary.textContent = `${stoolCount} ${stoolCount === 1 ? "pass" : "passes"} logged today.${feel}`;
  }

  function setStoolCount(nextCount) {
    stoolCount = Math.max(0, Number(nextCount) || 0);
    stoolButtons.forEach((button) => {
      button.classList.toggle("is-active", Number(button.dataset.stoolCount) === stoolCount);
    });
    updateStoolSummary();
  }

  function updateMenstrualSummary() {
    if (!menstrualSummary) {
      return;
    }

    const selectedDate = formatEntryDate(entryDateInput?.value || getTodayInputValue());
    if (!cycleValue) {
      menstrualSummary.textContent = `Pick a cycle marker for ${selectedDate} if you want to track it.`;
      return;
    }

    const phase = periodPhaseInput?.value ? ` Phase: ${periodPhaseInput.value}.` : "";
    const cycleDay = cycleDayInput?.value ? ` Cycle day ${cycleDayInput.value}.` : "";
    menstrualSummary.textContent = `${selectedDate} marked as ${cycleValue}.${cycleDay}${phase}`;
  }

  function setCycleValue(nextValue) {
    cycleValue = nextValue || "";
    cycleButtons.forEach((button) => {
      button.classList.toggle("is-active", (button.dataset.cycleValue || "") === cycleValue);
    });
    updateMenstrualSummary();
  }

  function syncMenstrualVisibility() {
    const shouldShow = isFemaleUser();
    menstrualPanel?.classList.toggle("hidden", !shouldShow);
    if (!shouldShow) {
      cycleValue = "";
      cycleDayInput.value = "";
      periodPhaseInput.value = "";
    }
    updateMenstrualSummary();
  }

  function resetHealthLogForm() {
    healthLogForm?.reset();
    ensureEntryDate();
    setWaterCount(0);
    setSugarFreeState(null);
    setStoolCount(0);
    setCycleValue("");
    updateMenstrualSummary();
  }

  hydrationButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextCount = Number(button.dataset.waterGlass);
      const currentCount = Math.round((Number(waterInput?.value || 0) / litersPerGlass));
      setWaterCount(currentCount === nextCount ? nextCount - 1 : nextCount);
    });
  });

  sugarButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextState = button.dataset.sugarChoice === "yes" ? true : false;
      setSugarFreeState(sugarFreeState === nextState ? null : nextState);
    });
  });

  stoolButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextCount = Number(button.dataset.stoolCount);
      setStoolCount(stoolCount === nextCount ? 0 : nextCount);
    });
  });

  cycleButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextValue = button.dataset.cycleValue || "";
      setCycleValue(cycleValue === nextValue ? "" : nextValue);
    });
  });

  stoolFeelInput?.addEventListener("change", updateStoolSummary);
  entryDateInput?.addEventListener("change", () => {
    updateMenstrualSummary();
    updateSugarFreeSummary();
  });
  cycleDayInput?.addEventListener("input", updateMenstrualSummary);
  periodPhaseInput?.addEventListener("change", updateMenstrualSummary);

  ensureEntryDate();
  setWaterCount(0);
  setSugarFreeState(null);
  setStoolCount(0);
  syncMenstrualVisibility();
  renderRecentLogs(recentLogs);

  healthLogForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setButtonLoading(healthSubmit, true, "Saving...");
    setMessage(healthStatus, "Saving health log...", "info");

    const payload = {
      entry_date: entryDateInput?.value || getTodayInputValue(),
      sugar_free: sugarFreeState,
      water_intake: Number(waterInput?.value || 0) > 0 ? Number(waterInput.value) : null,
      activity: byId("activity-input").value,
      diet: byId("diet-input").value,
      sleep: byId("sleep-input").value ? Number(byId("sleep-input").value) : null,
      stress: byId("stress-input").value,
      stool_passages: stoolCount,
      stool_feel: stoolFeelInput?.value || "",
      menstrual_cycle: isFemaleUser() ? cycleValue : "",
      menstrual_logged: isFemaleUser() && Boolean(cycleValue),
      period_phase: isFemaleUser() ? periodPhaseInput?.value || "" : "",
      cycle_day: isFemaleUser() && cycleDayInput?.value ? Number(cycleDayInput.value) : null,
    };

    try {
      const data = await apiFetch("/log-health", { method: "POST", body: JSON.stringify(payload) });
      appState.logs.unshift(data.log);
      appState.logs = appState.logs.slice(0, 12);
      renderRecentLogs(recentLogs);
      resetHealthLogForm();
      setMessage(healthStatus, data.message || "Health log saved.", "success");
    } catch (error) {
      setMessage(healthStatus, error.message || "Could not save health log.", "error");
    } finally {
      setButtonLoading(healthSubmit, false, "Saving...");
    }
  });

  textLogForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setButtonLoading(textLogSubmit, true, "Parsing...");
    setMessage(textLogStatus, "Parsing text log...", "info");

    const payload = {
      message: byId("text-log-input").value,
    };

    try {
      const data = await apiFetch("/log-text", { method: "POST", body: JSON.stringify(payload) });
      appState.logs.unshift(data.log);
      appState.logs = appState.logs.slice(0, 12);
      renderRecentLogs(recentLogs);
      textLogForm.reset();
      setMessage(textLogStatus, data.message || "Text log saved.", "success");
    } catch (error) {
      setMessage(textLogStatus, error.message || "Could not parse text log.", "error");
    } finally {
      setButtonLoading(textLogSubmit, false, "Parsing...");
    }
  });
}

function createBatchItemId(prefix = "item") {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function isAcceptedImageFile(file) {
  if (!file) {
    return false;
  }

  if (typeof file.type === "string" && file.type.startsWith("image/")) {
    return true;
  }

  const lowerName = String(file.name || "").toLowerCase();
  return [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic", ".heif"].some((extension) => lowerName.endsWith(extension));
}

function getMostAffectedZone(zones = {}) {
  const entries = Object.entries(zones);
  if (entries.length === 0) {
    return "your skin";
  }

  const [zoneName] = entries.reduce((highest, current) => {
    const currentCount = current[1]?.count || 0;
    const highestCount = highest[1]?.count || 0;
    return currentCount > highestCount ? current : highest;
  });

  return formatZoneName(zoneName).toLowerCase();
}

function hasDetectedInconvenience(data) {
  return false;
}

function buildVoiceGuideMessage(data) {
  return "";
}

function updateVoiceGuideState(button, enabled, message = "") {
  appState.voiceGuideAvailable = enabled;
  appState.voiceGuideMessage = enabled ? message : "";

  if (!button) {
    return;
  }

  button.disabled = !enabled;
  button.setAttribute("aria-disabled", String(!enabled));
  button.title = enabled
    ? "Replay voice guidance for the detected concern."
    : "Voice guide activates after a scan when a concern is detected.";
}

function speakGuide(customMessage = appState.voiceGuideMessage) {
  const analyzeStatus = byId("analyze-status");
  if (!customMessage) {
    setMessage(analyzeStatus, "Voice guide will activate after a scan when Dermora detects a concern.", "info");
    return;
  }

  if (!("speechSynthesis" in window)) {
    setMessage(analyzeStatus, "Speech synthesis is not supported in this browser.", "error");
    return;
  }

  const utterance = new SpeechSynthesisUtterance(customMessage);
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

function isQuestionAnswered(question) {
  const answer = appState.onboardingAnswers[question.key];
  if (question.multi) {
    return Array.isArray(answer) && answer.length > 0;
  }
  return typeof answer === "string" && answer.length > 0;
}

function renderOnboardingQuestion() {
  const card = byId("onboarding-card");
  const titleNode = byId("onboarding-question-title");
  const subtitleNode = byId("onboarding-question-subtitle");
  const optionsNode = byId("onboarding-options");
  const progressBar = byId("onboarding-progress-bar");
  const backButton = byId("onboarding-back");
  const nextButton = byId("onboarding-next");

  if (!card || !titleNode || !subtitleNode || !optionsNode || !progressBar || !backButton || !nextButton) {
    return;
  }

  const question = onboardingQuestions[appState.onboardingStep];
  titleNode.textContent = question.title;
  subtitleNode.textContent = question.subtitle;
  progressBar.style.width = `${((appState.onboardingStep + 1) / onboardingQuestions.length) * 100}%`;
  backButton.disabled = appState.onboardingStep === 0;
  nextButton.textContent = appState.onboardingStep === onboardingQuestions.length - 1 ? "Finish" : "Next";

  card.dataset.motion = card.dataset.motion || "forward";
  card.classList.add("is-transitioning");
  window.setTimeout(() => {
    optionsNode.innerHTML = "";

    question.options.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "onboarding-option";
      button.textContent = option;

      const currentAnswer = appState.onboardingAnswers[question.key];
      const selected = question.multi
        ? Array.isArray(currentAnswer) && currentAnswer.includes(option)
        : currentAnswer === option;
      if (selected) {
        button.classList.add("is-selected");
      }

      button.addEventListener("click", () => {
        if (question.multi) {
          const set = new Set(appState.onboardingAnswers[question.key] || []);
          if (set.has(option)) {
            set.delete(option);
          } else {
            set.add(option);
          }
          appState.onboardingAnswers[question.key] = Array.from(set);
        } else {
          appState.onboardingAnswers[question.key] = option;
        }
        card.dataset.motion = "none";
        renderOnboardingQuestion();
      });

      optionsNode.appendChild(button);
    });

    card.classList.remove("is-transitioning");
  }, 120);
}

async function submitOnboarding(skipped = false) {
  const nextButton = byId("onboarding-next");
  const backButton = byId("onboarding-back");
  const skipButton = byId("onboarding-skip");
  const statusNode = byId("onboarding-status");
  const overlay = byId("onboarding-overlay");

  setButtonLoading(nextButton, true, "Saving...");
  if (backButton) {
    backButton.disabled = true;
  }
  if (skipButton) {
    skipButton.disabled = true;
  }
  setMessage(statusNode, "Saving onboarding responses...", "info");

  try {
    const payload = await apiFetch(
      "/onboarding",
      {
        method: "POST",
        body: JSON.stringify({
          acne_type: appState.onboardingAnswers.acne_type,
          stress_level: appState.onboardingAnswers.stress_level,
          hormonal_issues: appState.onboardingAnswers.hormonal_issues,
          diet_type: appState.onboardingAnswers.diet_type,
          activity_level: appState.onboardingAnswers.activity_level,
          skipped,
        }),
      },
      true,
    );

    appState.user = payload.user;
    renderUserProfile();
    overlay?.classList.add("hidden");
    document.body.classList.remove("onboarding-open");
  } catch (error) {
    setMessage(statusNode, error.message || "Could not save onboarding responses.", "error");
    setButtonLoading(nextButton, false, "Saving...");
    if (backButton) {
      backButton.disabled = appState.onboardingStep === 0;
    }
    if (skipButton) {
      skipButton.disabled = false;
    }
  }
}

function maybeInitOnboardingQuiz() {
  if (!appState.user || appState.user.onboarding_completed) {
    return;
  }

  const overlay = byId("onboarding-overlay");
  const backButton = byId("onboarding-back");
  const nextButton = byId("onboarding-next");
  const skipButton = byId("onboarding-skip");
  const statusNode = byId("onboarding-status");

  if (!overlay || !backButton || !nextButton || !skipButton) {
    return;
  }

  appState.onboardingStep = 0;
  appState.onboardingAnswers = {
    acne_type: [],
    stress_level: "",
    hormonal_issues: "",
    diet_type: "",
    activity_level: "",
  };

  overlay.classList.remove("hidden");
  document.body.classList.add("onboarding-open");
  setMessage(statusNode, "");
  renderOnboardingQuestion();

  backButton.onclick = () => {
    if (appState.onboardingStep === 0) {
      return;
    }
    appState.onboardingStep -= 1;
    setMessage(statusNode, "");
    const card = byId("onboarding-card");
    if (card) {
      card.dataset.motion = "backward";
    }
    renderOnboardingQuestion();
  };

  nextButton.onclick = async () => {
    const question = onboardingQuestions[appState.onboardingStep];
    if (!isQuestionAnswered(question)) {
      setMessage(statusNode, "Please select an option before continuing.", "error");
      return;
    }

    setMessage(statusNode, "");

    if (appState.onboardingStep === onboardingQuestions.length - 1) {
      await submitOnboarding(false);
      return;
    }

    appState.onboardingStep += 1;
    const card = byId("onboarding-card");
    if (card) {
      card.dataset.motion = "forward";
    }
    renderOnboardingQuestion();
  };

  skipButton.onclick = async () => {
    await submitOnboarding(true);
  };
}
function bindDashboardEvents() {
  const logoutButton = byId("logout-button");
  const voiceGuideButton = byId("voice-guide-button");
  const downloadReportButton = byId("download-report-button");
  const reportStatus = byId("report-status");
  const sugarKeepButton = byId("sugar-streak-keep");
  const sugarBreakButton = byId("sugar-streak-break");
  const sugarStatus = byId("sugar-streak-status");
  const analyzeForm = byId("analyze-form");
  const imageInput = byId("image-input");
  const analyzeButton = byId("analyze-button");
  const analyzeStatus = byId("analyze-status");
  const uploadCaption = byId("upload-caption");
  const cameraStartButton = byId("camera-start-button");
  const cameraCaptureButton = byId("camera-capture-button");
  const cameraStopButton = byId("camera-stop-button");
  const cameraPanel = byId("camera-panel");
  const cameraPreview = byId("camera-preview");
  const cameraCanvas = byId("camera-canvas");
  const selectionList = byId("selection-list");
  const clearSelectionButton = byId("clear-selection-button");
  const analysisGallery = byId("analysis-gallery");
  const analysisBatchStatus = byId("analysis-batch-status");
  const analysisViewSwitcher = byId("analysis-view-switcher");
  const imageCompareGrid = byId("image-compare-grid");
  const originalImage = byId("original-image");
  const detectionCanvas = byId("detection-canvas");
  const overlayViewLabel = byId("overlay-view-label");
  const defaultUploadCaption = "Use even lighting and keep your face centered. You can add photos from your gallery or camera.";
  let selectedImages = [];
  let cameraStream = null;
  let captureCount = 0;
  const analysisViewLabels = {
    all: "Everything",
    regions: "Region Detected",
    "acne-type": "Acne Type",
    mesh: "Facial Mesh",
    pigmentation: "Hyperpigmentation Zones",
  };
  const faceZoneStyles = {
    forehead: { fill: "rgba(56, 189, 248, 0.18)", stroke: "#38bdf8" },
    left_cheek: { fill: "rgba(34, 197, 94, 0.18)", stroke: "#22c55e" },
    right_cheek: { fill: "rgba(250, 204, 21, 0.18)", stroke: "#facc15" },
    nose: { fill: "rgba(244, 114, 182, 0.18)", stroke: "#f472b6" },
    chin: { fill: "rgba(168, 85, 247, 0.18)", stroke: "#a855f7" },
  };
  const faceZoneLabelGroups = [
    { label: "Forehead", zoneNames: ["forehead"], offsetX: 0, offsetY: -14 },
    { label: "Cheek", zoneNames: ["left_cheek"], offsetX: -18, offsetY: -4 },
    { label: "Cheek", zoneNames: ["right_cheek"], offsetX: 18, offsetY: -4 },
    { label: "Nose", zoneNames: ["nose"], offsetX: 0, offsetY: 8 },
    { label: "Chin/Jawline", zoneNames: ["chin"], offsetX: 0, offsetY: 16 },
  ];

  function getAnalysisViewLabel(viewMode) {
    return analysisViewLabels[viewMode] || analysisViewLabels.all;
  }

  function updateAnalysisViewButtons() {
    if (overlayViewLabel) {
      overlayViewLabel.textContent = getAnalysisViewLabel(appState.analysisViewMode);
    }

    analysisViewSwitcher?.querySelectorAll("[data-view-mode]").forEach((button) => {
      const isActive = button.dataset.viewMode === appState.analysisViewMode;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });
  }

  function clearAnalysisResults() {
    appState.analysisResults.forEach((entry) => {
      if (entry.previewUrl) {
        window.URL.revokeObjectURL(entry.previewUrl);
      }
    });
    appState.analysisResults = [];
    appState.activeAnalysisIndex = -1;
  }

  function normalizeMeshPoint(point) {
    if (!point || typeof point !== "object") {
      return null;
    }

    const x = Number(point.x);
    const y = Number(point.y);
    const z = Number(point.z ?? 0);

    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return null;
    }

    return {
      x,
      y,
      z: Number.isFinite(z) ? z : 0,
    };
  }

  function normalizeZonePoint(point) {
    if (!point || typeof point !== "object") {
      return null;
    }

    const x = Number(point.x);
    const y = Number(point.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return null;
    }

    return { x, y };
  }

  function normalizeContourPoint(point) {
    return normalizeZonePoint(point);
  }

  function normalizePigmentationContours(contours) {
    if (!Array.isArray(contours)) {
      return [];
    }

    return contours
      .map((contour) => (Array.isArray(contour) ? contour.map(normalizeContourPoint).filter(Boolean) : []))
      .filter((contour) => contour.length >= 3);
  }

  function normalizeAcneTypeDetection(detection) {
    if (!detection || typeof detection !== "object") {
      return null;
    }

    const x1 = Number(detection.x1);
    const y1 = Number(detection.y1);
    const x2 = Number(detection.x2);
    const y2 = Number(detection.y2);
    const confidence = Number(detection.confidence ?? 0);
    if (![x1, y1, x2, y2].every(Number.isFinite)) {
      return null;
    }

    return {
      x1,
      y1,
      x2,
      y2,
      label: String(detection.label || "other"),
      rawLabel: String(detection.raw_label || detection.label || "other"),
      confidence: Number.isFinite(confidence) ? confidence : 0,
      color: String(detection.color || "#3b82f6"),
    };
  }

  function buildFaceMeshEdges(landmarks) {
    if (!Array.isArray(landmarks) || landmarks.length < 3) {
      return [];
    }

    let minX = landmarks[0].x;
    let maxX = landmarks[0].x;
    let minY = landmarks[0].y;
    let maxY = landmarks[0].y;

    landmarks.forEach((point) => {
      minX = Math.min(minX, point.x);
      maxX = Math.max(maxX, point.x);
      minY = Math.min(minY, point.y);
      maxY = Math.max(maxY, point.y);
    });

    const faceSpan = Math.max(maxX - minX, maxY - minY, 1);
    const maxDistance = Math.max(faceSpan * 0.09, 18);
    const maxDistanceSquared = maxDistance * maxDistance;
    const edges = new Set();

    landmarks.forEach((point, index) => {
      const neighbors = [];

      landmarks.forEach((candidate, candidateIndex) => {
        if (index === candidateIndex) {
          return;
        }

        const dx = point.x - candidate.x;
        const dy = point.y - candidate.y;
        const distanceSquared = (dx * dx) + (dy * dy);
        if (distanceSquared > maxDistanceSquared) {
          return;
        }

        neighbors.push({ candidateIndex, distanceSquared });
      });

      neighbors
        .sort((left, right) => left.distanceSquared - right.distanceSquared)
        .slice(0, 3)
        .forEach(({ candidateIndex }) => {
          const edgeStart = Math.min(index, candidateIndex);
          const edgeEnd = Math.max(index, candidateIndex);
          edges.add(`${edgeStart}:${edgeEnd}`);
        });
    });

    return Array.from(edges, (edgeKey) => edgeKey.split(":").map((value) => Number(value)));
  }

  function getDepthStats(landmarks) {
    const zValues = landmarks
      .map((point) => Number(point.z ?? 0))
      .filter((value) => Number.isFinite(value));

    if (zValues.length === 0) {
      return { min: 0, span: 1 };
    }

    const min = Math.min(...zValues);
    const max = Math.max(...zValues);
    return { min, span: Math.max(max - min, 0.0001) };
  }

  function drawBoxLabels(context, x, y, text, accent = "#0f172a") {
    context.save();
    context.font = "600 13px system-ui, sans-serif";
    const textWidth = context.measureText(text).width;
    const width = textWidth + 20;
    const height = 24;
    const rawLabelX = x - (textWidth / 2) - 10;
    const rawLabelY = y - 14;
    const labelX = Math.min(Math.max(8, rawLabelX), Math.max(8, context.canvas.width - width - 8));
    const labelY = Math.min(Math.max(8, rawLabelY), Math.max(8, context.canvas.height - height - 8));

    context.fillStyle = "rgba(15, 23, 42, 0.86)";
    context.fillRect(labelX, labelY, width, height);
    context.strokeStyle = accent;
    context.lineWidth = 1;
    context.strokeRect(labelX, labelY, width, height);
    context.fillStyle = "#f8fafc";
    context.textBaseline = "middle";
    context.fillText(text, labelX + 10, labelY + (height / 2));
    context.restore();
  }

  function drawFaceZones(context, zones, offsetX, offsetY) {
    Object.entries(zones).forEach(([zoneName, zonePoints]) => {
      if (!Array.isArray(zonePoints) || zonePoints.length < 3) {
        return;
      }

      const style = faceZoneStyles[zoneName] || { fill: "rgba(148, 163, 184, 0.16)", stroke: "#94a3b8" };
      context.save();
      context.beginPath();
      zonePoints.forEach((point, index) => {
        const drawX = point.x + offsetX;
        const drawY = point.y + offsetY;
        if (index === 0) {
          context.moveTo(drawX, drawY);
        } else {
          context.lineTo(drawX, drawY);
        }
      });
      context.closePath();
      context.fillStyle = style.fill;
      context.fill();
      context.strokeStyle = style.stroke;
      context.lineWidth = 2;
      context.stroke();
      context.restore();
    });
  }

  function getZoneCentroid(zonePoints) {
    if (!Array.isArray(zonePoints) || zonePoints.length === 0) {
      return null;
    }

    const total = zonePoints.reduce((accumulator, point) => ({
      x: accumulator.x + point.x,
      y: accumulator.y + point.y,
    }), { x: 0, y: 0 });

    return {
      x: total.x / zonePoints.length,
      y: total.y / zonePoints.length,
    };
  }

  function drawFaceZoneLabels(context, zones, offsetX, offsetY) {
    faceZoneLabelGroups.forEach(({ label, zoneNames, offsetX: labelOffsetX = 0, offsetY: labelOffsetY = 0 }) => {
      const centroids = zoneNames
        .map((zoneName) => getZoneCentroid(zones[zoneName]))
        .filter(Boolean);

      if (centroids.length === 0) {
        return;
      }

      const average = centroids.reduce((accumulator, point) => ({
        x: accumulator.x + point.x,
        y: accumulator.y + point.y,
      }), { x: 0, y: 0 });

      drawBoxLabels(
        context,
        (average.x / centroids.length) + offsetX + labelOffsetX,
        (average.y / centroids.length) + offsetY + labelOffsetY,
        label,
        "#38bdf8",
      );
    });
  }

  function drawFaceMesh(context, landmarks, offsetX, offsetY) {
    if (!Array.isArray(landmarks) || landmarks.length === 0) {
      return;
    }

    const edges = buildFaceMeshEdges(landmarks);
    const depthStats = getDepthStats(landmarks);

    edges.forEach(([startIndex, endIndex]) => {
      const start = landmarks[startIndex];
      const end = landmarks[endIndex];
      if (!start || !end) {
        return;
      }

      const depthRatio = Math.min(
        1,
        Math.max(0, (((start.z + end.z) / 2) - depthStats.min) / depthStats.span),
      );
      const lineAlpha = (0.38 - (depthRatio * 0.16)).toFixed(3);

      context.save();
      context.beginPath();
      context.moveTo(start.x + offsetX, start.y + offsetY);
      context.lineTo(end.x + offsetX, end.y + offsetY);
      context.strokeStyle = `rgba(125, 211, 252, ${lineAlpha})`;
      context.lineWidth = 1;
      context.stroke();
      context.restore();
    });

    landmarks.forEach((point) => {
      const depthRatio = Math.min(1, Math.max(0, ((point.z - depthStats.min) / depthStats.span)));
      const radius = 1.1 + ((1 - depthRatio) * 1.5);
      const pointAlpha = (0.55 + ((1 - depthRatio) * 0.3)).toFixed(3);

      context.save();
      context.beginPath();
      context.arc(point.x + offsetX, point.y + offsetY, radius, 0, Math.PI * 2);
      context.fillStyle = `rgba(255, 255, 255, ${pointAlpha})`;
      context.fill();
      context.restore();
    });
  }

  function drawPigmentationContours(context, contours, offsetX, offsetY) {
    if (!Array.isArray(contours) || contours.length === 0) {
      return;
    }

    contours.forEach((contour) => {
      if (!Array.isArray(contour) || contour.length < 3) {
        return;
      }

      context.save();
      context.beginPath();
      contour.forEach((point, index) => {
        const drawX = point.x + offsetX;
        const drawY = point.y + offsetY;
        if (index === 0) {
          context.moveTo(drawX, drawY);
        } else {
          context.lineTo(drawX, drawY);
        }
      });
      context.closePath();
      context.fillStyle = "rgba(37, 99, 235, 0.16)";
      context.fill();
      context.strokeStyle = "#1d4ed8";
      context.lineWidth = 2;
      context.stroke();
      context.restore();
    });
  }

  function drawDetectionBoxes(context, boxes, offsetX, offsetY) {
    context.save();
    context.strokeStyle = "#22c55e";
    context.fillStyle = "#22c55e";
    context.lineWidth = 2;
    context.font = "16px sans-serif";

    boxes.forEach((box, index) => {
      const [x1, y1, x2, y2] = box;
      context.strokeRect(x1 + offsetX, y1 + offsetY, x2 - x1, y2 - y1);
      context.fillText(`ID ${index + 1}`, x1 + offsetX, Math.max(18, y1 + offsetY - 6));
    });

    context.restore();
  }

  function drawAcneTypeDetections(context, detections, offsetX, offsetY) {
    if (!Array.isArray(detections) || detections.length === 0) {
      return;
    }

    context.save();
    context.lineWidth = 2;
    context.font = "16px sans-serif";
    context.textBaseline = "top";

    detections.forEach((detection) => {
      const width = detection.x2 - detection.x1;
      const height = detection.y2 - detection.y1;
      const accentColor = detection.color || "#3b82f6";
      const label = `${detection.label} ${detection.confidence.toFixed(2)}`;
      const textMetrics = context.measureText(label);
      const textWidth = Math.ceil(textMetrics.width);
      const boxX = detection.x1 + offsetX;
      const boxY = detection.y1 + offsetY;
      const labelHeight = 24;
      const labelY = Math.max(0, boxY - labelHeight);

      context.strokeStyle = accentColor;
      context.strokeRect(boxX, boxY, width, height);
      context.fillStyle = accentColor;
      context.fillRect(boxX, labelY, textWidth + 14, labelHeight);
      context.fillStyle = "#ffffff";
      context.fillText(label, boxX + 7, labelY + 4);
    });

    context.restore();
  }

  function buildAcneTypeSummary(data = {}) {
    if (!data.acne_type_available) {
      return "Acne-type model is not configured yet for this project.";
    }

    const counts = data.acne_type_counts || {};
    const comedonal = Number(counts.comedonal || 0);
    const inflammatory = Number(counts.inflammatory || 0);
    const other = Number(counts.other || 0);
    const total = comedonal + inflammatory + other;

    if (total === 0) {
      return "Acne-type model ran on this image, but no acne-type detections were returned.";
    }

    return `Acne-type view shows ${total} typed detection${total === 1 ? "" : "s"}: ${comedonal} comedonal, ${inflammatory} inflammatory, ${other} other.`;
  }

  function drawDetectionPreview(imageUrl, boxes = [], overlayImageUrl = "", faceData = {}, viewMode = appState.analysisViewMode) {
    const normalizedLandmarks = Array.isArray(faceData.landmarks)
      ? faceData.landmarks.map(normalizeMeshPoint).filter(Boolean)
      : [];
    const normalizedZones = Object.fromEntries(
      Object.entries(faceData.zones || {}).map(([zoneName, zonePoints]) => [
        zoneName,
        Array.isArray(zonePoints) ? zonePoints.map(normalizeZonePoint).filter(Boolean) : [],
      ]),
    );
    const normalizedPigmentationContours = normalizePigmentationContours(faceData.pigmentation_contours);
    const normalizedAcneTypeDetections = Array.isArray(faceData.acne_type_detections)
      ? faceData.acne_type_detections.map(normalizeAcneTypeDetection).filter(Boolean)
      : [];
    const acneTypeProcessedImageUrl = faceData.acne_type_processed_image_url || "";
    const regionBoxes = Array.isArray(faceData.region_boxes) ? faceData.region_boxes : [];
    const hasBoxes = Array.isArray(boxes) && boxes.length > 0;
    const hasRegionBoxes = regionBoxes.length > 0;
    const hasFaceOverlay = normalizedLandmarks.length > 0 || Object.values(normalizedZones).some((zonePoints) => zonePoints.length >= 3);
    const hasPigmentationOverlay = normalizedPigmentationContours.length > 0 || Object.values(normalizedZones).some((zonePoints) => zonePoints.length >= 3);
    const hasAcneTypeOverlay = Boolean(acneTypeProcessedImageUrl) || normalizedAcneTypeDetections.length > 0;
    const canRenderModeClientSide = (
      (viewMode === "all" && (hasBoxes || hasRegionBoxes || hasFaceOverlay || hasPigmentationOverlay || hasAcneTypeOverlay))
      || (viewMode === "regions" && hasRegionBoxes)
      || (viewMode === "acne-type" && normalizedAcneTypeDetections.length > 0 && !acneTypeProcessedImageUrl)
      || (viewMode === "mesh" && hasFaceOverlay)
      || (viewMode === "pigmentation" && hasPigmentationOverlay)
    );
    const previewUrl = viewMode === "acne-type"
      ? (acneTypeProcessedImageUrl || imageUrl)
      : ((canRenderModeClientSide && imageUrl) ? imageUrl : (overlayImageUrl || imageUrl));
    if (!detectionCanvas || !previewUrl) {
      return;
    }

    const context = detectionCanvas.getContext("2d");
    if (!context) {
      return;
    }

    const image = new Image();
    image.onload = () => {
      const imageWidth = image.naturalWidth || image.width;
      const imageHeight = image.naturalHeight || image.height;
      const squareSize = Math.max(imageWidth, imageHeight);
      const offsetX = (squareSize - imageWidth) / 2;
      const offsetY = (squareSize - imageHeight) / 2;

      detectionCanvas.width = squareSize;
      detectionCanvas.height = squareSize;
      context.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
      context.fillStyle = "#0f172a";
      context.fillRect(0, 0, detectionCanvas.width, detectionCanvas.height);
      context.drawImage(image, offsetX, offsetY, imageWidth, imageHeight);

      if (viewMode === "acne-type") {
        if (!acneTypeProcessedImageUrl && hasAcneTypeOverlay) {
          drawAcneTypeDetections(context, normalizedAcneTypeDetections, offsetX, offsetY);
        }
        return;
      }

      if (canRenderModeClientSide && (viewMode === "all" || viewMode === "pigmentation")) {
        drawFaceZones(context, normalizedZones, offsetX, offsetY);
      }

      if (canRenderModeClientSide && (viewMode === "all" || viewMode === "pigmentation")) {
        drawPigmentationContours(context, normalizedPigmentationContours, offsetX, offsetY);
      }

      if (canRenderModeClientSide && (viewMode === "all" || viewMode === "mesh")) {
        drawFaceMesh(context, normalizedLandmarks, offsetX, offsetY);
      }

      if (canRenderModeClientSide && (viewMode === "all" || viewMode === "mesh" || viewMode === "pigmentation")) {
        drawFaceZoneLabels(context, normalizedZones, offsetX, offsetY);
      }

      if (canRenderModeClientSide && (viewMode === "all" || viewMode === "regions") && hasRegionBoxes) {
        drawDetectionBoxes(context, regionBoxes, offsetX, offsetY);
      }

      if (canRenderModeClientSide && viewMode === "all" && hasAcneTypeOverlay) {
        drawAcneTypeDetections(context, normalizedAcneTypeDetections, offsetX, offsetY);
      }
    };
    image.src = previewUrl;
  }

  function renderActiveAnalysis(entry) {
    const data = entry?.data || {};
    imageCompareGrid?.classList.remove("is-empty");
    updateAnalysisViewButtons();
    if (originalImage) {
      originalImage.src = entry?.previewUrl || "";
    }
    const lesionCount = data.acne_count ?? 0;
    const regionCount = data.region_count ?? (Array.isArray(data.region_boxes) ? data.region_boxes.length : 0);
    const faceSummary = data.face_detected
      ? " Face mesh and labeled zones are shown in the overlay."
      : " Face landmarks were not detected in this image.";
    byId("summary-value").textContent = appState.analysisViewMode === "acne-type"
      ? `${buildAcneTypeSummary(data)} Viewing: ${getAnalysisViewLabel(appState.analysisViewMode)}.`
      : `Detected ${lesionCount} lesion${lesionCount === 1 ? "" : "s"} from acne-type analysis and ${regionCount} region${regionCount === 1 ? "" : "s"} from the region model. Viewing: ${getAnalysisViewLabel(appState.analysisViewMode)}.${faceSummary}`;
    byId("acne-count-value").textContent = data.acne_count ?? "--";
    byId("metric-acne-count-value").textContent = data.acne_count ?? "--";
    byId("boxes-count-value").textContent = regionCount || 0;
    byId("metric-boxes-count-value").textContent = regionCount || 0;
    drawDetectionPreview(entry?.previewUrl || "", data.boxes || [], data.processed_image_url || "", data, appState.analysisViewMode);
    setReportButtonState(downloadReportButton, reportStatus, null);
  }

  function resetAnalysisDisplay() {
    imageCompareGrid?.classList.add("is-empty");
    updateAnalysisViewButtons();
    if (originalImage) {
      originalImage.removeAttribute("src");
    }
    if (detectionCanvas) {
      const context = detectionCanvas.getContext("2d");
      context?.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
    }
    byId("summary-value").textContent = "Upload an image to detect acne-type lesions and compare them with the broader region model.";
    byId("acne-count-value").textContent = "--";
    byId("boxes-count-value").textContent = "--";
    byId("metric-acne-count-value").textContent = "--";
    byId("metric-boxes-count-value").textContent = "--";
    setReportButtonState(downloadReportButton, reportStatus, null);
  }

  function updateVoiceGuideForAnalysis(data, shouldSpeak = false) {
    updateVoiceGuideState(voiceGuideButton, false);
  }

  function updateUploadCaption() {
    if (!uploadCaption) {
      return;
    }

    const inputFileCount = Array.from(imageInput?.files || []).filter((file) => isAcceptedImageFile(file)).length;
    const totalCount = selectedImages.length || inputFileCount;

    if (totalCount === 0) {
      uploadCaption.textContent = defaultUploadCaption;
      return;
    }

    uploadCaption.textContent = `${totalCount} image${totalCount === 1 ? "" : "s"} ready for analysis. Add more anytime.`;
  }

  function updateAnalyzeButtonState() {
    if (!analyzeButton) {
      return;
    }

    const inputFiles = Array.from(imageInput?.files || []).filter((file) => isAcceptedImageFile(file));
    const totalCount = selectedImages.length || inputFiles.length;

    analyzeButton.disabled = false;
    analyzeButton.setAttribute("aria-disabled", "false");
    analyzeButton.textContent = totalCount > 0
      ? `Analyze ${totalCount} Image${totalCount === 1 ? "" : "s"}`
      : "Analyze Selected Images";
    analyzeButton.dataset.defaultLabel = analyzeButton.textContent;

    if (clearSelectionButton) {
      clearSelectionButton.classList.toggle("hidden", selectedImages.length === 0 && inputFiles.length === 0);
    }
  }

  function getPendingAnalysisEntries() {
    if (selectedImages.length > 0) {
      return selectedImages.map((entry) => ({
        id: entry.id,
        file: entry.file,
        source: entry.source,
        label: entry.file.name,
        previewUrl: entry.previewUrl,
      }));
    }

    return Array.from(imageInput?.files || [])
      .filter((file) => isAcceptedImageFile(file))
      .map((file) => ({
        id: createBatchItemId("upload"),
        file,
        source: "upload",
        label: file.name,
        previewUrl: window.URL.createObjectURL(file),
      }));
  }

  function renderSelectionList() {
    if (!selectionList) {
      return;
    }

    selectionList.innerHTML = "";

    if (selectedImages.length === 0) {
      const emptyState = document.createElement("p");
      emptyState.className = "selection-empty";
      emptyState.textContent = "No images selected yet.";
      selectionList.appendChild(emptyState);
      return;
    }

    selectedImages.forEach((entry) => {
      const item = document.createElement("div");
      item.className = "selection-card";

      const thumb = document.createElement("div");
      thumb.className = "selection-thumb";
      const thumbImage = document.createElement("img");
      thumbImage.src = entry.previewUrl;
      thumbImage.alt = `${entry.file.name} preview`;
      thumb.appendChild(thumbImage);

      const meta = document.createElement("div");
      meta.className = "selection-meta";
      const name = document.createElement("strong");
      name.className = "selection-name";
      name.textContent = entry.file.name;
      const source = document.createElement("span");
      source.textContent = `${entry.source === "camera" ? "Camera" : "Upload"} | ${(entry.file.size / 1024 / 1024).toFixed(2)} MB`;
      meta.append(name, source);

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "selection-remove";
      removeButton.textContent = "Remove";
      removeButton.addEventListener("click", () => {
        const target = selectedImages.find((candidate) => candidate.id === entry.id);
        if (target?.previewUrl) {
          window.URL.revokeObjectURL(target.previewUrl);
        }
        selectedImages = selectedImages.filter((candidate) => candidate.id !== entry.id);
        renderSelectionList();
        updateUploadCaption();
        updateAnalyzeButtonState();
        setMessage(analyzeStatus, "");
      });

      item.append(thumb, meta, removeButton);
      selectionList.appendChild(item);
    });
  }

  function renderAnalysisGallery() {
    if (!analysisGallery) {
      return;
    }

    analysisGallery.innerHTML = "";

    if (appState.analysisResults.length === 0) {
      const emptyState = document.createElement("p");
      emptyState.className = "selection-empty";
      emptyState.textContent = "Analyze one or more images to review them here.";
      analysisGallery.appendChild(emptyState);
      return;
    }

    appState.analysisResults.forEach((entry, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `analysis-gallery-item${index === appState.activeAnalysisIndex ? " is-active" : ""}`;

      const thumb = document.createElement("div");
      thumb.className = "analysis-gallery-thumb";
      const thumbImage = document.createElement("img");
      thumbImage.src = entry.previewUrl;
      thumbImage.alt = `${entry.label} result preview`;
      thumb.appendChild(thumbImage);

      const copy = document.createElement("div");
      copy.className = "analysis-gallery-copy";
      const title = document.createElement("strong");
      title.textContent = entry.label;
      const meta = document.createElement("span");
      meta.textContent = `${entry.data.acne_count} lesion${entry.data.acne_count === 1 ? "" : "s"} detected`;
      copy.append(title, meta);

      button.append(thumb, copy);
      button.addEventListener("click", () => {
        appState.activeAnalysisIndex = index;
        renderAnalysisGallery();
        renderActiveAnalysis(entry);
        updateVoiceGuideForAnalysis(entry.data);
        if (analysisBatchStatus) {
          analysisBatchStatus.textContent = appState.analysisResults.length === 1
            ? `Showing ${entry.label}.`
            : `Showing ${index + 1} of ${appState.analysisResults.length}: ${entry.label}.`;
        }
      });

      analysisGallery.appendChild(button);
    });
  }

  function addFilesToSelection(files, source = "upload") {
    const nextEntries = [];
    let skippedNonImages = 0;
    let skippedDuplicates = 0;

    files.forEach((file) => {
      if (!isAcceptedImageFile(file)) {
        skippedNonImages += 1;
        return;
      }

      const signature = [source, file.name, file.size, file.lastModified].join(":");
      const exists = selectedImages.some((entry) => entry.signature === signature);
      if (exists) {
        skippedDuplicates += 1;
        return;
      }

      nextEntries.push({
        id: createBatchItemId(source),
        file,
        source,
        signature,
        previewUrl: window.URL.createObjectURL(file),
      });
    });

    if (nextEntries.length === 0) {
      updateUploadCaption();
      updateAnalyzeButtonState();
      if (skippedNonImages > 0) {
        setMessage(analyzeStatus, "That file was not recognized as an image. Try JPG, PNG, WEBP, or HEIC.", "error");
      } else if (skippedDuplicates > 0) {
        setMessage(analyzeStatus, "That image is already in the queue.", "info");
      }
      return;
    }

    selectedImages = [...selectedImages, ...nextEntries];
    renderSelectionList();
    updateUploadCaption();
    updateAnalyzeButtonState();

    const suffix = skippedDuplicates > 0
      ? ` ${skippedDuplicates} duplicate${skippedDuplicates === 1 ? " was" : "s were"} skipped.`
      : "";
    setMessage(analyzeStatus, `${nextEntries.length} image${nextEntries.length === 1 ? "" : "s"} added to the queue.${suffix}`, "success");
  }

  function clearSelectedImages() {
    selectedImages.forEach((entry) => {
      if (entry.previewUrl) {
        window.URL.revokeObjectURL(entry.previewUrl);
      }
    });
    selectedImages = [];
    if (imageInput) {
      imageInput.value = "";
    }
    renderSelectionList();
    updateUploadCaption();
    updateAnalyzeButtonState();
  }

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      cameraStream = null;
    }

    if (cameraPreview) {
      cameraPreview.srcObject = null;
    }

    cameraPanel?.classList.add("hidden");
    if (cameraCaptureButton) {
      cameraCaptureButton.disabled = true;
    }
    if (cameraStopButton) {
      cameraStopButton.disabled = true;
    }
  }

  renderUserProfile();
  renderSugarFreeStreak();
  updateVoiceGuideState(voiceGuideButton, false);
  resetAnalysisDisplay();
  updateAnalysisViewButtons();
  renderSelectionList();
  renderAnalysisGallery();
  updateUploadCaption();
  updateAnalyzeButtonState();

  analysisViewSwitcher?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-view-mode]");
    if (!button) {
      return;
    }

    const nextViewMode = button.dataset.viewMode || "all";
    if (nextViewMode === appState.analysisViewMode) {
      return;
    }

    appState.analysisViewMode = nextViewMode;
    updateAnalysisViewButtons();

    const activeEntry = appState.analysisResults[appState.activeAnalysisIndex] || appState.analysisResults[0];
    if (activeEntry) {
      renderActiveAnalysis(activeEntry);
    }
  });

  imageInput?.addEventListener("change", () => {
    const files = Array.from(imageInput.files || []);
    if (files.length === 0) {
      updateUploadCaption();
      updateAnalyzeButtonState();
      return;
    }

    addFilesToSelection(files, "upload");
    updateVoiceGuideState(voiceGuideButton, false);
  });

  cameraStartButton?.addEventListener("click", async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMessage(analyzeStatus, "Camera capture is not supported in this browser.", "error");
      return;
    }

    try {
      stopCamera();
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 1600 },
        },
        audio: false,
      });

      if (cameraPreview) {
        cameraPreview.srcObject = cameraStream;
      }
      cameraPanel?.classList.remove("hidden");
      if (cameraCaptureButton) {
        cameraCaptureButton.disabled = false;
      }
      if (cameraStopButton) {
        cameraStopButton.disabled = false;
      }
      setMessage(analyzeStatus, "Camera is ready. Capture as many photos as you need.", "info");
    } catch (error) {
      setMessage(analyzeStatus, error.message || "Could not access the camera.", "error");
    }
  });

  cameraCaptureButton?.addEventListener("click", async () => {
    if (!cameraPreview || !cameraCanvas || !cameraStream) {
      setMessage(analyzeStatus, "Open the camera before capturing a photo.", "error");
      return;
    }

    if (!cameraPreview.videoWidth || !cameraPreview.videoHeight) {
      setMessage(analyzeStatus, "Camera is still warming up. Try again in a moment.", "info");
      return;
    }

    cameraCanvas.width = cameraPreview.videoWidth;
    cameraCanvas.height = cameraPreview.videoHeight;
    const context = cameraCanvas.getContext("2d");
    if (!context) {
      setMessage(analyzeStatus, "Could not capture the camera frame.", "error");
      return;
    }

    context.drawImage(cameraPreview, 0, 0, cameraCanvas.width, cameraCanvas.height);
    const blob = await new Promise((resolve) => cameraCanvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!blob) {
      setMessage(analyzeStatus, "Photo capture failed. Please try again.", "error");
      return;
    }

    captureCount += 1;
    const file = new File([blob], `camera-capture-${captureCount}.jpg`, {
      type: "image/jpeg",
      lastModified: Date.now(),
    });
    addFilesToSelection([file], "camera");
    setMessage(analyzeStatus, "Photo captured and added to the queue.", "success");
  });

  cameraStopButton?.addEventListener("click", () => {
    stopCamera();
    setMessage(analyzeStatus, "Camera closed. Your queued images are still ready.", "info");
  });

  clearSelectionButton?.addEventListener("click", () => {
    clearSelectedImages();
    setMessage(analyzeStatus, "Selection cleared.", "info");
  });

  analyzeForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const pendingEntries = getPendingAnalysisEntries();
    if (pendingEntries.length === 0) {
      setMessage(analyzeStatus, "Please choose at least one image first.", "error");
      return;
    }

    setButtonLoading(analyzeButton, true, "Analyzing...");
    updateVoiceGuideState(voiceGuideButton, false);
    clearAnalysisResults();
    renderAnalysisGallery();
    if (analysisBatchStatus) {
      analysisBatchStatus.textContent = `Analyzing ${pendingEntries.length} image${pendingEntries.length === 1 ? "" : "s"}...`;
    }

    try {
      const completed = [];
      const failures = [];

      for (let index = 0; index < pendingEntries.length; index += 1) {
        const entry = pendingEntries[index];
        const formData = new FormData();
        formData.append("file", entry.file, entry.file.name);
        setMessage(analyzeStatus, `Analyzing image ${index + 1} of ${pendingEntries.length}: ${entry.file.name}`, "info");

        try {
          const data = await apiFetch("/analyze", { method: "POST", body: formData });
          completed.push({
            id: entry.id,
            label: entry.file.name,
            source: entry.source,
            previewUrl: window.URL.createObjectURL(entry.file),
            data,
          });
          appState.analysisResults = [...completed];
          if (appState.activeAnalysisIndex === -1) {
            appState.activeAnalysisIndex = 0;
            renderActiveAnalysis(completed[0]);
            updateVoiceGuideForAnalysis(data);
          }
          renderAnalysisGallery();
        } catch (error) {
          failures.push(`${entry.file.name}: ${error.message || "Analysis failed."}`);
        }
      }

      if (completed.length === 0) {
        throw new Error(failures[0] || "Analysis failed.");
      }

      appState.analysisResults = completed;
      appState.activeAnalysisIndex = 0;
      renderActiveAnalysis(completed[0]);
      renderAnalysisGallery();
      updateVoiceGuideForAnalysis(completed[0].data, true);

      if (analysisBatchStatus) {
        analysisBatchStatus.textContent = completed.length === 1
          ? `Showing ${completed[0].label}.`
          : `Showing 1 of ${completed.length}: ${completed[0].label}.`;
      }

      const successMessage = failures.length > 0
        ? `Analysis complete for ${completed.length} image${completed.length === 1 ? "" : "s"}. ${failures.length} failed.`
        : `Analysis complete for ${completed.length} image${completed.length === 1 ? "" : "s"}.`;
      setMessage(analyzeStatus, successMessage, failures.length > 0 ? "info" : "success");
    } catch (error) {
      setMessage(analyzeStatus, error.message || "Analysis failed.", "error");
    } finally {
      setButtonLoading(analyzeButton, false, "Analyzing...");
    }
  });

  window.addEventListener("beforeunload", stopCamera);

  async function saveDashboardSugarCheckin(sugarFree) {
    const activeButton = sugarFree ? sugarKeepButton : sugarBreakButton;
    const inactiveButton = sugarFree ? sugarBreakButton : sugarKeepButton;
    const loadingLabel = sugarFree ? "Keeping..." : "Saving...";

    setButtonLoading(activeButton, true, loadingLabel);
    if (inactiveButton) {
      inactiveButton.disabled = true;
    }
    setMessage(sugarStatus, sugarFree ? "Keeping your streak going..." : "Logging today's sugar intake...", "info");

    try {
      const data = await apiFetch("/log-health", {
        method: "POST",
        body: JSON.stringify({
          entry_date: getTodayInputValue(),
          sugar_free: sugarFree,
          source: "dashboard_quick_checkin",
          notes: sugarFree ? "Dashboard sugar-free check-in" : "Dashboard sugar check-in",
          tags: ["dashboard", "sugar-streak"],
        }),
      });

      appState.logs.unshift(data.log);
      appState.logs = appState.logs.slice(0, 120);
      renderSugarFreeStreak();
      setMessage(sugarStatus, sugarFree ? "Sugar-free today recorded. Streak continued." : "Sugar intake recorded. Streak broken for today.", "success");
    } catch (error) {
      setMessage(sugarStatus, error.message || "Could not save today's sugar status.", "error");
    } finally {
      setButtonLoading(activeButton, false, loadingLabel);
      if (inactiveButton) {
        inactiveButton.disabled = false;
      }
    }
  }

  bindLogout(logoutButton);
  voiceGuideButton?.addEventListener("click", speakGuide);
  downloadReportButton?.addEventListener("click", async () => {
    await downloadReportArtifact(downloadReportButton, reportStatus);
  });
  sugarKeepButton?.addEventListener("click", async () => {
    await saveDashboardSugarCheckin(true);
  });
  sugarBreakButton?.addEventListener("click", async () => {
    await saveDashboardSugarCheckin(false);
  });
}

async function initDashboardPage() {
  const user = await fetchCurrentUser();
  if (!user) {
    redirectTo("/login");
    return;
  }

  appState.user = user;

  try {
    appState.logs = await fetchHealthLogs(120);
  } catch (error) {
    appState.logs = [];
  }

  bindDashboardEvents();
  maybeInitOnboardingQuiz();
}

async function initProfilePage() {
  const user = await fetchCurrentUser();
  if (!user) {
    redirectTo("/login");
    return;
  }

  appState.user = user;
  renderUserProfile();
  bindLogout(byId("logout-button"));

  const profileForm = byId("profile-form");
  const profileStatus = byId("profile-status");
  const profileSubmit = byId("profile-submit");
  const nameInput = byId("profile-name");
  const emailInput = byId("profile-email");
  const ageInput = byId("profile-age");
  const genderInput = byId("profile-gender");
  const birthdateInput = byId("profile-birthdate");

  if (!profileForm || !nameInput || !emailInput || !ageInput || !genderInput || !birthdateInput) {
    return;
  }

  function fillProfileForm() {
    nameInput.value = appState.user?.name || "";
    emailInput.value = appState.user?.email || "";
    ageInput.value = appState.user?.age ?? "";
    genderInput.value = appState.user?.gender || "";
    birthdateInput.value = appState.user?.birthdate || "";
  }

  function clearStatus() {
    setMessage(profileStatus, "");
  }

  fillProfileForm();
  nameInput.addEventListener("input", clearStatus);
  emailInput.addEventListener("input", clearStatus);
  ageInput.addEventListener("input", clearStatus);
  genderInput.addEventListener("change", clearStatus);
  birthdateInput.addEventListener("change", clearStatus);

  profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!nameInput.value.trim()) {
      setMessage(profileStatus, "Please enter your full name.", "error");
      return;
    }
    if (!isValidEmail(emailInput.value)) {
      setMessage(profileStatus, "Please enter a valid email address.", "error");
      return;
    }

    setButtonLoading(profileSubmit, true, "Saving...");
    setMessage(profileStatus, "Saving profile changes...", "info");

    try {
      const payload = await apiFetch("/me", {
        method: "PUT",
        body: JSON.stringify({
          name: nameInput.value.trim(),
          email: normalizeEmail(emailInput.value),
          age: ageInput.value ? Number(ageInput.value) : null,
          gender: genderInput.value,
          birthdate: birthdateInput.value || null,
        }),
      });

      appState.user = payload.user;
      renderUserProfile();
      fillProfileForm();
      setMessage(profileStatus, payload.message || "Profile updated.", "success");
    } catch (error) {
      setMessage(profileStatus, error.message || "Could not update profile.", "error");
    } finally {
      setButtonLoading(profileSubmit, false, "Saving...");
    }
  });
}

async function initHealthLogsPage() {
  const user = await fetchCurrentUser();
  if (!user) {
    redirectTo("/login");
    return;
  }

  appState.user = user;
  renderUserProfile();
  bindLogout(byId("logout-button"));

  try {
    appState.logs = await fetchHealthLogs(12);
  } catch (error) {
    appState.logs = [];
  }

  bindHealthLogForms();
}

async function bootstrap() {
  startTaglineRotation();

  if (page === "login") {
    await initLoginPage();
    return;
  }

  if (page === "register") {
    await initRegisterPage();
    return;
  }

  if (page === "reset-password") {
    await initResetPasswordPage();
    return;
  }

  if (page === "dashboard") {
    await initDashboardPage();
    return;
  }

  if (page === "profile") {
    await initProfilePage();
    return;
  }

  if (page === "health-logs") {
    await initHealthLogsPage();
  }
}

bootstrap();
























