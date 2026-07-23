(() => {
  const cfg = window.SFRFR_CONFIG || {};
  const apiBase = (cfg.apiBase || "").replace(/\/$/, "");
  const cabinetBase = (cfg.cabinetUrl || "https://cabinet.taxi-doroga-dobra.ru/").replace(
    /\/?$/,
    "/",
  );
  const botUrl = cfg.maxBotUrl || "https://max.ru/";

  const els = {
    boot: document.getElementById("panel-boot"),
    form: document.getElementById("panel-form"),
    list: document.getElementById("panel-list"),
    panel: document.getElementById("panel-case"),
    nameInput: document.getElementById("client-name"),
    consent: document.getElementById("consent"),
    btnOpen: document.getElementById("btn-open"),
    caseList: document.getElementById("case-list"),
    btnNewCase: document.getElementById("btn-new-case"),
    status: document.getElementById("case-status"),
    statusHint: document.getElementById("case-status-hint"),
    caseId: document.getElementById("case-id"),
    caseName: document.getElementById("case-name"),
    caseDocs: document.getElementById("case-docs"),
    caseError: document.getElementById("case-error"),
    caseFindings: document.getElementById("case-findings"),
    caseNext: document.getElementById("case-next"),
    caseNextText: document.getElementById("case-next-text"),
    caseChecklist: document.getElementById("case-checklist"),
    caseChecklistList: document.getElementById("case-checklist-list"),
    caseDraft: document.getElementById("case-draft"),
    caseDraftBody: document.getElementById("case-draft-body"),
    caseSubmitHint: document.getElementById("case-submit-hint"),
    caseWarning: document.getElementById("case-warning"),
    fileInput: document.getElementById("file-input"),
    btnRefresh: document.getElementById("btn-refresh"),
    btnRun: document.getElementById("btn-run"),
    btnWeb: document.getElementById("btn-web-cabinet"),
    btnChat: document.getElementById("btn-chat"),
    btnBackList: document.getElementById("btn-back-list"),
    ordersList: document.getElementById("orders-list"),
    ordersEmpty: document.getElementById("orders-empty"),
    payCabinetLink: document.getElementById("pay-cabinet-link"),
    resultBody: document.getElementById("result-body"),
    resultCabinetLink: document.getElementById("result-cabinet-link"),
    messagesList: document.getElementById("messages-list"),
    messagesEmpty: document.getElementById("messages-empty"),
    messageForm: document.getElementById("message-form"),
    messageInput: document.getElementById("message-input"),
    toast: document.getElementById("toast"),
  };

  const PACKAGE_LABELS = {
    DIAG: "Диагностика",
    ACCOMP: "Сопровождение",
    SF_LUMP: "Post-payment (ЕДВ)",
    SF_MONTH: "Post-payment (прибавка)",
  };

  let currentCase = null;
  let maxUserId = null;
  let me = null;
  let statusLabels = {};
  let statusHints = {};

  function show(el) {
    [els.boot, els.form, els.list, els.panel].forEach((p) => p && p.classList.add("hidden"));
    el.classList.remove("hidden");
  }

  function toast(msg) {
    els.toast.textContent = msg;
    els.toast.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => els.toast.classList.add("hidden"), 3500);
  }

  function setBusy(busy) {
    [els.btnOpen, els.btnRefresh, els.btnRun, els.btnNewCase].forEach((b) => {
      if (b) b.disabled = busy;
    });
    if (els.fileInput) els.fileInput.disabled = busy;
  }

  function authHeaders(extra = {}) {
    const headers = { ...extra };
    const initData = window.WebApp?.initData || "";
    if (initData) headers["X-MAX-InitData"] = initData;
    else if (maxUserId) headers["X-MAX-User-Id"] = maxUserId;
    return headers;
  }

  async function api(path, options = {}) {
    const headers = authHeaders(options.headers || {});
    if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const res = await fetch(`${apiBase}${path}`, { ...options, headers });
    let body = null;
    const text = await res.text();
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = { detail: text };
    }
    if (!res.ok) {
      const detail = body?.detail || body?.message || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return body;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function resolveMaxUserId() {
    const wa = window.WebApp;
    const fromBridge = wa?.initDataUnsafe?.user?.id;
    if (fromBridge != null) return String(fromBridge);
    const q = new URLSearchParams(location.search).get("uid");
    if (q) return q;
    const saved = localStorage.getItem("sfrfr_demo_uid");
    if (saved) return saved;
    const demo = `demo-${Date.now()}`;
    localStorage.setItem("sfrfr_demo_uid", demo);
    return demo;
  }

  function mapDetail(c) {
    const status = c.pipeline_status || c.status || "intake";
    return {
      ...c,
      status,
      status_label: c.status_label || statusLabels[status] || status,
      status_hint: c.status_hint || statusHints[status] || "",
      document_count: Array.isArray(c.documents) ? c.documents.length : c.document_count || 0,
      client_name: me?.full_name || "Клиент",
      error: c.pipeline_error,
    };
  }

  function renderCase(raw) {
    const c = mapDetail(raw);
    currentCase = c;
    localStorage.setItem("sfrfr_case_id", c.id);
    els.status.textContent = c.status_label;
    els.statusHint.textContent = c.status_hint || "";
    els.caseId.textContent = c.id;
    els.caseName.textContent = c.client_name;
    els.caseDocs.textContent = String(c.document_count);

    if (c.error) {
      els.caseError.textContent = c.error;
      els.caseError.classList.remove("hidden");
    } else {
      els.caseError.classList.add("hidden");
    }

    if (els.caseWarning) {
      els.caseWarning.textContent =
        c.warning || "Решение принимает СФР. Результат не гарантирован.";
    }

    const findings = Array.isArray(c.findings) ? c.findings : [];
    if (findings.length) {
      els.caseFindings.innerHTML = findings
        .slice(0, 8)
        .map((f) => {
          const title = f.type || "finding";
          const msg = f.detail || "";
          return `<strong>${escapeHtml(title)}</strong>${msg ? `: ${escapeHtml(msg)}` : ""}`;
        })
        .join("<br>");
      els.caseFindings.classList.remove("hidden");
    } else {
      els.caseFindings.classList.add("hidden");
    }

    if (c.next_action && els.caseNext && els.caseNextText) {
      els.caseNextText.textContent = c.next_action;
      els.caseNext.classList.remove("hidden");
    } else if (els.caseNext) {
      els.caseNext.classList.add("hidden");
    }

    const checklist = Array.isArray(c.checklist_items) ? c.checklist_items : [];
    if (els.caseChecklist && els.caseChecklistList) {
      if (checklist.length) {
        els.caseChecklistList.innerHTML = checklist
          .slice(0, 12)
          .map((item) => {
            const title = escapeHtml(item.title || "пункт");
            const st = escapeHtml(item.status || "");
            return `<li><strong>${title}</strong> <span class="hint">${st}</span></li>`;
          })
          .join("");
        els.caseChecklist.classList.remove("hidden");
      } else {
        els.caseChecklist.classList.add("hidden");
      }
    }

    const draft = c.draft;
    if (els.caseDraft && els.caseDraftBody) {
      if (draft && (draft.body || draft.title)) {
        els.caseDraftBody.textContent = [draft.title, draft.body].filter(Boolean).join("\n\n");
        els.caseDraft.classList.remove("hidden");
      } else {
        els.caseDraft.classList.add("hidden");
      }
    }

    if (els.caseSubmitHint && c.submission_instruction) {
      els.caseSubmitHint.textContent = c.submission_instruction;
    }

    const payUrl = `${cabinetBase}?case=${encodeURIComponent(c.id)}&view=payments`;
    const resultUrl = `${cabinetBase}?case=${encodeURIComponent(c.id)}&view=result`;
    if (els.payCabinetLink) els.payCabinetLink.href = payUrl;
    if (els.resultCabinetLink) els.resultCabinetLink.href = resultUrl;

    show(els.panel);
    void loadOrders();
    void loadResult();
    void loadMessages();
  }

  function setTab(name) {
    document.querySelectorAll("#case-tabs .tab").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-tab") === name);
    });
    ["pay", "result", "chat"].forEach((id) => {
      const panel = document.getElementById(`tab-${id}`);
      if (!panel) return;
      panel.classList.toggle("hidden", name !== id);
    });
    // вкладка «дело» — основной контент над табами всегда виден
  }

  async function loadOrders() {
    if (!currentCase?.id || !els.ordersList) return;
    try {
      const rows = await api(`/api/portal/cases/${encodeURIComponent(currentCase.id)}/orders`);
      if (!rows?.length) {
        els.ordersList.innerHTML = "";
        if (els.ordersEmpty) els.ordersEmpty.classList.remove("hidden");
        return;
      }
      if (els.ordersEmpty) els.ordersEmpty.classList.add("hidden");
      els.ordersList.innerHTML = rows
        .map((order) => {
          const title = PACKAGE_LABELS[order.package_code] || order.package_code;
          const canPay = order.status === "pending" || order.status === "awaiting_payment";
          const payBtn = canPay
            ? `<button type="button" class="btn primary pay-btn" data-order="${escapeHtml(order.id)}">Оплатить онлайн</button>`
            : "";
          return `<li><strong>${escapeHtml(title)}</strong><br>${escapeHtml(String(order.amount_rub))} ₽ · ${escapeHtml(order.status)}${payBtn}</li>`;
        })
        .join("");
      els.ordersList.querySelectorAll("button[data-order]").forEach((btn) => {
        btn.addEventListener("click", () => void startPay(btn.getAttribute("data-order")));
      });
    } catch (err) {
      if (els.ordersEmpty) {
        els.ordersEmpty.textContent = err.message || "Не удалось загрузить счета";
        els.ordersEmpty.classList.remove("hidden");
      }
    }
  }

  async function startPay(orderId) {
    if (!currentCase?.id || !orderId) return;
    try {
      setBusy(true);
      const payload = await api(
        `/api/portal/cases/${encodeURIComponent(currentCase.id)}/orders/${encodeURIComponent(orderId)}/pay`,
        {
          method: "POST",
          body: JSON.stringify({ return_channel: "max_miniapp" }),
        },
      );
      if (payload.confirmation_url) {
        window.open(payload.confirmation_url, "_blank", "noopener,noreferrer");
        toast("Открыта оплата ЮKassa");
      } else {
        toast("Платёж создан");
      }
      await loadOrders();
    } catch (err) {
      toast(err.message || "Оплата недоступна");
    } finally {
      setBusy(false);
    }
  }

  async function loadResult() {
    if (!currentCase?.id || !els.resultBody) return;
    try {
      const payload = await api(`/api/portal/cases/${encodeURIComponent(currentCase.id)}/result`);
      const ev = payload.evidence;
      if (!ev) {
        els.resultBody.textContent =
          payload.post_payment_note || "Пока нет подтверждённого результата.";
        return;
      }
      const fee = payload.success_fee || {};
      els.resultBody.innerHTML = [
        `Было: ${ev.monthly_before_rub ?? "—"} ₽`,
        `Стало: ${ev.monthly_after_rub ?? "—"} ₽`,
        `ЕДВ: ${ev.lump_sum_rub ?? "—"} ₽`,
        `Ориентир вознаграждения: ${fee.sf_total ?? "—"} ₽`,
        payload.warning || "",
      ]
        .filter(Boolean)
        .map((line) => `<div>${escapeHtml(String(line))}</div>`)
        .join("");
    } catch (err) {
      els.resultBody.textContent = err.message || "Результат недоступен";
    }
  }

  async function loadMessages() {
    if (!currentCase?.id || !els.messagesList) return;
    try {
      const rows = await api(`/api/portal/cases/${encodeURIComponent(currentCase.id)}/messages`);
      if (!rows?.length) {
        els.messagesList.innerHTML = "";
        if (els.messagesEmpty) els.messagesEmpty.classList.remove("hidden");
        return;
      }
      if (els.messagesEmpty) els.messagesEmpty.classList.add("hidden");
      els.messagesList.innerHTML = rows
        .slice(-20)
        .map((m) => {
          const who = escapeHtml(m.author_kind || "system");
          const body = escapeHtml(m.body || "");
          return `<li><span class="hint">${who}</span><br>${body}</li>`;
        })
        .join("");
    } catch (err) {
      if (els.messagesEmpty) {
        els.messagesEmpty.textContent = err.message || "Сообщения недоступны";
        els.messagesEmpty.classList.remove("hidden");
      }
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!currentCase?.id || !els.messageInput) return;
    const body = els.messageInput.value.trim();
    if (!body) return;
    try {
      setBusy(true);
      await api(`/api/portal/cases/${encodeURIComponent(currentCase.id)}/messages`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      els.messageInput.value = "";
      await loadMessages();
      toast("Сообщение отправлено");
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  }

  function renderList(rows) {
    if (!els.caseList) return;
    if (!rows.length) {
      els.caseList.innerHTML = "<li class='muted'>Дел пока нет — создайте первое.</li>";
    } else {
      els.caseList.innerHTML = rows
        .map((row) => {
          const id = escapeHtml(row.id);
          const st = escapeHtml(row.pipeline_status || "");
          return `<li><button type="button" data-case="${id}" class="linkish">${id.slice(0, 8)}… · ${st}</button></li>`;
        })
        .join("");
      els.caseList.querySelectorAll("button[data-case]").forEach((btn) => {
        btn.addEventListener("click", () => void openCaseById(btn.getAttribute("data-case")));
      });
    }
    show(els.list);
  }

  async function loadLabels() {
    try {
      const meta = await api("/api/portal/meta/status-labels");
      statusLabels = meta.labels || {};
      statusHints = meta.hints || {};
    } catch {
      /* fallback пустой — сервер всё равно шлёт label в detail */
    }
  }

  async function ensureConsent(caseId) {
    await api(`/api/portal/cases/${encodeURIComponent(caseId)}/consents`, {
      method: "POST",
      body: JSON.stringify({ version: "pdn-v1" }),
    });
  }

  async function openCaseById(caseId) {
    const c = await api(`/api/portal/cases/${encodeURIComponent(caseId)}`);
    renderCase(c);
  }

  async function createOrOpenCase(extra = {}) {
    const cases = await api("/api/portal/me/cases");
    if (Array.isArray(cases) && cases.length) {
      if (cases.length === 1) {
        await openCaseById(cases[0].id);
        return;
      }
      renderList(cases);
      return;
    }
    const c = await api("/api/portal/cases", {
      method: "POST",
      body: JSON.stringify({
        full_name: extra.client_name || undefined,
        problem_type: "max_miniapp",
      }),
    });
    if (els.consent?.checked) {
      try {
        await ensureConsent(c.id);
        c.consent_accepted = true;
      } catch (err) {
        console.warn(err);
      }
    }
    renderCase(c);
  }

  async function refreshCase() {
    if (!currentCase?.id) return;
    await openCaseById(currentCase.id);
  }

  async function uploadFile(file) {
    if (!currentCase?.id) throw new Error("Сначала откройте дело");
    if (!currentCase.consent_accepted) {
      await ensureConsent(currentCase.id);
      currentCase.consent_accepted = true;
    }
    const fd = new FormData();
    fd.append("file", file, file.name);
    await api(`/api/portal/cases/${encodeURIComponent(currentCase.id)}/documents`, {
      method: "POST",
      body: fd,
    });
    await refreshCase();
    toast("Документ загружен");
  }

  async function runPipeline() {
    if (!currentCase?.id) return;
    if (!currentCase.consent_accepted) {
      await ensureConsent(currentCase.id);
      currentCase.consent_accepted = true;
    }
    const result = await api(`/api/portal/cases/${encodeURIComponent(currentCase.id)}/run`, {
      method: "POST",
    });
    toast(result.message || "Проверка запрошена");
    await refreshCase();
  }

  async function openWebCabinet() {
    try {
      const body = await api("/api/portal/link/web-from-max", {
        method: "POST",
        body: JSON.stringify({
          max_user_id: maxUserId,
          init_data: window.WebApp?.initData || null,
          preferred_channel: "max_miniapp",
          case_id: currentCase?.id || null,
        }),
      });
      const url = body.cabinet_url || `${cabinetBase}?link_max=${maxUserId}`;
      if (els.btnWeb) els.btnWeb.href = url;
      window.open(url, "_blank", "noopener,noreferrer");
      toast("Откройте веб-кабинет и войдите по коду");
    } catch (err) {
      const fallback = `${cabinetBase}?link_max=${encodeURIComponent(maxUserId || "")}`;
      window.open(fallback, "_blank", "noopener,noreferrer");
      toast(err.message || "Открыт веб-кабинет");
    }
  }

  function initBridge() {
    const wa = window.WebApp;
    if (!wa) return;
    try {
      if (typeof wa.ready === "function") wa.ready();
      if (typeof wa.expand === "function") wa.expand();
      const user = wa.initDataUnsafe?.user;
      if (user?.first_name && els.nameInput) {
        els.nameInput.value = [user.first_name, user.last_name].filter(Boolean).join(" ");
      }
    } catch (err) {
      console.warn("WebApp bridge init failed", err);
    }
  }

  async function bootstrap() {
    initBridge();
    maxUserId = resolveMaxUserId();
    try {
      setBusy(true);
      await loadLabels();
      me = await api("/api/portal/me");
      await api("/api/portal/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ preferred_channel: "max_miniapp" }),
      }).catch(() => null);
      await createOrOpenCase({ client_name: els.nameInput?.value?.trim() });
    } catch (err) {
      console.error(err);
      els.boot.classList.add("hidden");
      show(els.form);
      toast(`API: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  els.btnOpen?.addEventListener("click", async () => {
    const name = els.nameInput.value.trim();
    if (!name) {
      toast("Укажите имя");
      return;
    }
    if (!els.consent.checked) {
      toast("Нужно согласие на обработку ПДн");
      return;
    }
    try {
      setBusy(true);
      await createOrOpenCase({ client_name: name });
      toast("Кабинет открыт");
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  els.btnRefresh?.addEventListener("click", async () => {
    try {
      setBusy(true);
      await refreshCase();
      toast("Обновлено");
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  els.btnRun?.addEventListener("click", async () => {
    try {
      setBusy(true);
      await runPipeline();
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  els.fileInput?.addEventListener("change", async () => {
    const file = els.fileInput.files?.[0];
    els.fileInput.value = "";
    if (!file) return;
    try {
      setBusy(true);
      await uploadFile(file);
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  if (els.btnWeb) {
    els.btnWeb.addEventListener("click", (event) => {
      event.preventDefault();
      void openWebCabinet();
    });
  }
  const btnWebList = document.getElementById("btn-web-from-list");
  if (btnWebList) {
    btnWebList.addEventListener("click", (event) => {
      event.preventDefault();
      void openWebCabinet();
    });
  }

  els.btnChat?.addEventListener("click", (event) => {
    event.preventDefault();
    window.open(botUrl, "_blank", "noopener,noreferrer");
  });

  document.querySelectorAll("#case-tabs .tab").forEach((btn) => {
    btn.addEventListener("click", () => setTab(btn.getAttribute("data-tab") || "case"));
  });

  els.messageForm?.addEventListener("submit", (event) => void sendMessage(event));

  // deep-link ?view=payments|result|chat
  const initialView = new URLSearchParams(location.search).get("view");
  if (initialView && ["pay", "payments", "result", "chat"].includes(initialView)) {
    setTimeout(() => setTab(initialView === "payments" ? "pay" : initialView), 800);
  }

  els.btnBackList?.addEventListener("click", async () => {
    try {
      const cases = await api("/api/portal/me/cases");
      renderList(cases || []);
    } catch (err) {
      toast(err.message);
    }
  });

  els.btnNewCase?.addEventListener("click", async () => {
    try {
      setBusy(true);
      const c = await api("/api/portal/cases", {
        method: "POST",
        body: JSON.stringify({ full_name: me?.full_name, problem_type: "max_miniapp" }),
      });
      if (els.consent?.checked !== false) {
        await ensureConsent(c.id).catch(() => null);
        c.consent_accepted = true;
      }
      renderCase(c);
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  bootstrap();
})();
