const API = "http://localhost:8000";

window.onload = () => {
    loadDocs();
    loadCacheStats();
    loadSuggestions();
    setInterval(loadCacheStats, 30000);
};

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
    uploadFile(e.dataTransfer.files[0]);
}
function onFileSelect(e) {
    uploadFile(e.target.files[0]);
}

async function uploadFile(file) {
    if (!file) return;

    const prog = document.getElementById("progressWrap");
    const msg  = document.getElementById("uploadMsg");
    const lbl  = document.getElementById("progressLabel");

    prog.style.display = "block";
    msg.style.display  = "none";
    lbl.textContent    = `Uploading ${file.name}...`;

    try {
        const fd = new FormData();
        fd.append("file", file);
        const res  = await fetch(`${API}/upload`, { method: "POST", body: fd });
        const data = await res.json();

        prog.style.display = "none";
        msg.style.display  = "block";

        if (data.success) {
            msg.className   = "upload-msg ok";
            msg.textContent = data.message;
            loadDocs();
            loadSuggestions();
        } else {
            msg.className   = "upload-msg err";
            msg.textContent = data.message;
        }
    } catch (err) {
        prog.style.display = "none";
        msg.style.display  = "block";
        msg.className      = "upload-msg err";
        msg.textContent    = "Upload failed: " + err.message;
    }

    document.getElementById("fileInput").value = "";
    setTimeout(() => msg.style.display = "none", 6000);
}

async function loadSuggestions() {
    const container = document.getElementById("suggestionsBox");
    if (!container) return;

    container.innerHTML = `<div class="suggestion-loading">⏳ Generating suggestions from your documents (may take a moment)...</div>`;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000);

        const res  = await fetch(`${API}/suggestions`, { signal: controller.signal });
        clearTimeout(timeoutId);
        const data = await res.json();

        console.log("Suggestions response:", data);

        if (data.suggestions && data.suggestions.length > 0) {
            container.innerHTML = data.suggestions.map(s => `
                <button class="suggestion-chip" onclick="ask('${s.replace(/'/g, "\\'")}')">
                    ${s}
                </button>
            `).join("");
        } else {
            showDefaultSuggestions(container);
        }
    } catch (err) {
        console.error("Suggestions error:", err);
        showDefaultSuggestions(container);
    }

    document.getElementById("chatBox").scrollTop = 0;
}

function showDefaultSuggestions(container) {
    const defaults = [
        "What is the annual leave policy?",
        "What are the travel expense limits?",
        "What is the work from home policy?",
        "What are the office timings?",
        "How do I apply for sick leave?"
    ];
    container.innerHTML = defaults.map(s => `
        <button class="suggestion-chip" onclick="ask('${s}')">${s}</button>
    `).join("");
}

async function loadDocs() {
    try {
        const res  = await fetch(`${API}/documents`);
        const data = await res.json();
        const docs = data.documents;

        document.getElementById("docCount").textContent = docs.length;
        const list = document.getElementById("docList");

        if (!docs.length) {
            list.innerHTML = '<div class="no-docs">No documents yet</div>';
            return;
        }

        list.innerHTML = docs.map(d => `
            <div class="doc-item">
                <div class="doc-left">
                    <span class="doc-icon">${fileIcon(d.name)}</span>
                    <div>
                        <div class="doc-name" title="${d.name}">${d.name}</div>
                        <div class="doc-size">${d.size_kb} KB</div>
                    </div>
                </div>
                <button class="del-btn" onclick="deleteDoc('${d.name}')">✕</button>
            </div>
        `).join("");
    } catch {}
}

function fileIcon(name) {
    const ext = name.split(".").pop().toLowerCase();
    return { pdf:"📕", docx:"📘", xlsx:"📗", csv:"📊", html:"🌐", txt:"📄", md:"📝" }[ext] || "📄";
}

async function deleteDoc(name) {
    if (!confirm(`Delete ${name}?`)) return;
    await fetch(`${API}/documents/${name}`, { method: "DELETE" });
    loadDocs();
    loadSuggestions();
    sysMsg(`🗑️ ${name} deleted`);
}

async function loadCacheStats() {
    try {
        const res  = await fetch(`${API}/cache/stats`);
        const data = await res.json();
        const ok   = data.status === "connected";

        const el = document.getElementById("cacheStatus");
        el.textContent = ok ? "🟢 Connected" : "🔴 Offline";
        el.className   = "stat-val " + (ok ? "on" : "off");

        document.getElementById("cachedCount").textContent = data.cached_answers ?? "—";
        document.getElementById("cacheTTL").textContent = data.ttl_seconds ? `${data.ttl_seconds / 60} min` : "—";
    } catch {}
}

async function clearCache() {
    await fetch(`${API}/cache/clear`, { method: "DELETE" });
    loadCacheStats();
    sysMsg("⚡ Cache cleared");
}

async function ask(question) {
    const input = document.getElementById("qInput");
    const q     = question || input.value.trim();
    if (!q) return;
    input.value = "";

    addMsg(q, "user");
    const loadId = addMsg("⏳ Searching documents...", "loading");

    const btn = document.getElementById("sendBtn");
    btn.disabled    = true;
    btn.textContent = "...";

    try {
        const res  = await fetch(`${API}/ask`, {
            method : "POST",
            headers: { "Content-Type": "application/json" },
            body   : JSON.stringify({ question: q })
        });
        const data = await res.json();
        removeMsg(loadId);

        let followup = null;
        if (data.sources && data.sources.length > 0) {
            try {
                const fuRes = await fetch(
                    `${API}/followup?question=${encodeURIComponent(q)}&answer=${encodeURIComponent(data.answer.substring(0, 200))}`
                );
                const fuData = await fuRes.json();
                followup     = fuData.followup;
            } catch (e) {}
        }

        addBotMsg(data.answer, data.sources, data.cached, followup);
        loadCacheStats();
    } catch (err) {
        removeMsg(loadId);
        addMsg("❌ Cannot connect. Is the API running?", "bot");
    }

    btn.disabled    = false;
    btn.textContent = "Send ➤";
    input.focus();
}

function addMsg(text, type) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    const id  = "m" + Date.now();
    div.id          = id;
    div.className   = `msg ${type}-msg`;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return id;
}

function addBotMsg(answer, sources, cached, followup) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = "msg bot-msg";
    div.appendChild(document.createTextNode(answer));

    if (cached) {
        const badge       = document.createElement("span");
        badge.className   = "cache-badge";
        badge.textContent = "⚡ cached";
        div.appendChild(badge);
    }

    if (sources && sources.length > 0) {
        const src       = document.createElement("div");
        src.className   = "sources";
        src.textContent = "📚 Sources: " + sources.join(", ");
        div.appendChild(src);
    }

    if (followup) {
        const fu     = document.createElement("div");
        fu.className = "followup-single";
        const btn       = document.createElement("button");
        btn.className   = "followup-single-btn";
        btn.textContent = "💡 " + followup;
        btn.onclick     = () => ask(followup);
        fu.appendChild(btn);
        div.appendChild(fu);
    }

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function removeMsg(id) {
    document.getElementById(id)?.remove();
}

function sysMsg(text) {
    const box       = document.getElementById("chatBox");
    const div       = document.createElement("div");
    div.className   = "system-msg";
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop   = box.scrollHeight;
}