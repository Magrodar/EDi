const state = {
  apiBase: localStorage.getItem("edi_api_base") || "http://localhost:8000",
  apiKey: localStorage.getItem("edi_api_key") || "",
};

function el(id) { return document.getElementById(id); }

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function api(path, options = {}) {
  const resp = await fetch(state.apiBase + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": state.apiKey,
      ...(options.headers || {}),
    },
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ? JSON.stringify(body.detail) : detail;
    } catch (_) { /* ignore */ }
    throw new Error(`${resp.status} ${detail}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function showError(containerId, err) {
  const container = el(containerId);
  container.innerHTML = `<div class="error-banner">${escapeHtml(err.message || String(err))}</div>` + container.innerHTML;
}

// ---------- Tabs ----------
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.add("hidden"));
    btn.classList.add("active");
    el(`tab-${btn.dataset.tab}`).classList.remove("hidden");
    el("settingsPanel").classList.add("hidden");
    if (btn.dataset.tab === "brief") loadBrief();
    if (btn.dataset.tab === "commitments") loadCommitments();
    if (btn.dataset.tab === "decisions") loadDecisions();
    if (btn.dataset.tab === "risks") loadRisks();
    if (btn.dataset.tab === "alerts") loadAlerts();
  });
});

// ---------- Settings ----------
el("settingsToggle").addEventListener("click", () => {
  el("apiBase").value = state.apiBase;
  el("apiKey").value = state.apiKey;
  el("settingsPanel").classList.toggle("hidden");
});
el("saveSettings").addEventListener("click", () => {
  state.apiBase = el("apiBase").value.trim() || "http://localhost:8000";
  state.apiKey = el("apiKey").value.trim();
  localStorage.setItem("edi_api_base", state.apiBase);
  localStorage.setItem("edi_api_key", state.apiKey);
  el("settingsPanel").classList.add("hidden");
  loadBrief();
});

// ---------- Daily Brief ----------
function levelBadge(level) {
  return `<span class="badge ${level}">${level.replace("_", " ")}</span>`;
}

function renderBriefList(items, renderItem, emptyText) {
  if (!items || items.length === 0) return `<p class="empty">${emptyText}</p>`;
  return items.map(renderItem).join("");
}

async function loadBrief() {
  const container = el("briefContent");
  container.innerHTML = "<p class='hint'>Loading…</p>";
  try {
    const brief = await api("/v1/briefs/daily");
    let html = "";

    html += `<div class="brief-block"><h3>Priority #1</h3>`;
    if (brief.priority_1) {
      const p = brief.priority_1;
      html += `<div class="card priority-card"><div class="card-title">${escapeHtml(p.title || p.reason || "—")}</div>
        <div class="card-meta">${p.type ? `<span>${escapeHtml(p.type)}</span>` : ""}${p.due_at ? `<span>due ${new Date(p.due_at).toLocaleString()}</span>` : ""}</div></div>`;
    } else {
      html += `<p class="empty">Nothing pressing detected.</p>`;
    }
    html += `</div>`;

    html += `<div class="brief-block"><h3>Critical tasks (max 3)</h3>${renderBriefList(
      brief.critical_tasks,
      (c) => `<div class="card"><div class="card-title">${escapeHtml(c.title)}</div>
        <div class="card-meta"><span>${c.status}</span>${c.due_at ? `<span>due ${new Date(c.due_at).toLocaleString()}</span>` : ""}</div></div>`,
      "No critical tasks due."
    )}</div>`;

    html += `<div class="brief-block"><h3>Decisions needed</h3>${renderBriefList(
      brief.decisions_needed,
      (d) => `<div class="card"><div class="card-title">${escapeHtml(d.question)}</div></div>`,
      "None open."
    )}</div>`;

    html += `<div class="brief-block"><h3>Risks (changed / action-relevant)</h3>${renderBriefList(
      brief.risks_changed,
      (r) => `<div class="card"><div class="card-title">${escapeHtml(r.title)}</div><div class="card-meta"><span>exposure ${r.exposure}</span></div></div>`,
      "No action-relevant risks."
    )}</div>`;

    html += `<div class="brief-block"><h3>Waiting on</h3>${renderBriefList(
      brief.waiting_on,
      (w) => `<div class="card"><div class="card-title">${escapeHtml(w.title)}</div></div>`,
      "Nothing waiting on someone else."
    )}</div>`;

    html += `<div class="brief-block"><h3>Deep work</h3><p>${escapeHtml(brief.deep_work_recommendation || "—")}</p></div>`;

    if (brief.edi_observation) {
      html += `<div class="brief-block"><h3>EDI observation</h3><p>${escapeHtml(brief.edi_observation)}</p></div>`;
    }

    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = "";
    showError("briefContent", err);
  }
}
el("refreshBrief").addEventListener("click", loadBrief);

// ---------- Debrief ----------
el("submitDebrief").addEventListener("click", async () => {
  const text = el("debriefText").value.trim();
  if (!text) return;
  const resultEl = el("debriefResult");
  resultEl.innerHTML = "<p class='hint'>Processing…</p>";
  try {
    const result = await api("/v1/capture/transcript", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    let html = `<div class="card"><div class="card-title">Extracted</div><div class="card-meta">
      <span>${result.facts.length} facts</span>
      <span>${result.commitments.length} commitments</span>
      <span>${result.risks.length} risks</span>
      <span>${result.alerts_created} alerts created</span>
    </div></div>`;
    result.commitments.forEach((c) => {
      html += `<div class="card"><span class="badge open">commitment</span> ${escapeHtml(c.title)}</div>`;
    });
    result.risks.forEach((r) => {
      html += `<div class="card"><span class="badge warning">risk</span> ${escapeHtml(r.title)}</div>`;
    });
    resultEl.innerHTML = html;
    el("debriefText").value = "";
  } catch (err) {
    resultEl.innerHTML = "";
    showError("debriefResult", err);
  }
});

// ---------- Commitments ----------
async function loadCommitments() {
  const container = el("commitmentsList");
  container.innerHTML = "<p class='hint'>Loading…</p>";
  try {
    const items = await api("/v1/commitments");
    container.innerHTML = renderBriefList(
      items,
      (c) => `<div class="card">
        <div class="card-title">${escapeHtml(c.title)}</div>
        <div class="card-meta">
          <span class="badge ${c.status}">${c.status}</span>
          ${c.due_at ? `<span>due ${new Date(c.due_at).toLocaleString()}</span>` : "<span>no due date</span>"}
        </div>
        <div class="card-actions">
          ${["in_progress", "blocked", "done", "cancelled"]
            .map((s) => `<button class="btn small" data-commitment="${c.commitment_id}" data-status="${s}">${s}</button>`)
            .join("")}
        </div>
      </div>`,
      "No commitments yet."
    );
    container.querySelectorAll("[data-commitment]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/v1/commitments/${btn.dataset.commitment}`, {
          method: "PATCH",
          body: JSON.stringify({ status: btn.dataset.status }),
        });
        loadCommitments();
      });
    });
  } catch (err) {
    container.innerHTML = "";
    showError("commitmentsList", err);
  }
}
el("refreshCommitments").addEventListener("click", loadCommitments);
el("addCommitment").addEventListener("click", async () => {
  const title = el("newCommitmentTitle").value.trim();
  if (!title) return;
  const due = el("newCommitmentDue").value;
  try {
    await api("/v1/commitments", {
      method: "POST",
      body: JSON.stringify({ title, due_at: due ? new Date(due).toISOString() : null }),
    });
    el("newCommitmentTitle").value = "";
    el("newCommitmentDue").value = "";
    loadCommitments();
  } catch (err) {
    showError("commitmentsList", err);
  }
});

// ---------- Decisions ----------
async function loadDecisions() {
  const container = el("decisionsList");
  container.innerHTML = "<p class='hint'>Loading…</p>";
  try {
    const items = await api("/v1/decisions");
    container.innerHTML = renderBriefList(
      items,
      (d) => `<div class="card">
        <div class="card-title">${escapeHtml(d.question)}</div>
        <div class="card-meta"><span class="badge ${d.status}">${d.status}</span></div>
        ${d.status === "decided" ? `<div class="card-actions"><button class="btn small" data-review="${d.decision_id}">Mark reviewed</button></div>` : ""}
      </div>`,
      "No decisions logged yet."
    );
    container.querySelectorAll("[data-review]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const notes = prompt("Outcome notes (predicted vs. actual):") || "";
        await api(`/v1/decisions/${btn.dataset.review}/review`, {
          method: "PATCH",
          body: JSON.stringify({ outcome_notes: notes }),
        });
        loadDecisions();
      });
    });
  } catch (err) {
    container.innerHTML = "";
    showError("decisionsList", err);
  }
}
el("refreshDecisions").addEventListener("click", loadDecisions);
el("addDecision").addEventListener("click", async () => {
  const question = el("newDecisionQuestion").value.trim();
  if (!question) return;
  try {
    await api("/v1/decisions", { method: "POST", body: JSON.stringify({ question }) });
    el("newDecisionQuestion").value = "";
    loadDecisions();
  } catch (err) {
    showError("decisionsList", err);
  }
});

// ---------- Risks ----------
async function loadRisks() {
  const container = el("risksList");
  container.innerHTML = "<p class='hint'>Loading…</p>";
  try {
    const items = await api("/v1/risks");
    container.innerHTML = renderBriefList(
      items,
      (r) => `<div class="card">
        <div class="card-title">${escapeHtml(r.title)}</div>
        <div class="card-meta">
          <span class="badge ${r.status}">${r.status}</span>
          <span>exposure ${r.exposure ?? "—"}</span>
        </div>
        <div class="card-actions">
          ${["mitigating", "accepted", "closed"]
            .map((s) => `<button class="btn small" data-risk="${r.risk_id}" data-status="${s}">${s}</button>`)
            .join("")}
        </div>
      </div>`,
      "No risks logged yet."
    );
    container.querySelectorAll("[data-risk]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/v1/risks/${btn.dataset.risk}`, {
          method: "PATCH",
          body: JSON.stringify({ status: btn.dataset.status }),
        });
        loadRisks();
      });
    });
  } catch (err) {
    container.innerHTML = "";
    showError("risksList", err);
  }
}
el("refreshRisks").addEventListener("click", loadRisks);
el("addRisk").addEventListener("click", async () => {
  const title = el("newRiskTitle").value.trim();
  if (!title) return;
  const probability = parseFloat(el("newRiskProbability").value);
  const impact = parseFloat(el("newRiskImpact").value);
  try {
    await api("/v1/risks", {
      method: "POST",
      body: JSON.stringify({
        title,
        probability: Number.isFinite(probability) ? probability : undefined,
        impact: Number.isFinite(impact) ? impact : undefined,
      }),
    });
    el("newRiskTitle").value = "";
    el("newRiskProbability").value = "";
    el("newRiskImpact").value = "";
    loadRisks();
  } catch (err) {
    showError("risksList", err);
  }
});

// ---------- Alerts ----------
async function loadAlerts() {
  const container = el("alertsList");
  container.innerHTML = "<p class='hint'>Loading…</p>";
  try {
    const items = await api("/v1/alerts");
    container.innerHTML = renderBriefList(
      items,
      (a) => `<div class="card">
        <div class="card-title">${levelBadge(a.level)} ${escapeHtml(a.reason)}</div>
        <div class="card-meta">
          <span class="badge ${a.status}">${a.status}</span>
          <span>score ${a.intervention_score}</span>
          ${a.recommended_action ? `<span>${escapeHtml(a.recommended_action)}</span>` : ""}
        </div>
        ${a.status !== "acknowledged" ? `<div class="card-actions"><button class="btn small" data-ack="${a.alert_id}">Acknowledge</button></div>` : ""}
      </div>`,
      "No alerts."
    );
    container.querySelectorAll("[data-ack]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/v1/alerts/${btn.dataset.ack}/ack`, { method: "POST" });
        loadAlerts();
      });
    });
  } catch (err) {
    container.innerHTML = "";
    showError("alertsList", err);
  }
}
el("refreshAlerts").addEventListener("click", loadAlerts);
el("runScan").addEventListener("click", async () => {
  try {
    await api("/v1/reason", { method: "POST" });
    loadAlerts();
  } catch (err) {
    showError("alertsList", err);
  }
});

// ---------- Search ----------
async function runSearch() {
  const q = el("searchQuery").value.trim();
  const container = el("searchResults");
  container.innerHTML = "<p class='hint'>Searching…</p>";
  try {
    const items = await api(`/v1/memory/search?q=${encodeURIComponent(q)}`);
    container.innerHTML = renderBriefList(
      items,
      (f) => `<div class="card">
        <div class="card-title">${escapeHtml(f.subject_label)} — ${escapeHtml(f.predicate)}</div>
        <div class="card-meta">
          <span class="badge ${f.status}">${f.status}</span>
          <span>confidence ${f.confidence}</span>
          ${f.promotion_score !== null ? `<span>promotion ${f.promotion_score}</span>` : ""}
        </div>
        <pre style="white-space:pre-wrap;color:var(--text-dim);font-size:12px;margin:8px 0 0;">${escapeHtml(JSON.stringify(f.value_json))}</pre>
        <div class="card-actions"><button class="btn small" data-delete="${f.fact_id}">Delete</button></div>
      </div>`,
      "No matching facts."
    );
    container.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/v1/memory/${btn.dataset.delete}`, { method: "DELETE" });
        runSearch();
      });
    });
  } catch (err) {
    container.innerHTML = "";
    showError("searchResults", err);
  }
}
el("runSearch").addEventListener("click", runSearch);
el("searchQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });

// ---------- Init ----------
loadBrief();
