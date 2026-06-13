const API = "http://localhost:8000";

// ── On Page Load ──────────────────────────────────────────────
window.onload = () => {
    loadDocs();
    loadCacheStats();
    setInterval(loadCacheStats, 30000);
};

// ── DRAG & DROP ───────────────────────────────────────────────
function onDragOver(e) {
    e.preventDefault();
    document.getElementById("dropZone")
            .classList.add("dragover");
}

function onDragLeave() {
    document.getElementById("dropZone")
            .classList.remove("dragover");
}

function onDrop(e) {
    e.preventDefault();
    onDragLeave();
    uploadFile(e.dataTransfer.files[0]);
}

function onFileSelect(e) {
    uploadFile(e.target.files[0]);
}

// ── UPLOAD ────────────────────────────────────────────────────
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

        const res  = await fetch(`${API}/upload`,
                         { method: "POST", body: fd });
        const data = await res.json();

        prog.style.display = "none";
        msg.style.display  = "block";

        if (data.success) {
            msg.className   = "upload-msg ok";
            msg.textContent = data.message;
            loadDocs();
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

// ── DOCUMENTS ─────────────────────────────────────────────────
async function loadDocs() {
    try {
        const res  = await fetch(`${API}/documents`);
        const data = await res.json();
        const docs = data.documents;

        document.getElementById("docCount")
                .textContent = docs.length;

        const list = document.getElementById("docList");

        if (!docs.length) {
            list.innerHTML =
                '<div class="no-docs">No documents yet</div>';
            return;
        }

        list.innerHTML = docs.map(d => `
            <div class="doc-item">
                <div class="doc-left">
                    <span class="doc-icon">
                        ${fileIcon(d.name)}
                    </span>
                    <div>
                        <div class="doc-name" title="${d.name}">
                            ${d.name}
                        </div>
                        <div class="doc-size">${d.size_kb} KB</div>
                    </div>
                </div>
                <button class="del-btn"
                    onclick="deleteDoc('${d.name}')">✕</button>
            </div>
        `).join("");
    } catch {}
}

function fileIcon(name) {
    const ext = name.split(".").pop().toLowerCase();
    return {
        pdf : "📕", docx: "📘", xlsx: "📗",
        csv : "📊", html: "🌐", txt : "📄", md: "📝"
    }[ext] || "📄";
}

async function deleteDoc(name) {
    if (!confirm(`Delete ${name}?`)) return;
    await fetch(`${API}/documents/${name}`,
                { method: "DELETE" });
    loadDocs();
    sysMsg(`${name} deleted`);
}

// ── CACHE ─────────────────────────────────────────────────────
async function loadCacheStats() {
    try {
        const res  = await fetch(`${API}/cache/stats`);
        const data = await res.json();
        const ok   = data.status === "connected";

        const el = document.getElementById("cacheStatus");
        el.textContent = ok ? "Connected" : "Offline";
        el.className   = "stat-val " + (ok ? "on" : "off");

        document.getElementById("cachedCount")
                .textContent = data.cached_answers ?? "—";
        document.getElementById("cacheTTL")
                .textContent = data.ttl_seconds
                    ? `${data.ttl_seconds / 60} min` : "—";
    } catch {}
}

async function clearCache() {
    await fetch(`${API}/cache/clear`, { method: "DELETE" });
    loadCacheStats();
    sysMsg("Cache cleared");
}

// ── CHAT ──────────────────────────────────────────────────────
async function ask(question) {
    const input = document.getElementById("qInput");
    const q     = question || input.value.trim();
    if (!q) return;
    input.value = "";

    // Remove welcome screen
    const w = document.getElementById("welcome");
    if (w) w.remove();

    addMsg(q, "user");

    const loadId = addMsg(
        " Searching documents...", "loading"
    );

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
        addBotMsg(
            data.answer,
            data.sources,
            data.cached,
            data.suggestions
        );
        loadCacheStats();

    } catch (err) {
        removeMsg(loadId);
        addMsg(
            "Cannot connect. Is the API running?",
            "bot"
        );
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

function addBotMsg(answer, sources, cached, suggestions) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = "msg bot-msg";

    // Answer text
    div.appendChild(document.createTextNode(answer));

    // Cache badge
    if (cached) {
        const badge = document.createElement("span");
        badge.className   = "cache-badge";
        badge.textContent = "⚡ cached";
        div.appendChild(badge);
    }

    // Sources
    if (sources?.length) {
        const src = document.createElement("div");
        src.className   = "sources";
        src.textContent = "📚 Sources: " + sources.join(", ");
        div.appendChild(src);
    }

    // Follow-up suggestions
    if (suggestions?.length) {
        const fu = document.createElement("div");
        fu.className = "followups";

        const lbl = document.createElement("div");
        lbl.className   = "followup-label";
        lbl.textContent = "💡 You might also ask:";
        fu.appendChild(lbl);

        suggestions.forEach(s => {
            const btn       = document.createElement("button");
            btn.className   = "followup-btn";
            btn.textContent = s;
            btn.onclick     = () => ask(s);
            fu.appendChild(btn);
        });

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
    div.className   = "system-msg";
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}