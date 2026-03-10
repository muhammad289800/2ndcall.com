const state = {
  providers: [],
  numbers: [],
  searchResults: [],
  inboundMessages: [],
  inboundCalls: [],
  wallet: { balance: 0, transactions: [] },
  providerBalances: [],
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

function renderProviderBalances() {
  const tbody = document.getElementById("provider_balances");
  if (!state.providerBalances.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="small">No provider balances available.</td></tr>';
    return;
  }
  tbody.innerHTML = state.providerBalances
    .map((item) => {
      const details = item.account_balance || {};
      const balance =
        details.balance === null || details.balance === undefined
          ? "n/a"
          : `${esc(details.currency || "USD")} ${Number(details.balance).toFixed(2)}`;
      const note = details.error
        ? `error: ${esc(details.error)}`
        : details.source
          ? `source: ${esc(details.source)}`
          : "";
      return `<tr>
        <td>${esc(item.provider)}</td>
        <td>${balance}</td>
        <td>${note}</td>
      </tr>`;
    })
    .join("");
}

function renderWallet() {
  document.getElementById("wallet_balance").textContent = `$${Number(state.wallet.balance || 0).toFixed(2)}`;
}

function renderInboundMessages() {
  const tbody = document.getElementById("inbound_messages");
  if (!state.inboundMessages.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="small">No inbound messages yet.</td></tr>';
    return;
  }
  tbody.innerHTML = state.inboundMessages
    .map(
      (m) => `<tr>
        <td>${esc(m.created_at)}</td>
        <td>${esc(m.provider)}</td>
        <td>${esc(m.from_number)}</td>
        <td>${esc(m.to_number)}</td>
        <td>${esc(m.body)}</td>
        <td>${esc(m.status)}</td>
      </tr>`
    )
    .join("");
}

function renderInboundCalls() {
  const tbody = document.getElementById("inbound_calls");
  if (!state.inboundCalls.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="small">No inbound calls yet.</td></tr>';
    return;
  }
  tbody.innerHTML = state.inboundCalls
    .map(
      (c) => `<tr>
        <td>${esc(c.created_at)}</td>
        <td>${esc(c.provider)}</td>
        <td>${esc(c.from_number)}</td>
        <td>${esc(c.to_number)}</td>
        <td>${esc(c.status)}</td>
        <td>${esc(c.provider_call_id || "")}</td>
      </tr>`
    )
    .join("");
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
        <td><button data-buy-number="${esc(n.phone_number)}">Order number</button></td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll("button[data-buy-number]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const provider = document.getElementById("provider").value;
        const nonVoipOnly = document.getElementById("non_voip_only").value === "true";
        const data = await requestJson("/api/numbers/order", {
          method: "POST",
          body: JSON.stringify({
            provider,
            phone_number: btn.dataset.buyNumber,
            non_voip_only: nonVoipOnly,
          }),
        });
        const warnings = data.warnings || [];
        const warningText = warnings.length ? ` Warning: ${warnings.join(" | ")}` : "";
        setStatus(
          "search_status",
          `Ordered ${btn.dataset.buyNumber}. Charged $${Number(data.charged_usd || 0).toFixed(2)}.${warningText}`
        );
        await loadWallet();
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

async function loadProviderBalances() {
  const data = await requestJson("/api/providers/balances");
  state.providerBalances = data.balances || [];
  renderProviderBalances();
}

async function loadWallet() {
  const data = await requestJson("/api/wallet");
  state.wallet = data || { balance: 0, transactions: [] };
  renderWallet();
}

async function topupWallet() {
  const amount = Number(document.getElementById("topup_amount").value || "0");
  const method = document.getElementById("topup_method").value || "manual";
  try {
    const data = await requestJson("/api/wallet/topup", {
      method: "POST",
      body: JSON.stringify({ amount, method }),
    });
    setStatus("wallet_status", `Top-up successful. New balance: $${Number(data.balance).toFixed(2)}`);
    await loadWallet();
  } catch (error) {
    setStatus("wallet_status", error.message, true);
  }
}

async function loadNumbers() {
  const data = await requestJson("/api/numbers");
  state.numbers = data.numbers || [];
  renderManagedNumbers();
}

async function loadInboundMessages() {
  const data = await requestJson("/api/messages?direction=inbound&limit=50");
  state.inboundMessages = data.messages || [];
  renderInboundMessages();
}

async function loadInboundCalls() {
  const data = await requestJson("/api/calls?direction=inbound&limit=50");
  state.inboundCalls = data.calls || [];
  renderInboundCalls();
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
    const syncWarning = data.message?.auto_profile_sync?.warning
      ? ` | Sync warning: ${data.message.auto_profile_sync.warning}`
      : "";
    setStatus(
      "msg_status",
      `Message queued: ${data.message.id || "ok"} | Charged $${Number(data.charged_usd || 0).toFixed(2)}${syncWarning}`
    );
    await loadWallet();
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
    estimated_minutes: Number(document.getElementById("call_minutes").value || "1"),
  };
  try {
    setStatus("call_status", "Starting call...");
    const data = await requestJson("/api/calls/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const syncWarning = data.call?.auto_profile_sync?.warning
      ? ` | Sync warning: ${data.call.auto_profile_sync.warning}`
      : "";
    setStatus(
      "call_status",
      `Call initiated: ${data.call.id || "ok"} | Charged $${Number(data.charged_usd || 0).toFixed(2)}${syncWarning}`
    );
    await loadWallet();
  } catch (error) {
    setStatus("call_status", error.message, true);
  }
}

function renderWebhookUrls() {
  const base = window.location.origin;
  document.getElementById("twilio_msg_webhook").textContent = `${base}/webhooks/twilio/message`;
  document.getElementById("twilio_voice_webhook").textContent = `${base}/webhooks/twilio/voice`;
  document.getElementById("telnyx_events_webhook").textContent = `${base}/webhooks/telnyx/events`;
}

function bindEvents() {
  document.getElementById("search_btn").addEventListener("click", runSearch);
  document.getElementById("refresh_numbers_btn").addEventListener("click", loadNumbers);
  document.getElementById("sync_provider_btn").addEventListener("click", syncProviderNumbers);
  document.getElementById("send_msg_btn").addEventListener("click", sendMessage);
  document.getElementById("start_call_btn").addEventListener("click", startCall);
  document.getElementById("topup_btn").addEventListener("click", topupWallet);
  document.getElementById("refresh_provider_balances_btn").addEventListener("click", loadProviderBalances);
  document.getElementById("refresh_inbound_messages_btn").addEventListener("click", loadInboundMessages);
  document.getElementById("refresh_inbound_calls_btn").addEventListener("click", loadInboundCalls);
  document.getElementById("msg_provider").addEventListener("change", syncFromProviderToFromNumberSelects);
  document.getElementById("call_provider").addEventListener("change", syncFromProviderToFromNumberSelects);
}

async function init() {
  try {
    await loadProviders();
    await loadWallet();
    await loadProviderBalances();
    await loadNumbers();
    await loadInboundMessages();
    await loadInboundCalls();
    bindEvents();
    renderWebhookUrls();
  } catch (error) {
    setStatus("search_status", error.message, true);
  }
}

init();

