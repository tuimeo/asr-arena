// Main application logic

const ALL_ENGINES = [
    {
        id: "ali_paraformer", name: "阿里云 Paraformer-v2", provider: "ali",
        model: "paraformer-realtime-v2",
        desc: "阿里达摩院非自回归语音识别模型，通过 DashScope Recognition WebSocket 流式调用。支持中文(含方言)、英、日、韩等语言。",
        url: "https://help.aliyun.com/zh/model-studio/real-time-speech-recognition",
    },
    {
        id: "ali_funasr", name: "阿里云 Fun-ASR", provider: "ali",
        model: "fun-asr-realtime",
        desc: "阿里通义实验室端到端语音识别大模型，通过 DashScope Recognition WebSocket 流式调用。支持中英日、18种方言、热词自定义。",
        url: "https://help.aliyun.com/zh/model-studio/real-time-speech-recognition",
    },
    {
        id: "ali_qwen3asr", name: "阿里云 Qwen3-ASR", provider: "ali",
        model: "qwen3-asr-flash",
        desc: "基于千问大语言模型的语音识别，通过 MultiModalConversation API 同步调用（传完整音频，非流式）。支持 27+ 语言。",
        url: "https://help.aliyun.com/zh/model-studio/qwen-speech-recognition",
    },
    {
        id: "ali_qwen3asr_realtime", name: "阿里云 Qwen3-ASR-RT", provider: "ali",
        model: "qwen3-asr-flash-realtime",
        desc: "Qwen3-ASR 的实时流式版本，通过 OmniRealtimeConversation WebSocket 调用。音频流式发送，边说边出结果。",
        url: "https://help.aliyun.com/zh/model-studio/qwen-real-time-speech-recognition",
    },
    {
        id: "baidu_standard", name: "百度 标准版", provider: "baidu",
        model: "短语音识别标准版 (dev_pid=1537)",
        desc: "百度短语音识别标准版，REST API 同步调用，传完整音频(≤60s)返回结果。支持普通话、粤语、四川话、英语。",
        url: "https://ai.baidu.com/tech/speech/asr",
    },
    {
        id: "baidu_pro", name: "百度 极速版", provider: "baidu",
        model: "短语音识别极速版 (dev_pid=80001)",
        desc: "百度短语音识别极速版 (SMLTA 模型)，REST API 同步调用。官方称比标准版精度高约 15%，仅支持普通话。",
        url: "https://ai.baidu.com/tech/speech/asr",
    },
    {
        id: "xunfei_iat", name: "讯飞 语音听写", provider: "xunfei",
        model: "语音听写 (domain=iat)",
        desc: "科大讯飞传统语音听写接口，WebSocket 流式调用。支持23种方言，是讯飞的基础款语音识别。",
        url: "https://www.xfyun.cn/doc/asr/voicedictation/API.html",
    },
    {
        id: "xunfei_spark", name: "讯飞 星火大模型", provider: "xunfei",
        model: "星火中英识别大模型 (domain=slm)",
        desc: "基于星火大模型训练的语音识别，WebSocket 流式调用。支持 202 种方言自动识别、37 种语言。讯飞较新的语音识别产品。",
        url: "https://www.xfyun.cn/doc/spark/spark_zh_iat.html",
    },
    {
        id: "tencent_sentence", name: "腾讯云 一句话识别", provider: "tencent",
        model: "SentenceRecognition (16k_zh)",
        desc: "腾讯云一句话识别，REST API 同步调用，传完整音频(≤60s)返回结果。通过官方 SDK 调用。",
        url: "https://cloud.tencent.com/document/product/1093/37308",
    },
    {
        id: "tencent_flash", name: "腾讯云 极速版", provider: "tencent",
        model: "录音文件识别极速版 (16k_zh)",
        desc: "腾讯云极速版，HTTP 同步调用，支持≤5分钟音频。比一句话识别支持更长音频，引擎类型 16k_zh（标准中文模型）。",
        url: "https://cloud.tencent.com/document/product/1093/52097",
    },
    {
        id: "tencent_flash_large", name: "腾讯云 极速版(大模型)", provider: "tencent",
        model: "录音文件识别极速版 (16k_zh_large)",
        desc: "腾讯云极速版大模型引擎，引擎类型 16k_zh_large。相比标准引擎有更好的准确率、标点和数字格式化能力。",
        url: "https://cloud.tencent.com/document/product/1093/52097",
    },
    {
        id: "volcengine_seedasr", name: "火山 ASR 1.0 双向流式", provider: "volcengine",
        model: "豆包流式语音识别 1.0 (bigmodel)",
        desc: "火山引擎(字节跳动) ASR 1.0，WebSocket 二进制协议双向流式。每发一包音频就返回当前识别结果，延迟低。",
        url: "https://www.volcengine.com/docs/6561/1354869",
    },
    {
        id: "volcengine_seedasr_nostream", name: "火山 ASR 1.0 流式输入", provider: "volcengine",
        model: "豆包流式语音识别 1.0 (bigmodel_nostream)",
        desc: "火山引擎 ASR 1.0 流式输入模式。音频流式发送，但结果在发送完毕后一次性返回，准确率高于双向流式。",
        url: "https://www.volcengine.com/docs/6561/1354869",
    },
    {
        id: "volcengine_seedasr2", name: "火山 ASR 2.0 双向流式", provider: "volcengine",
        model: "豆包流式语音识别 2.0 / Seed-ASR (bigmodel_async)",
        desc: "火山引擎 ASR 2.0 (Seed-ASR) 优化版双向流式。结果有变化时才返回（非每包都返回）。2B 参数音频编码器 + MoE 大模型架构。",
        url: "https://www.volcengine.com/docs/6561/1354869",
    },
    {
        id: "volcengine_seedasr2_nostream", name: "火山 ASR 2.0 流式输入", provider: "volcengine",
        model: "豆包流式语音识别 2.0 / Seed-ASR (bigmodel_nostream)",
        desc: "火山引擎 ASR 2.0 流式输入模式。音频流式发送，结果在发送完毕后一次性返回。官方数据：平均 5s 音频约 300-400ms 返回。",
        url: "https://www.volcengine.com/docs/6561/1354869",
    },
];

// Build engine selection checkboxes
function buildEngineCheckboxes() {
    const container = document.getElementById("engine-checkboxes");
    if (!container) return;
    container.innerHTML = "";

    const configured = getConfiguredEngines();

    ALL_ENGINES.forEach((engine) => {
        const isConfigured = configured.includes(engine.id);
        const label = document.createElement("label");
        label.className = "engine-checkbox" + (isConfigured ? "" : " disabled");
        if (!isConfigured) label.title = "未配置 API 密钥";
        label.innerHTML = `
            <input type="checkbox" value="${engine.id}"
                ${isConfigured ? "checked" : "disabled"}>
            <span>${engine.name}</span>
            <span class="engine-info-icon" data-engine-id="${engine.id}">ℹ</span>
        `;
        // Prevent info icon click from toggling checkbox
        label.querySelector(".engine-info-icon").addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
        container.appendChild(label);
    });

    // Setup hover popups for info icons
    setupEngineInfoPopups();
}

function getSelectedEngines() {
    const checkboxes = document.querySelectorAll("#engine-checkboxes input[type=checkbox]:checked");
    return Array.from(checkboxes).map((cb) => cb.value);
}

// Engine info popup
function setupEngineInfoPopups() {
    let popup = document.getElementById("engine-info-popup");
    if (!popup) {
        popup = document.createElement("div");
        popup.id = "engine-info-popup";
        popup.className = "engine-info-popup";
        popup.style.display = "none";
        document.body.appendChild(popup);
    }

    document.querySelectorAll(".engine-info-icon").forEach((icon) => {
        icon.addEventListener("mouseenter", (e) => {
            const engineId = icon.dataset.engineId;
            const engine = ALL_ENGINES.find((eng) => eng.id === engineId);
            if (!engine) return;

            popup.innerHTML = `
                <div class="popup-title">${engine.name}</div>
                <div class="popup-model">模型: ${engine.model}</div>
                <div class="popup-desc">${engine.desc}</div>
                <a class="popup-link" href="${engine.url}" target="_blank" rel="noopener">查看官方文档 →</a>
            `;
            popup.style.display = "block";

            // Position near the icon
            const rect = icon.getBoundingClientRect();
            popup.style.top = (rect.bottom + window.scrollY + 6) + "px";
            popup.style.left = Math.max(8, Math.min(rect.left + window.scrollX - 100, window.innerWidth - 340)) + "px";
        });

        icon.addEventListener("mouseleave", () => {
            // Delay hide so user can move mouse to popup
            setTimeout(() => {
                if (!popup.matches(":hover")) {
                    popup.style.display = "none";
                }
            }, 200);
        });
    });

    popup.addEventListener("mouseleave", () => {
        popup.style.display = "none";
    });
}

function toggleAllEngines(checked) {
    document.querySelectorAll("#engine-checkboxes input[type=checkbox]:not(:disabled)").forEach((cb) => {
        cb.checked = checked;
    });
}

async function startRecognize() {
    if (!currentAudioBlob) {
        alert("请先录音或上传音频文件");
        return;
    }

    const selectedEngines = getSelectedEngines();
    if (selectedEngines.length === 0) {
        alert("请至少勾选一个引擎");
        return;
    }

    const encryptedKeys = loadEncryptedKeys();
    if (!encryptedKeys) {
        alert("请先保存 API 密钥");
        return;
    }
    const referenceText = document.getElementById("reference-text").value.trim();

    // Show live results area
    const liveSection = document.getElementById("live-results-section");
    liveSection.style.display = "block";
    const grid = document.getElementById("live-results-grid");
    grid.innerHTML = "";

    // Create cards for selected engines
    selectedEngines.forEach((engineId) => {
        const engine = ALL_ENGINES.find((e) => e.id === engineId);
        if (!engine) return;
        const card = document.createElement("div");
        card.className = "result-card loading";
        card.id = `live-card-${engine.id}`;
        card.innerHTML = `
            <div class="engine-name"><a href="${engine.url}" target="_blank" rel="noopener" title="${engine.model}">${engine.name}</a></div>
            <div class="result-text loading-text"><span class="spinner"></span>识别中...</div>
            <div class="result-meta"></div>
        `;
        grid.appendChild(card);
    });

    // Disable button
    const btn = document.getElementById("recognize-btn");
    btn.disabled = true;
    btn.textContent = "识别中...";

    // Build form data
    const formData = new FormData();
    formData.append("audio", currentAudioBlob, "audio.webm");
    formData.append("config", JSON.stringify({
        engines: selectedEngines,
        encrypted_keys: encryptedKeys,
        reference_text: referenceText,
    }));

    let results = {};
    let completedCount = 0;

    try {
        const resp = await fetch("/api/recognize", {
            method: "POST",
            body: formData,
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: "请求失败" }));
            alert(err.error || `HTTP ${resp.status}`);
            btn.disabled = false;
            btn.textContent = "开始识别";
            return;
        }

        // Read SSE stream
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse SSE events from buffer
            const lines = buffer.split("\n");
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.slice(6);
                try {
                    const event = JSON.parse(jsonStr);
                    if (event.done) continue;

                    const { engine_id, result } = event;
                    results[engine_id] = result;
                    updateLiveCard(engine_id, result);
                    completedCount++;
                    btn.textContent = `识别中... (${completedCount}/${selectedEngines.length})`;
                } catch (e) { /* skip bad lines */ }
            }
        }

        // Save as a new record
        const recordName = currentAudioName + ` (${selectedEngines.length}引擎)`;
        await createRecord(currentAudioBlob, recordName, selectedEngines, results, referenceText);
        refreshHistory();

    } catch (err) {
        alert("网络错误，请检查后端是否运行：" + err.message);
    }

    btn.disabled = false;
    btn.textContent = "开始识别";
}

function updateLiveCard(engineId, result) {
    const card = document.getElementById(`live-card-${engineId}`);
    if (!card) return;

    card.classList.remove("loading");

    const textEl = card.querySelector(".result-text");
    const metaEl = card.querySelector(".result-meta");

    if (result.error) {
        card.classList.add("error");
        textEl.className = "result-text error-text";
        textEl.textContent = result.error;
    } else {
        card.classList.add("success");
        textEl.className = "result-text";
        textEl.textContent = result.text || "(空结果)";
    }

    metaEl.innerHTML = buildResultMetaHtml(result);
}

// Shared: build meta HTML (duration + CER) for a result
function buildResultMetaHtml(result) {
    let html = "";
    if (result.duration_ms != null) {
        html += `<span>耗时: ${(result.duration_ms / 1000).toFixed(1)}s</span>`;
    }
    if (result.cer != null) {
        const cerPercent = (result.cer * 100).toFixed(1);
        let cerClass = result.cer > 0.1 ? "cer-bad" : (result.cer > 0.05 ? "cer-ok" : "cer-good");
        html += `<span class="cer-value ${cerClass}">CER: ${cerPercent}%</span>`;
    }
    return html;
}

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    setTimeout(buildEngineCheckboxes, 100);
});
