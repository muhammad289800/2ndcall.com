const state = {
  providers: [],
  numbers: [],
  searchResults: [],
};

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}

function setStatus(elId, text, isError = false) {
  const el = document.getElementById(elId);
  el.textContent = text || "";
  el.className = `status ${isError ? "err" : "ok"}`;
}

function providerOptions(includeUnconfigured = true) {
  const filtered = includeUnconfigured
    ? state.providers
    : state.providers.filter((p) => p.configured);
  return filtered
    .map((provider) => {
      const disabledHint = provider.configured ? "" : " (not configured)";
      return `<option value="${esc(provider.provider)}">${esc(provider.label)}${disabledHint}</option>`;
    })
    .join("");
}

function refreshProviderSelects() {
  const options = providerOptions(true);
  ["provider", "msg_provider", "call_provider"].forEach((id) => {
    const sel = document.getElementById(id);
    sel.innerHTML = options;
  });
}

function syncFromProviderToFromNumberSelects() {
  const msgProvider = document.getElementById("msg_provider").value;
  const callProvider = document.getElementById("call_provider").value;

  const msgOptions = state.numbers
    .filter((n) => n.provider === msgProvider)
    .map((n) => `<option value="${esc(n.phone_number)}">${esc(n.phone_number)} (id:${n.id})</option>`)
    .join("");
  document.getElementById("msg_from").innerHTML =
    msgOptions || '<option value="">No numbers for selected provider</option>';

  const callOptions = state.numbers
    .filter((n) => n.provider === callProvider)
    .map((n) => `<option value="${esc(n.phone_number)}">${esc(n.phone_number)} (id:${n.id})</option>`)
    .join("");
  document.getElementById("call_from").innerHTML =
    callOptions || '<option value="">No numbers for selected provider</option>';
}

function renderManagedNumbers() {
  const tbody = document.getElementById("managed_numbers");
  if (!state.numbers.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="small">No managed numbers yet.</td></tr>';
    syncFromProviderToFromNumberSelects();
    return;
  }

  tbody.innerHTML = state.numbers
    .map(
      (n) => `
      <tr>
        <td>${esc(n.id)}</td>
        <td><span class="chip">${esc(n.provider)}</span></td>
        <td>${esc(n.phone_number)}</td>
        <td>${esc(n.line_type || "unknown")}</td>
        <td class="actions">
          <button class="danger" data-release-id="${esc(n.id)}">Release</button>
        </td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll("button[data-release-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await requestJson(`/api/numbers/${btn.dataset.releaseId}/release`, { method: "POST" });
        setStatus("numbers_status", `Released managed number ID ${btn.dataset.releaseId}.`);
        await loadNumbers();
      } catch (error) {
        setStatus("numbers_status", error.message, true);
      }
    });
  });

  syncFromProviderToFromNumberSelects();
}

function renderSearchResults() {
  const tbody = document.getElementById("search_results");
  if (!state.searchResults.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="small">No results yet.</td></tr>';
    return;
  }

  tbody.innerHTML = state.searchResults
    .map((n) => {
      const caps = [];
      if (n.capabilities?.sms) caps.push("sms");
      if (n.capabilities?.voice) caps.push("voice");
      return `
      <tr>
        <td>${esc(n.phone_number)}</td>
        <td>${esc(n.line_type || "unknown")}</td>
        <td>${esc(caps.join(", ") || "n/a")}</td>
        <td>${esc([n.locality, n.region].filter(Boolean).join(", ") || "-")}</td>
        <td>${esc(n.monthly_cost_estimate ?? "-")}</td>
        <td><button data-buy-number="${esc(n.phone_number)}">Buy</button></td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll("button[data-buy-number]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const provider = document.getElementById("provider").value;
        const nonVoipOnly = document.getElementById("non_voip_only").value === "true";
        await requestJson("/api/numbers/purchase", {
          method: "POST",
          body: JSON.stringify({
            provider,
            phone_number: btn.dataset.buyNumber,
            non_voip_only: nonVoipOnly,
          }),
        });
        setStatus("search_status", `Purchased ${btn.dataset.buyNumber}.`);
        await loadNumbers();
      } catch (error) {
        setStatus("search_status", error.message, true);
      }
    });
  });
}

async function loadProviders() {
  const data = await requestJson("/api/providers");
  state.providers = data.providers || [];
  refreshProviderSelects();
}

async function loadNumbers() {
  const data = await requestJson("/api/numbers");
  state.numbers = data.numbers || [];
  renderManagedNumbers();
}

async function runSearch() {
  const provider = document.getElementById("provider").value;
  const payload = {
    provider,
    country: document.getElementById("country").value || "US",
    area_code: document.getElementById("area_code").value || "",
    limit: Number(document.getElementById("limit").value || "10"),
    non_voip_only: document.getElementById("non_voip_only").value === "true",
    require_sms: document.getElementById("require_sms").value === "true",
    require_voice: document.getElementById("require_voice").value === "true",
  };
  try {
    setStatus("search_status", "Searching...");
    const data = await requestJson("/api/numbers/search", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.searchResults = data.results || [];
    renderSearchResults();
    setStatus("search_status", `Found ${state.searchResults.length} numbers.`);
  } catch (error) {
    setStatus("search_status", error.message, true);
  }
}

async function syncProviderNumbers() {
  const provider = document.getElementById("provider").value;
  try {
    setStatus("numbers_status", "Syncing...");
    const data = await requestJson("/api/numbers/sync", {
      method: "POST",
      body: JSON.stringify({ provider }),
    });
    setStatus("numbers_status", `Imported ${data.imported} numbers from ${provider}.`);
    await loadNumbers();
  } catch (error) {
    setStatus("numbers_status", error.message, true);
  }
}

async function sendMessage() {
  const provider = document.getElementById("msg_provider").value;
  const payload = {
    provider,
    from_number: document.getElementById("msg_from").value,
    to_number: document.getElementById("msg_to").value,
    message: document.getElementById("msg_body").value,
  };
  try {
    setStatus("msg_status", "Sending message...");
    const data = await requestJson("/api/messages/send", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setStatus("msg_status", `Message queued: ${data.message.id || "ok"}`);
  } catch (error) {
    setStatus("msg_status", error.message, true);
  }
}

async function startCall() {
  const provider = document.getElementById("call_provider").value;
  const payload = {
    provider,
    from_number: document.getElementById("call_from").value,
    to_number: document.getElementById("call_to").value,
    say_text: document.getElementById("call_text").value,
  };
  try {
    setStatus("call_status", "Starting call...");
    const data = await requestJson("/api/calls/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setStatus("call_status", `Call initiated: ${data.call.id || "ok"}`);
  } catch (error) {
    setStatus("call_status", error.message, true);
  }
}

function bindEvents() {
  document.getElementById("search_btn").addEventListener("click", runSearch);
  document.getElementById("refresh_numbers_btn").addEventListener("click", loadNumbers);
  document.getElementById("sync_provider_btn").addEventListener("click", syncProviderNumbers);
  document.getElementById("send_msg_btn").addEventListener("click", sendMessage);
  document.getElementById("start_call_btn").addEventListener("click", startCall);
  document.getElementById("msg_provider").addEventListener("change", syncFromProviderToFromNumberSelects);
  document.getElementById("call_provider").addEventListener("change", syncFromProviderToFromNumberSelects);
}

async function init() {
  try {
    await loadProviders();
    await loadNumbers();
    bindEvents();
  } catch (error) {
    setStatus("search_status", error.message, true);
  }
}

init();

