const API = "http://localhost:8000";

let suggestionsLoaded = false;
let suggestionsRequestRunning = false;
let currentSuggestions = [];

window.onload = () => {
    loadDocs();
    loadCacheStats();
    loadSuggestions();
    setInterval(loadCacheStats, 30000);
};


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

    const prog = document.getElementById("progressWrap");
    const msg = document.getElementById("uploadMsg");
    const lbl = document.getElementById("progressLabel");

    prog.style.display = "block";
    msg.style.display = "none";
    lbl.textContent = `Uploading ${file.name}...`;

    try {
        const fd = new FormData();
        fd.append("file", file);

        const res = await fetch(`${API}/upload`, {
            method: "POST",
            body: fd
        });

        const data = await res.json();

        prog.style.display = "none";
        msg.style.display = "block";

        if (data.success) {
            msg.className = "upload-msg ok";
            msg.textContent = data.message;

            // New document means old suggestions should be replaced.
            suggestionsLoaded = false;
            currentSuggestions = [];

            await loadDocs();
            await loadSuggestions(true);
        } else {
            msg.className = "upload-msg err";
            msg.textContent = data.message;
        }

    } catch (err) {
        prog.style.display = "none";
        msg.style.display = "block";
        msg.className = "upload-msg err";
        msg.textContent = "Upload failed: " + err.message;
    }

    document.getElementById("fileInput").value = "";

    setTimeout(() => {
        msg.style.display = "none";
    }, 6000);
}


// ---------------------------------------------------------
// Suggestions
// ---------------------------------------------------------

async function loadSuggestions(forceRefresh = false) {
    const container = document.getElementById("suggestionsBox");

    if (!container) return;

    // Prevent duplicate /suggestions requests.
    if (suggestionsRequestRunning) {
        return;
    }

    // Keep existing suggestion buttons visible.
    if (suggestionsLoaded && !forceRefresh) {
        return;
    }

    suggestionsRequestRunning = true;

    container.innerHTML = `
        <div class="suggestion-loading">
            ⏳ Generating suggestions from your documents...
        </div>
    `;

    try {
        const controller = new AbortController();

        const timeoutId = setTimeout(() => {
            controller.abort();
        }, 180000);

        const res = await fetch(`${API}/suggestions`, {
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        const data = await res.json();

        console.log("Suggestions response:", data);

        currentSuggestions = Array.isArray(data.suggestions)
            ? data.suggestions
            : [];

        renderSuggestions(currentSuggestions);

        suggestionsLoaded = true;

    } catch (err) {
        console.error("Suggestions error:", err);

        container.innerHTML = `
            <div class="suggestion-loading">
                No suggestions available right now.
            </div>
        `;

        suggestionsLoaded = false;

    } finally {
        suggestionsRequestRunning = false;
    }
}

function renderSuggestions(suggestions) {
    const container = document.getElementById("suggestionsBox");

    if (!container) return;

    container.innerHTML = "";

    if (!suggestions || suggestions.length === 0) {
        container.innerHTML = `
            <div class="suggestion-loading">
                No document-based suggestions are available yet.
            </div>
        `;
        return;
    }

    suggestions.forEach((question) => {
        const button = document.createElement("button");

        button.className = "suggestion-chip";
        button.textContent = question;

        // Safe event listener.
        // No inline onclick string escaping issue.
        button.addEventListener("click", () => {
            ask(question);
        });

        container.appendChild(button);
    });
}


// ---------------------------------------------------------
// Documents
// ---------------------------------------------------------

async function loadDocs() {
    try {
        const res = await fetch(`${API}/documents`);
        const data = await res.json();

        const docs = data.documents || [];

        document.getElementById("docCount").textContent = docs.length;

        const list = document.getElementById("docList");

        if (!docs.length) {
            list.innerHTML = `
                <div class="no-docs">No documents yet</div>
            `;
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
            deleteButton.textContent = "✕";

            deleteButton.addEventListener("click", () => {
                deleteDoc(doc.name);
            });

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
        pdf: "📕",
        docx: "📘",
        xlsx: "📗",
        csv: "📊",
        html: "🌐",
        txt: "📄",
        md: "📝"
    }[ext] || "📄";
}

async function deleteDoc(name) {
    if (!confirm(`Delete ${name}?`)) return;

    try {
        await fetch(
            `${API}/documents/${encodeURIComponent(name)}`,
            {
                method: "DELETE"
            }
        );

        suggestionsLoaded = false;
        currentSuggestions = [];

        await loadDocs();
        await loadSuggestions(true);

        sysMsg(`🗑️ ${name} deleted`);

    } catch (err) {
        console.error("Delete failed:", err);
        sysMsg("❌ Could not delete document");
    }
}


// ---------------------------------------------------------
// Redis Cache
// ---------------------------------------------------------

async function loadCacheStats() {
    try {
        const res = await fetch(`${API}/cache/stats`);
        const data = await res.json();

        const ok = data.status === "connected";

        const el = document.getElementById("cacheStatus");

        el.textContent = ok
            ? "🟢 Connected"
            : "🔴 Offline";

        el.className = "stat-val " + (
            ok ? "on" : "off"
        );

        document.getElementById("cachedCount").textContent =
            data.cached_answers ?? "—";

        document.getElementById("cacheTTL").textContent =
            data.ttl_seconds
                ? `${data.ttl_seconds / 60} min`
                : "—";

    } catch (err) {
        console.error("Cache stats error:", err);
    }
}

async function clearCache() {
    try {
        await fetch(`${API}/cache/clear`, {
            method: "DELETE"
        });

        suggestionsLoaded = false;
        currentSuggestions = [];

        await loadCacheStats();
        await loadSuggestions(true);

        sysMsg("⚡ Cache cleared");

    } catch (err) {
        console.error("Cache clear error:", err);
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

    const loadId = addMsg(
        "⏳ Searching documents...",
        "loading"
    );

    const btn = document.getElementById("sendBtn");

    btn.disabled = true;
    btn.textContent = "...";

    try {
        const res = await fetch(`${API}/ask`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: q
            })
        });

        const data = await res.json();

        removeMsg(loadId);

        // Backend already returns followup.
        // Do NOT call /followup again.
        const followup = data.followup || null;

        addBotMsg(
            data.answer,
            data.sources,
            data.cached,
            followup
        );

        loadCacheStats();

    } catch (err) {
        removeMsg(loadId);

        addMsg(
            "❌ Cannot connect. Is the API running?",
            "bot"
        );

    } finally {
        btn.disabled = false;
        btn.textContent = "Send ➤";
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

function addBotMsg(answer, sources, cached, followup) {
    const box = document.getElementById("chatBox");

    const div = document.createElement("div");

    div.className = "msg bot-msg";

    const answerText = document.createElement("span");
    answerText.textContent = answer;

    div.appendChild(answerText);

    if (cached) {
        const badge = document.createElement("span");

        badge.className = "cache-badge";
        badge.textContent = "⚡ cached";

        div.appendChild(badge);
    }

    if (sources && sources.length > 0) {
        const src = document.createElement("div");

        src.className = "sources";
        src.textContent = "📚 Sources: " + sources.join(", ");

        div.appendChild(src);
    }

    if (followup) {
        const fu = document.createElement("div");

        fu.className = "followup-single";

        const button = document.createElement("button");

        button.className = "followup-single-btn";
        button.textContent = "💡 " + followup;

        button.addEventListener("click", () => {
            ask(followup);
        });

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