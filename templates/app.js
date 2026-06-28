const API = "http://localhost:8000";

let suggestionsLoaded = false;
let suggestionsRequestRunning = false;
let currentSuggestions = [];
let currentJobId = null;
let jobPollTimer = null;

const session = {
    user: localStorage.getItem("askpolicy_user") || "default",
    token: localStorage.getItem("askpolicy_token") || ""
};

window.onload = () => {
    updateSessionUi();
    loadDocs();
    loadCacheStats();
    loadSuggestions();
    pollLatestJob();
};


function authHeaders(extra = {}) {
    return {
        ...extra,
        "X-AskPolicy-User": session.user,
        "X-AskPolicy-Token": session.token
    };
}


// ---------------------------------------------------------
// Login
// ---------------------------------------------------------

async function login() {
    const userInput = document.getElementById("loginUser");
    const passInput = document.getElementById("loginPass");
    const msg = document.getElementById("loginMsg");

    const username = userInput.value.trim();
    const password = passInput.value;

    if (!username || !password) {
        msg.textContent = "Enter username and password.";
        return;
    }

    try {
        const res = await fetch(`${API}/login`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({username, password})
        });

        if (!res.ok) {
            throw new Error("Invalid login");
        }

        const data = await res.json();
        session.user = data.user;
        session.token = data.token;
        localStorage.setItem("askpolicy_user", session.user);
        localStorage.setItem("askpolicy_token", session.token);

        passInput.value = "";
        msg.textContent = "";
        suggestionsLoaded = false;
        currentSuggestions = [];

        updateSessionUi();
        await loadDocs();
        await loadCacheStats();
        await loadSuggestions(true);
        sysMsg(`Signed in as ${session.user}`);

    } catch (err) {
        msg.textContent = "Login failed.";
    }
}

function logout() {
    session.user = "default";
    session.token = "";
    localStorage.removeItem("askpolicy_user");
    localStorage.removeItem("askpolicy_token");
    suggestionsLoaded = false;
    currentSuggestions = [];
    updateSessionUi();
    loadDocs();
    loadSuggestions(true);
    sysMsg("Signed out.");
}

function updateSessionUi() {
    document.getElementById("activeUser").textContent = session.user;
    document.getElementById("loginUser").value =
        session.user === "default" ? "" : session.user;
}


// ---------------------------------------------------------
// Upload Handling
// ---------------------------------------------------------

function onDragOver(e) {
    e.preventDefault();
    document.getElementById("dropZone").classList.add("dragover");
}

function onDragLeave() {
    document.getElementById("dropZone").classList.remove("dragover");
}

function onDrop(e) {
    e.preventDefault();
    onDragLeave();

    if (e.dataTransfer.files.length > 0) {
        uploadFile(e.dataTransfer.files[0]);
    }
}

function onFileSelect(e) {
    if (e.target.files.length > 0) {
        uploadFile(e.target.files[0]);
    }
}

async function uploadFile(file) {
    if (!file) return;

    setProcessingState(`Uploading ${file.name}...`);

    try {
        const fd = new FormData();
        fd.append("file", file);

        const res = await fetch(`${API}/upload`, {
            method: "POST",
            headers: authHeaders(),
            body: fd
        });

        const data = await res.json();

        if (data.success) {
            suggestionsLoaded = false;
            currentSuggestions = [];
            currentJobId = data.job_id;
            showUploadMessage(data.message, true);
            pollJob(data.job_id);
            await loadDocs();
        } else {
            finishProcessingState();
            showUploadMessage(data.message, false);
        }

    } catch (err) {
        finishProcessingState();
        showUploadMessage("Upload failed: " + err.message, false);
    }

    document.getElementById("fileInput").value = "";
}

function setProcessingState(label) {
    const prog = document.getElementById("progressWrap");
    const lbl = document.getElementById("progressLabel");
    prog.style.display = "block";
    lbl.textContent = label;
}

function finishProcessingState() {
    document.getElementById("progressWrap").style.display = "none";
}

function showUploadMessage(text, ok) {
    const msg = document.getElementById("uploadMsg");
    msg.style.display = "block";
    msg.className = ok ? "upload-msg ok" : "upload-msg err";
    msg.textContent = text;

    setTimeout(() => {
        msg.style.display = "none";
    }, 6000);
}


// ---------------------------------------------------------
// Job Polling
// ---------------------------------------------------------

async function pollLatestJob() {
    try {
        const res = await fetch(`${API}/jobs/latest`, {
            headers: authHeaders()
        });

        if (!res.ok) return;

        const data = await res.json();

        if (data.job && ["queued", "running"].includes(data.job.status)) {
            currentJobId = data.job.id;
            pollJob(data.job.id);
        }
    } catch (err) {
        console.error("Job status error:", err);
    }
}

async function pollJob(jobId) {
    if (!jobId) return;

    if (jobPollTimer) {
        clearTimeout(jobPollTimer);
    }

    try {
        const res = await fetch(`${API}/jobs/${jobId}`, {
            headers: authHeaders()
        });

        if (!res.ok) {
            finishProcessingState();
            return;
        }

        const job = await res.json();
        setProcessingState(`${job.kind}: ${job.step}`);

        if (job.status === "complete") {
            finishProcessingState();
            showUploadMessage(job.message || "Processing complete.", true);
            currentJobId = null;
            suggestionsLoaded = false;
            currentSuggestions = [];
            await loadDocs();
            await loadCacheStats();
            await loadSuggestions(true);
            return;
        }

        if (job.status === "failed") {
            finishProcessingState();
            showUploadMessage(job.message || "Processing failed.", false);
            currentJobId = null;
            return;
        }

        jobPollTimer = setTimeout(() => pollJob(jobId), 1500);

    } catch (err) {
        console.error("Job poll error:", err);
        jobPollTimer = setTimeout(() => pollJob(jobId), 2500);
    }
}


// ---------------------------------------------------------
// Suggestions
// ---------------------------------------------------------

async function loadSuggestions(forceRefresh = false) {
    const container = document.getElementById("suggestionsBox");

    if (!container || suggestionsRequestRunning) return;
    if (suggestionsLoaded && !forceRefresh) return;

    suggestionsRequestRunning = true;
    container.innerHTML = `<div class="suggestion-loading">Generating suggestions from your documents...</div>`;

    let timeoutId = null;

    try {
        const controller = new AbortController();
        timeoutId = setTimeout(() => controller.abort(), 180000);

        const res = await fetch(`${API}/suggestions`, {
            headers: authHeaders(),
            signal: controller.signal
        });

        if (!res.ok) {
            throw new Error("Could not load suggestions");
        }

        const data = await res.json();
        currentSuggestions = Array.isArray(data.suggestions)
            ? data.suggestions
            : [];

        renderSuggestions(currentSuggestions);
        suggestionsLoaded = true;

    } catch (err) {
        console.error("Suggestions error:", err);
        container.innerHTML = `<div class="suggestion-loading">No suggestions available right now.</div>`;
        suggestionsLoaded = false;

    } finally {
        if (timeoutId) clearTimeout(timeoutId);
        suggestionsRequestRunning = false;
    }
}

function renderSuggestions(suggestions) {
    const container = document.getElementById("suggestionsBox");
    if (!container) return;

    container.innerHTML = "";

    if (!suggestions || suggestions.length === 0) {
        container.innerHTML = `<div class="suggestion-loading">No document-based suggestions are available yet.</div>`;
        return;
    }

    suggestions.forEach((question) => {
        const button = document.createElement("button");
        button.className = "suggestion-chip";
        button.textContent = question;
        button.addEventListener("click", () => ask(question));
        container.appendChild(button);
    });
}


// ---------------------------------------------------------
// Documents
// ---------------------------------------------------------

async function loadDocs() {
    try {
        const res = await fetch(`${API}/documents`, {
            headers: authHeaders()
        });

        if (!res.ok) {
            throw new Error("Could not load documents");
        }

        const data = await res.json();
        const docs = data.documents || [];

        document.getElementById("docCount").textContent = docs.length;

        const list = document.getElementById("docList");

        if (!docs.length) {
            list.innerHTML = `<div class="no-docs">No documents yet</div>`;
            return;
        }

        list.innerHTML = "";

        docs.forEach((doc) => {
            const item = document.createElement("div");
            item.className = "doc-item";

            const left = document.createElement("div");
            left.className = "doc-left";

            const icon = document.createElement("span");
            icon.className = "doc-icon";
            icon.textContent = fileIcon(doc.name);

            const info = document.createElement("div");

            const name = document.createElement("div");
            name.className = "doc-name";
            name.title = doc.name;
            name.textContent = doc.name;

            const size = document.createElement("div");
            size.className = "doc-size";
            size.textContent = `${doc.size_kb} KB`;

            info.appendChild(name);
            info.appendChild(size);
            left.appendChild(icon);
            left.appendChild(info);

            const deleteButton = document.createElement("button");
            deleteButton.className = "del-btn";
            deleteButton.textContent = "Delete";
            deleteButton.addEventListener("click", () => deleteDoc(doc.name));

            item.appendChild(left);
            item.appendChild(deleteButton);
            list.appendChild(item);
        });

    } catch (err) {
        console.error("Could not load documents:", err);
    }
}

function fileIcon(name) {
    const ext = name.split(".").pop().toLowerCase();

    return {
        pdf: "PDF",
        docx: "DOC",
        xlsx: "XLS",
        xls: "XLS",
        csv: "CSV",
        html: "WEB",
        htm: "WEB",
        txt: "TXT",
        md: "MD"
    }[ext] || "DOC";
}

async function deleteDoc(name) {
    if (!confirm(`Delete ${name}?`)) return;

    setProcessingState(`Deleting ${name}...`);

    try {
        const res = await fetch(
            `${API}/documents/${encodeURIComponent(name)}`,
            {
                method: "DELETE",
                headers: authHeaders()
            }
        );

        if (!res.ok) {
            throw new Error("Could not delete document");
        }

        const data = await res.json();
        suggestionsLoaded = false;
        currentSuggestions = [];
        await loadDocs();

        if (data.job_id) {
            pollJob(data.job_id);
        } else {
            finishProcessingState();
            await loadSuggestions(true);
        }

        sysMsg(`${name} deleted`);

    } catch (err) {
        console.error("Delete failed:", err);
        finishProcessingState();
        sysMsg("Could not delete document");
    }
}


// ---------------------------------------------------------
// Redis Cache
// ---------------------------------------------------------

async function loadCacheStats() {
    try {
        const res = await fetch(`${API}/cache/stats`);

        if (!res.ok) {
            throw new Error("Could not load cache statistics");
        }

        const data = await res.json();
        const ok = data.status === "connected";
        const el = document.getElementById("cacheStatus");

        el.textContent = ok ? "Connected" : "Offline";
        el.className = "stat-val " + (ok ? "on" : "off");

        document.getElementById("cachedCount").textContent =
            data.cached_answers ?? "-";

        document.getElementById("cacheTTL").textContent =
            data.ttl_seconds ? `${data.ttl_seconds / 60} min` : "-";

    } catch (err) {
        console.error("Cache stats error:", err);
    }
}

async function clearCache() {
    try {
        const res = await fetch(`${API}/cache/clear`, {
            method: "DELETE"
        });

        if (!res.ok) {
            throw new Error("Could not clear cache");
        }

        suggestionsLoaded = false;
        currentSuggestions = [];
        await loadCacheStats();
        await loadSuggestions(true);
        sysMsg("Cache cleared");

    } catch (err) {
        console.error("Cache clear error:", err);
        sysMsg("Could not clear cache");
    }
}


// ---------------------------------------------------------
// Ask Question
// ---------------------------------------------------------

async function ask(question) {
    const input = document.getElementById("qInput");
    const q = question || input.value.trim();

    if (!q) return;

    input.value = "";
    addMsg(q, "user");

    const loadId = addMsg("Searching documents...", "loading");
    const btn = document.getElementById("sendBtn");

    btn.disabled = true;
    btn.textContent = "...";

    try {
        const res = await fetch(`${API}/ask`, {
            method: "POST",
            headers: authHeaders({"Content-Type": "application/json"}),
            body: JSON.stringify({question: q})
        });

        if (!res.ok) {
            throw new Error("Could not get answer");
        }

        const data = await res.json();
        removeMsg(loadId);
        addBotMsg(data.answer, data.followup || null);
        loadCacheStats();

    } catch (err) {
        console.error("Ask error:", err);
        removeMsg(loadId);
        addMsg("Cannot connect. Is the API running?", "bot");

    } finally {
        btn.disabled = false;
        btn.textContent = "Send";
        input.focus();
    }
}


// ---------------------------------------------------------
// Chat Message Helpers
// ---------------------------------------------------------

function addMsg(text, type) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    const id = "m" + Date.now() + Math.random();

    div.id = id;
    div.className = `msg ${type}-msg`;
    div.textContent = text;

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;

    return id;
}

function addBotMsg(answer, followup) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = "msg bot-msg";

    const answerText = document.createElement("span");
    answerText.textContent = answer;
    div.appendChild(answerText);

    if (followup) {
        const fu = document.createElement("div");
        fu.className = "followup-single";

        const button = document.createElement("button");
        button.className = "followup-single-btn";
        button.textContent = followup;
        button.addEventListener("click", () => ask(followup));

        fu.appendChild(button);
        div.appendChild(fu);
    }

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function removeMsg(id) {
    document.getElementById(id)?.remove();
}

function sysMsg(text) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = "system-msg";
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}
