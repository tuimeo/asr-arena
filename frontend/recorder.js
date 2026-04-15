// Audio recording and IndexedDB storage

const DB_NAME = "asr_compare_db";
const STORE_NAME = "recordings";
const DB_VERSION = 3;
let db = null;
let mediaRecorder = null;
let audioChunks = [];
let recordingStartTime = null;
let timerInterval = null;
let currentAudioBlob = null;
let currentAudioName = "";

// IndexedDB helpers
function openDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
            }
        };
        request.onsuccess = (e) => resolve(e.target.result);
        request.onerror = (e) => reject(e.target.error);
    });
}

async function initDB() {
    db = await openDB();
    refreshHistory();
}

// Record structure:
// { id, name, blob, timestamp, referenceText, engines: [...], results: {engine_id: {text, duration_ms, cer, error}} }

async function createRecord(blob, name, engines, results, referenceText) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        const record = {
            name: name,
            blob: blob,
            timestamp: Date.now(),
            referenceText: referenceText || "",
            engines: engines || [],
            results: results || {},
        };
        const req = store.add(record);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function updateRecord(id, updates) {
    const rec = await getRecording(id);
    if (!rec) return;
    Object.assign(rec, updates);
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        const req = store.put(rec);
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
    });
}

async function getAllRecordings() {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readonly");
        const store = tx.objectStore(STORE_NAME);
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function deleteRecording(id) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        const req = store.delete(id);
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
    });
}

async function getRecording(id) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readonly");
        const store = tx.objectStore(STORE_NAME);
        const req = store.get(id);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

// Recording controls
async function toggleRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        stopRecording();
    } else {
        await startRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: "audio/webm;codecs=opus",
        });

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach((t) => t.stop());
            const blob = new Blob(audioChunks, { type: "audio/webm" });
            const name = `录音 ${formatTime(new Date())}`;
            setCurrentAudio(blob, name);
            clearTimer();
        };

        mediaRecorder.start(250);
        recordingStartTime = Date.now();
        startTimer();

        const btn = document.getElementById("record-btn");
        btn.classList.add("recording");
        btn.innerHTML = '<span class="record-dot"></span> 停止录音';
    } catch (err) {
        alert("无法访问麦克风：" + err.message);
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        const btn = document.getElementById("record-btn");
        btn.classList.remove("recording");
        btn.innerHTML = '<span class="record-dot"></span> 开始录音';
    }
}

function startTimer() {
    const timerEl = document.getElementById("record-timer");
    timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
        const mins = Math.floor(elapsed / 60);
        const secs = elapsed % 60;
        timerEl.textContent = `${mins}:${String(secs).padStart(2, "0")}`;
        if (elapsed >= 60) {
            stopRecording();
        }
    }, 200);
}

function clearTimer() {
    clearInterval(timerInterval);
    document.getElementById("record-timer").textContent = "";
}

// File upload
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    setCurrentAudio(file, file.name);
    event.target.value = "";
}

// Current audio management
function setCurrentAudio(blob, name) {
    currentAudioBlob = blob;
    currentAudioName = name;

    const section = document.getElementById("current-audio");
    section.style.display = "flex";
    document.getElementById("current-audio-name").textContent = name;

    const player = document.getElementById("current-audio-player");
    player.src = URL.createObjectURL(blob);

    document.getElementById("recognize-btn").disabled = false;
}

// Use audio from a history record as current input
async function useAudioFromRecord(id) {
    const rec = await getRecording(id);
    if (rec) {
        setCurrentAudio(rec.blob, rec.name + " (重跑)");
    }
}

// History display
async function refreshHistory() {
    const recordings = await getAllRecordings();
    const section = document.getElementById("history-section");
    const list = document.getElementById("history-list");

    if (recordings.length === 0) {
        section.style.display = "none";
        return;
    }

    section.style.display = "block";
    list.innerHTML = "";

    recordings.reverse().forEach((rec) => {
        const item = document.createElement("div");
        item.className = "history-record";

        const engineCount = rec.engines ? rec.engines.length : 0;
        const hasResults = rec.results && Object.keys(rec.results).length > 0;
        const hasRef = rec.referenceText ? true : false;

        item.innerHTML = `
            <div class="record-header" onclick="toggleRecordDetail(${rec.id})">
                <span class="record-name" id="rname-${rec.id}">${escapeHtml(rec.name)}</span>
                <span class="record-meta">
                    ${engineCount > 0 ? `<span class="badge">${engineCount} 引擎</span>` : ""}
                    ${hasRef ? '<span class="badge badge-ref">有参考</span>' : ""}
                </span>
                <span class="record-time">${formatTime(new Date(rec.timestamp))}</span>
                <span class="record-expand" id="expand-${rec.id}">▶</span>
            </div>
            <div class="record-detail" id="detail-${rec.id}" style="display:none;">
                <div class="record-actions">
                    <button class="btn btn-secondary" onclick="event.stopPropagation(); renameRecord(${rec.id})">重命名</button>
                    <button class="btn btn-secondary" onclick="event.stopPropagation(); playRecord(${rec.id})">播放</button>
                    <button class="btn btn-secondary" onclick="event.stopPropagation(); useAudioFromRecord(${rec.id})">使用此音频</button>
                    <button class="btn btn-danger" onclick="event.stopPropagation(); removeRecord(${rec.id})">删除</button>
                </div>
                <div class="record-ref">
                    <label>参考文本：</label>
                    <textarea id="ref-${rec.id}" rows="2" placeholder="输入参考文本以计算 CER..."
                        oninput="onRefTextChange(${rec.id})">${escapeHtml(rec.referenceText || "")}</textarea>
                </div>
                <div class="record-results" id="results-${rec.id}"></div>
            </div>
        `;
        list.appendChild(item);

        // Render results if present
        if (hasResults) {
            renderRecordResults(rec.id, rec.results);
        }
    });
}

function toggleRecordDetail(id) {
    const detail = document.getElementById(`detail-${id}`);
    const expand = document.getElementById(`expand-${id}`);
    if (detail.style.display === "none") {
        detail.style.display = "block";
        expand.textContent = "▼";
    } else {
        detail.style.display = "none";
        expand.textContent = "▶";
    }
}

function renderRecordResults(id, results) {
    const container = document.getElementById(`results-${id}`);
    if (!container) return;
    container.innerHTML = "";

    ALL_ENGINES.forEach((engine) => {
        const result = results[engine.id];
        if (!result) return;

        const card = document.createElement("div");
        card.className = "result-card mini";
        card.id = `rec-${id}-card-${engine.id}`;

        if (result.error) {
            card.classList.add("error");
            card.innerHTML = `
                <div class="engine-name"><a href="${engine.url || '#'}" target="_blank" rel="noopener" title="${engine.model || ''}">${engine.name}</a></div>
                <div class="result-text error-text">${escapeHtml(result.error)}</div>
                <div class="result-meta"></div>
            `;
        } else {
            card.classList.add("success");
            card.innerHTML = `
                <div class="engine-name"><a href="${engine.url || '#'}" target="_blank" rel="noopener" title="${engine.model || ''}">${engine.name}</a></div>
                <div class="result-text">${escapeHtml(result.text || "(空结果)")}</div>
                <div class="result-meta">${buildResultMetaHtml(result)}</div>
            `;
        }
        container.appendChild(card);
    });
}

// Reference text changed on a record — recalc CER
let refTimers = {};
function onRefTextChange(id) {
    clearTimeout(refTimers[id]);
    refTimers[id] = setTimeout(() => recalcRecordCER(id), 500);
}

async function recalcRecordCER(id) {
    const rec = await getRecording(id);
    if (!rec) return;

    const refText = document.getElementById(`ref-${id}`).value.trim();
    await updateRecord(id, { referenceText: refText });

    if (!refText || !rec.results) return;

    const hypotheses = {};
    for (const [engineId, result] of Object.entries(rec.results)) {
        if (result.text) hypotheses[engineId] = result.text;
    }
    if (Object.keys(hypotheses).length === 0) return;

    try {
        const resp = await fetch("/api/cer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reference_text: refText, hypotheses }),
        });
        if (!resp.ok) return;
        const data = await resp.json();

        // Update results with new CER
        for (const [engineId, cer] of Object.entries(data.cer || {})) {
            if (rec.results[engineId]) {
                rec.results[engineId].cer = cer;
            }
        }
        await updateRecord(id, { results: rec.results });
        renderRecordResults(id, rec.results);
    } catch (e) { /* silent */ }
}

async function renameRecord(id) {
    const rec = await getRecording(id);
    if (!rec) return;
    const newName = prompt("输入名称/备注：", rec.name);
    if (newName !== null && newName.trim() !== "") {
        await updateRecord(id, { name: newName.trim() });
        refreshHistory();
    }
}

async function playRecord(id) {
    const rec = await getRecording(id);
    if (rec) {
        const url = URL.createObjectURL(rec.blob);
        const audio = new Audio(url);
        audio.addEventListener("ended", () => URL.revokeObjectURL(url));
        audio.play();
    }
}

async function removeRecord(id) {
    if (!confirm("确定删除此记录？")) return;
    await deleteRecording(id);
    refreshHistory();
}

// Helpers
function formatTime(date) {
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    const h = String(date.getHours()).padStart(2, "0");
    const min = String(date.getMinutes()).padStart(2, "0");
    const s = String(date.getSeconds()).padStart(2, "0");
    return `${m}-${d} ${h}:${min}:${s}`;
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// Init
document.addEventListener("DOMContentLoaded", initDB);
