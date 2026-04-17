// API Keys management
// Plaintext keys are NEVER stored. localStorage only holds encrypted ciphertext.

const STORAGE_KEY = "asr_compare_encrypted_keys";

// Provider definitions with their required fields
const PROVIDERS = {
    ali: { fields: ["api_key"] },
    baidu: { fields: ["app_id", "api_key", "secret_key"] },
    xunfei: { fields: ["app_id", "api_key", "api_secret"] },
    tencent: { fields: ["secret_id", "secret_key", "appid"] },
    volcengine: { fields: ["app_id", "access_token"] },
};

// Engine to provider mapping — derived from ALL_ENGINES in app.js
function getEngineProviders() {
    const map = {};
    if (typeof ALL_ENGINES !== "undefined") {
        for (const e of ALL_ENGINES) {
            map[e.id] = e.provider;
        }
    }
    return map;
}

// Load encrypted keys from localStorage
function loadEncryptedKeys() {
    return localStorage.getItem(STORAGE_KEY) || "";
}

function saveEncryptedKeys(encrypted) {
    localStorage.setItem(STORAGE_KEY, encrypted);
}

// Populate key inputs — inputs start empty (we don't decrypt back to show)
// Show "已配置" badge on providers that have saved keys
function populateKeyInputs() {
    const encrypted = loadEncryptedKeys();
    if (encrypted) {
        document.getElementById("keys-status-hint").textContent = "已有保存的密钥（加密存储）";
    }
    updateProviderBadges();
}

function updateProviderBadges() {
    const configured = getConfiguredProviders();
    document.querySelectorAll("[data-provider-group]").forEach((group) => {
        const provider = group.dataset.providerGroup;
        const badge = group.querySelector(".key-configured-badge");
        if (badge) {
            badge.style.display = configured.includes(provider) ? "inline" : "none";
        }
    });
}

// Collect plaintext keys from input fields
function collectKeysFromInputs() {
    const keys = {};
    document.querySelectorAll("[data-provider][data-field]").forEach((input) => {
        const provider = input.dataset.provider;
        const field = input.dataset.field;
        const value = input.value.trim();
        if (value) {
            if (!keys[provider]) keys[provider] = {};
            keys[provider][field] = value;
        }
    });
    return keys;
}

function validateNewKeys(newKeys) {
    const errors = [];
    for (const [provider, values] of Object.entries(newKeys)) {
        const requiredFields = PROVIDERS[provider]?.fields || [];
        const missing = requiredFields.filter((field) => !values[field]);
        if (missing.length > 0) {
            errors.push(`${provider}: 缺少 ${missing.join(" / ")}`);
        }
    }
    return errors;
}


// Provider list stored alongside encrypted keys (we can't decrypt on frontend)
const PROVIDERS_KEY = "asr_compare_configured_providers";

function getConfiguredProviders() {
    try {
        return JSON.parse(localStorage.getItem(PROVIDERS_KEY) || "[]");
    } catch {
        return [];
    }
}

function getConfiguredEngines() {
    const providers = getConfiguredProviders();
    const engineProviders = getEngineProviders();
    const engines = [];
    for (const [engineId, provider] of Object.entries(engineProviders)) {
        if (providers.includes(provider)) {
            engines.push(engineId);
        }
    }
    return engines;
}

async function saveKeys() {
    const newKeys = collectKeysFromInputs();
    const status = document.getElementById("keys-save-status");

    if (Object.keys(newKeys).length === 0) {
        status.textContent = "未填写任何密钥";
        setTimeout(() => { status.textContent = ""; }, 2000);
        return;
    }

    const validationErrors = validateNewKeys(newKeys);
    if (validationErrors.length > 0) {
        status.textContent = "保存失败: 请补全当前供应商的必填字段";
        alert("以下密钥配置不完整，未保存：\n" + validationErrors.join("\n"));
        return;
    }

    // Merge: send new keys + old ciphertext to backend.
    // Backend decrypts old, merges new on top, re-encrypts.
    const existingEncrypted = loadEncryptedKeys();

    try {
        const resp = await fetch("/api/merge-keys", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                new_keys: newKeys,
                existing_encrypted: existingEncrypted || "",
            }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: "保存失败" }));
            status.textContent = err.error || "保存失败";
            return;
        }

        const data = await resp.json();
        saveEncryptedKeys(data.encrypted);

        // Update configured providers list
        const allProviders = data.providers || [];
        localStorage.setItem(PROVIDERS_KEY, JSON.stringify(allProviders));

        // Clear inputs
        document.querySelectorAll("[data-provider][data-field]").forEach((input) => {
            input.value = "";
        });

        status.textContent = "已加密保存";
        document.getElementById("keys-status-hint").textContent = "已有保存的密钥（加密存储）";
        setTimeout(() => { status.textContent = ""; }, 2000);
        updateProviderBadges();
        if (typeof buildEngineCheckboxes === "function") {
            buildEngineCheckboxes();
        }
    } catch (err) {
        status.textContent = "保存失败: " + err.message;
    }
}

function clearKeys() {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(PROVIDERS_KEY);
    document.querySelectorAll("[data-provider][data-field]").forEach((input) => {
        input.value = "";
    });
    document.getElementById("keys-status-hint").textContent = "";
    document.getElementById("keys-save-status").textContent = "已清除";
    setTimeout(() => { document.getElementById("keys-save-status").textContent = ""; }, 2000);
    updateProviderBadges();
    if (typeof buildEngineCheckboxes === "function") {
        buildEngineCheckboxes();
    }
}

function toggleSection(id) {
    const el = document.getElementById(id);
    el.classList.toggle("collapsed");
    const toggle = document.getElementById("keys-toggle");
    toggle.textContent = el.classList.contains("collapsed") ? "▶" : "▼";
}

// Initialize on load
document.addEventListener("DOMContentLoaded", populateKeyInputs);
