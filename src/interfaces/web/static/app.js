// ────────────── App state and helpers ──────────────

const API_BASE = ""; // Same origin — no prefix needed

async function api(path, options = {}) {
    const response = await fetch(API_BASE + path, options);
    if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.detail || `HTTP ${response.status}`);
    }
    return response.json();
}

function setStatus(element, type, message) {
    element.className = "status " + type;
    element.textContent = message;
}

function clearStatus(element) {
    element.className = "status";
    element.textContent = "";
}

function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
}

// ────────────── Stats ──────────────

async function refreshStats() {
    try {
        const stats = await api("/stats");
        document.getElementById("stats").textContent =
            `${stats.documents} documents · ${stats.chunks} chunks`;
    } catch (e) {
        document.getElementById("stats").textContent = "Stats unavailable";
    }
}

// ────────────── Document list ──────────────

async function refreshDocuments() {
    const container = document.getElementById("documents-list");
    container.innerHTML = '<p class="empty">Loading…</p>';
    try {
        const data = await api("/documents");
        if (!data.documents.length) {
            container.innerHTML = '<p class="empty">No documents yet. Upload one above to get started.</p>';
            return;
        }
        container.innerHTML = data.documents.map(doc => `
            <div class="doc-item">
                <div class="doc-info">
                    <span class="doc-name">${escapeHtml(doc.filename)}</span>
                    <span class="doc-meta">
                        ${doc.filetype} · ${doc.chunk_count} chunks ·
                        uploaded ${formatDate(doc.uploaded_at)} ·
                        id: ${doc.doc_id}
                    </span>
                </div>
                <button class="delete-btn" data-id="${doc.doc_id}">Delete</button>
            </div>
        `).join("");

        // Wire up delete buttons
        container.querySelectorAll(".delete-btn").forEach(btn => {
            btn.addEventListener("click", () => deleteDocument(btn.dataset.id));
        });
    } catch (e) {
        container.innerHTML = `<p class="empty">Failed to load: ${escapeHtml(e.message)}</p>`;
    }
}

async function deleteDocument(docId) {
    if (!confirm(`Delete document ${docId}?`)) return;
    try {
        await api(`/documents/${docId}`, { method: "DELETE" });
        await refreshDocuments();
        await refreshStats();
    } catch (e) {
        alert("Delete failed: " + e.message);
    }
}

// ────────────── Upload ──────────────

const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-btn");
const uploadStatus = document.getElementById("upload-status");

uploadBtn.addEventListener("click", async () => {
    const file = fileInput.files[0];
    if (!file) {
        setStatus(uploadStatus, "error", "Please select a file first.");
        return;
    }

    uploadBtn.disabled = true;
    setStatus(uploadStatus, "success", `Uploading ${file.name}…`);

    const formData = new FormData();
    formData.append("file", file);

    try {
        const result = await api("/documents/upload", {
            method: "POST",
            body: formData,
        });
        setStatus(
            uploadStatus,
            "success",
            `✓ Ingested ${result.filename} — ${result.chunks_created} chunks created (doc_id: ${result.doc_id})`,
        );
        fileInput.value = "";
        await refreshDocuments();
        await refreshStats();
    } catch (e) {
        setStatus(uploadStatus, "error", "Upload failed: " + e.message);
    } finally {
        uploadBtn.disabled = false;
    }
});

// ────────────── Search ──────────────

const queryInput = document.getElementById("query-input");
const modeSelect = document.getElementById("mode-select");
const searchBtn = document.getElementById("search-btn");
const resultsContainer = document.getElementById("search-results");

async function performSearch() {
    const query = queryInput.value.trim();
    if (!query) return;

    const mode = modeSelect.value;
    searchBtn.disabled = true;
    resultsContainer.innerHTML = '<p class="no-results">Searching…</p>';

    try {
        const data = await api(`/search/${mode}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query, top_k: 5 }),
        });
        renderResults(data.results, mode);
    } catch (e) {
        resultsContainer.innerHTML = `<p class="no-results">Search failed: ${escapeHtml(e.message)}</p>`;
    } finally {
        searchBtn.disabled = false;
    }
}

function renderResults(results, mode) {
    if (!results.length) {
        resultsContainer.innerHTML = '<p class="no-results">No matches.</p>';
        return;
    }

    resultsContainer.innerHTML = results.map(r => {
        const badges = [];

        // Mode-specific score badges
        if (mode === "hybrid") {
            badges.push(`<span class="badge">RRF: ${r.rrf_score.toFixed(4)}</span>`);
            if (r.found_in && r.found_in.length === 2) {
                badges.push(`<span class="badge found-both">found by both</span>`);
            } else if (r.found_in) {
                badges.push(`<span class="badge">found by ${r.found_in[0]}</span>`);
            }
        } else if (mode === "semantic") {
            badges.push(`<span class="badge">distance: ${r.semantic_distance.toFixed(3)}</span>`);
        } else {
            badges.push(`<span class="badge">BM25: ${r.keyword_score.toFixed(2)}</span>`);
        }

        return `
            <div class="result">
                <div class="result-meta">
                    <span class="badge">${escapeHtml(r.filename || "?")}</span>
                    <span>chunk #${r.chunk_index}</span>
                    ${badges.join("")}
                </div>
                <div class="result-text">${escapeHtml(r.content)}</div>
            </div>
        `;
    }).join("");
}

searchBtn.addEventListener("click", performSearch);
queryInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") performSearch();
});

document.getElementById("refresh-docs-btn").addEventListener("click", refreshDocuments);

// ────────────── Utilities ──────────────

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
}

// ────────────── Initial load ──────────────

refreshStats();
refreshDocuments();