const API = "http://localhost:8000";

let suggestionsLoaded = false;
let suggestionsRequestRunning = false;
let currentSuggestions = [];

window.onload = () => {
    loadDocs();
    loadCacheStats();
    loadSuggestions();
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

            suggestionsLoaded = false;
            currentSuggestions = [];

            await loadDocs();
            await loadCacheStats();
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

    // Prevent two /suggestions requests at the same time.
    if (suggestionsRequestRunning) {
        return;
    }

    // Keep current suggestions visible unless refresh is required.
    if (suggestionsLoaded && !forceRefresh) {
        return;
    }

    suggestionsRequestRunning = true;

    container.innerHTML = `
        <div class="suggestion-loading">
            ⏳ Generating suggestions from your documents...
        </div>
    `;

    let timeoutId = null;

    try {
        const controller = new AbortController();

        // Stop only if suggestion generation takes longer than 3 minutes.
        timeoutId = setTimeout(() => {
            controller.abort();
        }, 180000);

        const res = await fetch(`${API}/suggestions`, {
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

        container.innerHTML = `
            <div class="suggestion-loading">
                No suggestions available right now.
            </div>
        `;

        suggestionsLoaded = false;

    } finally {
        if (timeoutId) {
            clearTimeout(timeoutId);
        }

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

        if (!res.ok) {
            throw new Error("Could not load documents");
        }

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
        xls: "📗",
        csv: "📊",
        html: "🌐",
        htm: "🌐",
        txt: "📄",
        md: "📝"
    }[ext] || "📄";
}

async function deleteDoc(name) {
    if (!confirm(`Delete ${name}?`)) {
        return;
    }

    try {
        const res = await fetch(
            `${API}/documents/${encodeURIComponent(name)}`,
            {
                method: "DELETE"
            }
        );

        if (!res.ok) {
            throw new Error("Could not delete document");
        }

        suggestionsLoaded = false;
        currentSuggestions = [];

        await loadDocs();
        await loadCacheStats();
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

        if (!res.ok) {
            throw new Error("Could not load cache statistics");
        }

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

        sysMsg("⚡ Cache cleared");

    } catch (err) {
        console.error("Cache clear error:", err);
        sysMsg("❌ Could not clear cache");
    }
}


// ---------------------------------------------------------
// Ask Question
// ---------------------------------------------------------

async function ask(question) {
    const input = document.getElementById("qInput");
    const q = question || input.value.trim();

    if (!q) {
        return;
    }

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

        if (!res.ok) {
            throw new Error("Could not get answer");
        }

        const data = await res.json();

        removeMsg(loadId);

        // Backend already supplies follow-up if enabled.
        // Frontend does not call /followup separately.
        const followup = data.followup || null;

        addBotMsg(
            data.answer,
            data.cached,
            followup
        );

        // Updates cache status only after an actual question.
        loadCacheStats();

    } catch (err) {
        console.error("Ask error:", err);

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

function addBotMsg(answer, cached, followup) {
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

    // No source section is created here.
    // Source names remain available internally in backend response.

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