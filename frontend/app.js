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

async function fetchHealthLogs() {
  const payload = await apiFetch("/health-logs-data");
  return payload.logs || [];
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
    time.textContent = formatEntryDate(log.entry_date || (log.date ? String(log.date).slice(0, 10) : ""));

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
      chip.className = metric.accent ? "log-metric log-metric-accent" : "log-metric";
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
  entryDateInput?.addEventListener("change", updateMenstrualSummary);
  cycleDayInput?.addEventListener("input", updateMenstrualSummary);
  periodPhaseInput?.addEventListener("change", updateMenstrualSummary);

  ensureEntryDate();
  setWaterCount(0);
  setStoolCount(0);
  syncMenstrualVisibility();
  renderRecentLogs(recentLogs);

  healthLogForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    setButtonLoading(healthSubmit, true, "Saving...");
    setMessage(healthStatus, "Saving health log...", "info");

    const payload = {
      entry_date: entryDateInput?.value || getTodayInputValue(),
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

function showPreview(file) {
  const previewWrapper = byId("preview-wrapper");
  const previewImage = byId("preview-image");
  if (!previewWrapper || !previewImage) {
    return;
  }

  const reader = new FileReader();
  reader.onload = (event) => {
    previewImage.src = event.target.result;
    previewWrapper.classList.remove("hidden");
  };
  reader.readAsDataURL(file);
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
  return ["Moderate", "High"].includes(data.acne.severity)
    || data.acne.count >= 2
    || data.trend.change > 0
    || data.score < 90;
}

function buildVoiceGuideMessage(data) {
  const topZone = getMostAffectedZone(data.zones);
  const recommendedActions = (data.recommendations || []).slice(0, 2).join(" Then ");
  const actionLine = recommendedActions || "Focus on a gentle routine, hydration, and consistent skin monitoring.";

  return `I detected some inconvenience after your photo scan. Your skin analysis shows ${data.acne.count} active spots with ${data.acne.severity.toLowerCase()} severity, mainly around ${topZone}. ${actionLine}`;
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
  const analyzeForm = byId("analyze-form");
  const imageInput = byId("image-input");
  const analyzeButton = byId("analyze-button");
  const analyzeStatus = byId("analyze-status");
  const uploadCaption = byId("upload-caption");
  const zonesList = byId("zones-list");
  const insightsList = byId("insights-list");
  const correlationsList = byId("correlations-list");
  const recommendationsList = byId("recommendations-list");

  function renderAnalysis(data) {
    byId("result-image").src = data.image_url;
    byId("processed-image").src = data.processed_image_url;
    byId("score-value").textContent = data.score;
    byId("summary-value").textContent = data.summary;
    byId("confidence-value").textContent = `${data.confidence}%`;
    byId("acne-count-value").textContent = data.acne.count;
    byId("severity-value").textContent = data.acne.severity;
    byId("pigmentation-coverage-value").textContent = `${data.pigmentation.coverage}% ${data.pigmentation.intensity}`;
    byId("boxes-count-value").textContent = data.acne.boxes.length;
    byId("previous-acne-count-value").textContent = data.trend.previous_acne_count;
    byId("current-acne-count-value").textContent = data.acne.count;
    byId("trend-change-value").textContent = formatTrendChange(data.trend.change);
    byId("trend-status-value").textContent = data.trend.status;
    byId("prediction-value").textContent = data.prediction;
    byId("analysis-date-value").textContent = new Date(data.analysis_date).toLocaleString();

    renderZones(zonesList, data.zones);
    renderList(insightsList, data.insights, "Insights will appear after analysis.");
    renderList(correlationsList, data.correlations, "Correlations will appear after more logs.");
    renderList(recommendationsList, data.recommendations, "Recommendations will appear after analysis.");
  }

  renderUserProfile();
  updateVoiceGuideState(voiceGuideButton, false);
  renderZones(zonesList);
  renderList(insightsList, [], "Insights will appear after analysis.");
  renderList(correlationsList, [], "Correlations will appear after more logs.");
  renderList(recommendationsList, [], "Recommendations will appear after analysis.");

  imageInput?.addEventListener("change", () => {
    const [file] = imageInput.files;
    if (!file) {
      byId("preview-wrapper")?.classList.add("hidden");
      uploadCaption.textContent = "Use even lighting and keep your face centered.";
      updateVoiceGuideState(voiceGuideButton, false);
      setMessage(analyzeStatus, "");
      return;
    }

    uploadCaption.textContent = `Selected: ${file.name}`;
    updateVoiceGuideState(voiceGuideButton, false);
    showPreview(file);
    setMessage(analyzeStatus, "");
  });

  analyzeForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const [file] = imageInput.files;
    if (!file) {
      setMessage(analyzeStatus, "Please choose an image first.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setButtonLoading(analyzeButton, true, "Analyzing...");
    setMessage(analyzeStatus, "Analyzing skin and generating intelligence...", "info");

    try {
      const data = await apiFetch("/analyze", { method: "POST", body: formData });
      renderAnalysis(data);

      if (hasDetectedInconvenience(data)) {
        const voiceMessage = buildVoiceGuideMessage(data);
        updateVoiceGuideState(voiceGuideButton, true, voiceMessage);
        speakGuide(voiceMessage);
        setMessage(analyzeStatus, "Analysis complete. Voice guide activated because a concern was detected.", "success");
      } else {
        updateVoiceGuideState(voiceGuideButton, false);
        setMessage(analyzeStatus, "Analysis complete. No inconvenience detected, so voice guide stayed off.", "success");
      }
    } catch (error) {
      setMessage(analyzeStatus, error.message || "Analysis failed.", "error");
    } finally {
      setButtonLoading(analyzeButton, false, "Analyzing...");
    }
  });

  bindLogout(logoutButton);
  voiceGuideButton?.addEventListener("click", speakGuide);
}

async function initDashboardPage() {
  const user = await fetchCurrentUser();
  if (!user) {
    redirectTo("/login");
    return;
  }

  appState.user = user;
  bindDashboardEvents();
  maybeInitOnboardingQuiz();
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
    appState.logs = await fetchHealthLogs();
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

  if (page === "health-logs") {
    await initHealthLogsPage();
  }
}

bootstrap();
























