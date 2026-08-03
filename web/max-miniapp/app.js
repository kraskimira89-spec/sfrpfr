(() => {
  const cfg = window.SFRFR_CONFIG || {};
  const apiBase = (cfg.apiBase || "").replace(/\/$/, "");
  const cabinetBase = (cfg.cabinetUrl || "https://cabinet.proverkastaza.ru/").replace(
    /\/?$/,
    "/",
  );
  const botUrl = cfg.maxBotUrl || "https://max.ru/";
  const CONSENT_VERSION = "pdn-consent-2026-08-03";

  const PIPELINE_STEPS = [
    "intake",
    "documents_received",
    "ocr_done",
    "classified",
    "extracted",
    "audited",
    "draft_ready",
    "human_review",
    "completed",
  ];

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
    caseConsent: document.getElementById("case-consent"),
    caseConsentCheck: document.getElementById("case-consent-check"),
    btnCaseConsent: document.getElementById("btn-case-consent"),
    caseChecklist: document.getElementById("case-checklist"),
    caseChecklistList: document.getElementById("case-checklist-list"),
    checklistEmpty: document.getElementById("checklist-empty"),
    caseDraft: document.getElementById("case-draft"),
    caseDraftBody: document.getElementById("case-draft-body"),
    draftEmpty: document.getElementById("draft-empty"),
    caseSubmitHint: document.getElementById("case-submit-hint"),
    caseWarning: document.getElementById("case-warning"),
    fileInput: document.getElementById("file-input"),
    fileInputDocs: document.getElementById("file-input-docs"),
    btnRefresh: document.getElementById("btn-refresh"),
    btnRun: document.getElementById("btn-run"),
    btnWeb: document.getElementById("btn-web-cabinet"),
    btnChat: document.getElementById("btn-chat"),
    btnBackList: document.getElementById("btn-back-list"),
    btnBack: document.getElementById("btn-back"),
    btnHomeCases: document.getElementById("btn-home-cases"),
    bottomNav: document.getElementById("bottom-nav"),
    btnMenu: document.getElementById("btn-menu"),
    drawer: document.getElementById("drawer"),
    drawerBackdrop: document.getElementById("drawer-backdrop"),
    stepsList: document.getElementById("steps-list"),
    appbarSub: document.getElementById("appbar-sub"),
    drawerWeb: document.getElementById("drawer-web"),
    drawerChatBot: document.getElementById("drawer-chat-bot"),
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
  let currentView = "overview";

  function show(el) {
    [els.boot, els.form, els.list, els.panel].forEach((p) => p && p.classList.add("hidden"));
    el.classList.remove("hidden");
    const inApp = el === els.list || el === els.panel;
    els.bottomNav?.classList.toggle("hidden", !inApp);
    els.btnBack?.classList.toggle("hidden", el !== els.panel);
    els.btnHomeCases?.classList.toggle("hidden", !inApp);
    document.body.classList.toggle("has-bottom-nav", inApp);
  }

  function syncNavActive(view) {
    const key = view === "pay" ? "pay" : view;
    document.querySelectorAll("#drawer-nav .nav-item, #case-tabs .case-tab, #bottom-nav .bottom-nav__item").forEach((btn) => {
      const v = btn.getAttribute("data-view");
      const active =
        v === key ||
        (key === "list" && v === "list") ||
        (["overview", "docs", "checklist", "draft", "pay", "result", "chat"].includes(key) &&
          v === key);
      btn.classList.toggle("active", active);
    });
    // На нижней панели «Обзор» активен и для второстепенных вкладок без своей кнопки
    document.querySelectorAll("#bottom-nav .bottom-nav__item").forEach((btn) => {
      const v = btn.getAttribute("data-view");
      if (v === "overview") {
        btn.classList.toggle(
          "active",
          key === "overview" ||
            ["checklist", "draft", "pay", "result"].includes(key),
        );
      } else if (v === "docs") {
        btn.classList.toggle("active", key === "docs");
      } else if (v === "chat") {
        btn.classList.toggle("active", key === "chat");
      } else if (v === "list") {
        btn.classList.toggle("active", key === "list");
      }
    });
  }

  function setMenuOpen(open) {
    els.drawer?.classList.toggle("open", open);
    els.drawerBackdrop?.classList.toggle("hidden", !open);
    document.body.classList.toggle("menu-open", open);
    if (els.btnMenu) els.btnMenu.setAttribute("aria-expanded", open ? "true" : "false");
    if (els.drawer) els.drawer.setAttribute("aria-hidden", open ? "false" : "true");
  }

  function renderSteps(status) {
    if (!els.stepsList) return;
    const cur = status === "failed" ? "failed" : status || "intake";
    const idx = PIPELINE_STEPS.indexOf(cur);
    const labels = { ...statusLabels };
    if (!Object.keys(labels).length) {
      // Синхронно с shared/status-labels.json и /api/portal/meta/status-labels
      Object.assign(labels, {
        intake: "Приём данных",
        documents_received: "Документы получены",
        ocr_done: "Текст распознан",
        classified: "Документы классифицированы",
        extracted: "Периоды извлечены",
        audited: "Сверка завершена",
        draft_ready: "Черновик готов",
        human_review: "На проверке специалиста",
        completed: "Завершено",
        failed: "Ошибка",
      });
    }
    const steps = cur === "failed" ? [...PIPELINE_STEPS.slice(0, -1), "failed"] : PIPELINE_STEPS;
    els.stepsList.innerHTML = steps
      .map((key, i) => {
        let cls = "future";
        if (cur === "failed" && key === "failed") cls = "current";
        else if (idx >= 0) {
          if (i < idx) cls = "done";
          else if (i === idx) cls = "current";
        } else if (key === cur) cls = "current";
        const title = escapeHtml(labels[key] || key);
        return `<li class="${cls}"><span class="dot" aria-hidden="true"></span><span>${title}</span></li>`;
      })
      .join("");
  }

  function setView(name) {
    const view = name === "payments" ? "pay" : name;
    if (view === "list") {
      setMenuOpen(false);
      void (async () => {
        try {
          const cases = await api("/api/portal/me/cases");
          renderList(cases || []);
          syncNavActive("list");
        } catch (err) {
          toast(err.message);
        }
      })();
      return;
    }
    if (!currentCase?.id && view !== "overview") {
      // Нет открытого дела — сначала список
      void setView("list");
      return;
    }
    currentView = view;
    if (els.panel && els.panel.classList.contains("hidden")) {
      show(els.panel);
    }
    document.querySelectorAll("#panel-case .view").forEach((node) => {
      node.classList.toggle("hidden", node.id !== `view-${view}`);
    });
    syncNavActive(view);
    if (els.appbarSub) {
      const titles = {
        overview: "Обзор",
        docs: "Документы",
        checklist: "Чек-лист",
        draft: "Черновик",
        pay: "Оплаты",
        result: "Результат",
        chat: "Сообщения",
      };
      els.appbarSub.textContent = titles[view] || "Кабинет";
    }
    setMenuOpen(false);
    if (view === "pay") void loadOrders();
    if (view === "result") void loadResult();
    if (view === "chat") void loadMessages();
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
    if (els.fileInputDocs) els.fileInputDocs.disabled = busy;
  }

  function authHeaders(extra = {}) {
    const headers = { ...extra };
    const initData = window.WebApp?.initData || "";
    if (initData) headers["X-MAX-InitData"] = initData;
    else if (maxUserId) headers["X-MAX-User-Id"] = maxUserId;
    return headers;
  }

  async function api(path, options = {}) {
    if (!apiBase) {
      throw new Error("API не настроен (config.js). Обновите мини-приложение.");
    }
    const headers = authHeaders(options.headers || {});
    if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    let res;
    try {
      res = await fetch(`${apiBase}${path}`, { ...options, headers });
    } catch (err) {
      const reason = err instanceof Error ? err.message : String(err);
      throw new Error(
        `Нет связи с API (${apiBase}). Проверьте интернет и откройте мини-приложение заново. ${reason}`,
      );
    }
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

  /** Короткий понятный номер дела из UUID (стабильный). */
  function caseNumber(caseId) {
    const hex = String(caseId || "").replace(/-/g, "").slice(-5);
    const n = parseInt(hex, 16);
    if (!Number.isFinite(n) || n <= 0) return "—";
    return String(n);
  }

  function caseTitle(caseId) {
    return `Дело ПС-${caseNumber(caseId)}`;
  }

  function statusTitle(status) {
    const key = status || "intake";
    return statusLabels[key] || key;
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
    els.caseId.textContent = caseTitle(c.id);
    if (els.caseName) els.caseName.textContent = c.client_name;
    els.caseDocs.textContent = String(c.document_count);
    renderSteps(c.status);
    if (els.appbarSub && currentView === "overview") {
      els.appbarSub.textContent = c.status_label || "Обзор";
    }

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

    if (els.caseConsent) {
      els.caseConsent.classList.toggle("hidden", Boolean(c.consent_accepted));
    }
    if (els.caseConsentCheck && !c.consent_accepted) {
      els.caseConsentCheck.checked = false;
    }
    if (els.btnCaseConsent) {
      els.btnCaseConsent.disabled = true;
    }

    const checklist = Array.isArray(c.checklist_items) ? c.checklist_items : [];
    if (els.caseChecklistList) {
      if (checklist.length) {
        els.caseChecklistList.innerHTML = checklist
          .slice(0, 12)
          .map((item) => {
            const title = escapeHtml(item.title || "пункт");
            const st = escapeHtml(item.status || "");
            return `<li><strong>${title}</strong> <span class="hint">${st}</span></li>`;
          })
          .join("");
        if (els.checklistEmpty) els.checklistEmpty.classList.add("hidden");
      } else {
        els.caseChecklistList.innerHTML = "";
        if (els.checklistEmpty) els.checklistEmpty.classList.remove("hidden");
      }
    }

    const draft = c.draft;
    if (els.caseDraftBody) {
      if (draft && (draft.body || draft.title)) {
        els.caseDraftBody.textContent = [draft.title, draft.body].filter(Boolean).join("\n\n");
        els.caseDraftBody.classList.remove("hidden");
        if (els.draftEmpty) els.draftEmpty.classList.add("hidden");
      } else {
        els.caseDraftBody.textContent = "";
        els.caseDraftBody.classList.add("hidden");
        if (els.draftEmpty) els.draftEmpty.classList.remove("hidden");
      }
    }

    if (els.caseSubmitHint && c.submission_instruction) {
      els.caseSubmitHint.textContent = c.submission_instruction;
    }

    const payUrl = `${cabinetBase}cases/${encodeURIComponent(c.id)}?view=payments`;
    const resultUrl = `${cabinetBase}cases/${encodeURIComponent(c.id)}?view=result`;
    if (els.payCabinetLink) els.payCabinetLink.href = payUrl;
    if (els.resultCabinetLink) els.resultCabinetLink.href = resultUrl;

    show(els.panel);
    setView(currentView === "list" ? "overview" : currentView);
    syncNavActive(currentView === "list" ? "overview" : currentView);
    void loadOrders();
    void loadResult();
    void loadMessages();
  }

  function setTab(name) {
    setView(name === "case" ? "overview" : name);
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
          const title = escapeHtml(caseTitle(row.id));
          const st = escapeHtml(statusTitle(row.pipeline_status || row.status));
          return `<li><button type="button" data-case="${id}" class="linkish">${title} · ${st}</button></li>`;
        })
        .join("");
      els.caseList.querySelectorAll("button[data-case]").forEach((btn) => {
        btn.addEventListener("click", () => void openCaseById(btn.getAttribute("data-case")));
      });
    }
    show(els.list);
    if (els.appbarSub) els.appbarSub.textContent = "Мои дела";
    syncNavActive("list");
    setMenuOpen(false);
  }

  async function loadLabels() {
    try {
      const meta = await api("/api/portal/meta/status-labels");
      statusLabels = meta.labels || {};
      statusHints = meta.hints || {};
      renderSteps(currentCase?.status || "intake");
    } catch {
      /* fallback пустой — сервер всё равно шлёт label в detail */
      renderSteps(currentCase?.status || "intake");
    }
  }

  async function ensureConsent(caseId) {
    await api(`/api/portal/cases/${encodeURIComponent(caseId)}/consents`, {
      method: "POST",
      body: JSON.stringify({ version: CONSENT_VERSION }),
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
      throw new Error("Сначала отдельно подтвердите согласие на обработку персональных данных");
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
      throw new Error("Сначала отдельно подтвердите согласие на обработку персональных данных");
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
      const url =
        body.cabinet_url ||
        (currentCase?.id
          ? `${cabinetBase}cases/${encodeURIComponent(currentCase.id)}?link_max=${maxUserId}`
          : `${cabinetBase}?link_max=${maxUserId}`);
      if (els.btnWeb) els.btnWeb.href = url;
      window.open(url, "_blank", "noopener,noreferrer");
      toast("Откройте веб-кабинет и войдите по коду");
    } catch (err) {
      const fallback = currentCase?.id
        ? `${cabinetBase}cases/${encodeURIComponent(currentCase.id)}?link_max=${encodeURIComponent(maxUserId || "")}`
        : `${cabinetBase}?link_max=${encodeURIComponent(maxUserId || "")}`;
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

  els.caseConsentCheck?.addEventListener("change", () => {
    if (els.btnCaseConsent) {
      els.btnCaseConsent.disabled = !els.caseConsentCheck.checked;
    }
  });

  els.btnCaseConsent?.addEventListener("click", async () => {
    if (!currentCase?.id || !els.caseConsentCheck?.checked) return;
    try {
      setBusy(true);
      await ensureConsent(currentCase.id);
      toast("Согласие зафиксировано");
      await refreshCase();
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

  els.fileInputDocs?.addEventListener("change", async () => {
    const file = els.fileInputDocs.files?.[0];
    els.fileInputDocs.value = "";
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

  els.btnMenu?.addEventListener("click", () => {
    const open = !els.drawer?.classList.contains("open");
    setMenuOpen(open);
  });
  els.drawerBackdrop?.addEventListener("click", () => setMenuOpen(false));

  function goNav(view) {
    setView(view || "overview");
  }

  document.querySelectorAll("#drawer-nav .nav-item").forEach((btn) => {
    btn.addEventListener("click", () => goNav(btn.getAttribute("data-view") || "overview"));
  });
  document.querySelectorAll("#case-tabs .case-tab").forEach((btn) => {
    btn.addEventListener("click", () => goNav(btn.getAttribute("data-view") || "overview"));
  });
  document.querySelectorAll("#bottom-nav .bottom-nav__item").forEach((btn) => {
    btn.addEventListener("click", () => goNav(btn.getAttribute("data-view") || "overview"));
  });

  async function goToCasesList() {
    try {
      const cases = await api("/api/portal/me/cases");
      renderList(cases || []);
    } catch (err) {
      toast(err.message);
    }
  }

  els.btnBack?.addEventListener("click", () => void goToCasesList());
  els.btnHomeCases?.addEventListener("click", () => void goToCasesList());
  els.btnBackList?.addEventListener("click", () => void goToCasesList());

  if (els.drawerWeb) {
    els.drawerWeb.addEventListener("click", (event) => {
      event.preventDefault();
      setMenuOpen(false);
      void openWebCabinet();
    });
  }
  if (els.drawerChatBot) {
    els.drawerChatBot.href = botUrl;
    els.drawerChatBot.addEventListener("click", () => setMenuOpen(false));
  }

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

  els.messageForm?.addEventListener("submit", (event) => void sendMessage(event));

  // deep-link ?view=payments|result|chat|docs|checklist|draft
  const initialView = new URLSearchParams(location.search).get("view");
  if (
    initialView &&
    ["pay", "payments", "result", "chat", "docs", "checklist", "draft", "overview"].includes(
      initialView,
    )
  ) {
    setTimeout(() => setView(initialView === "payments" ? "pay" : initialView), 800);
  }

  els.btnNewCase?.addEventListener("click", async () => {
    try {
      setBusy(true);
      const c = await api("/api/portal/cases", {
        method: "POST",
        body: JSON.stringify({ full_name: me?.full_name, problem_type: "max_miniapp" }),
      });
      renderCase(c);
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  bootstrap();
})();
