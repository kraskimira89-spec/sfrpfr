(() => {
  const cfg = window.SFRFR_CONFIG || {};
  const apiBase = (cfg.apiBase || "").replace(/\/$/, "");

  const STATUS_LABELS = {
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
  };

  const STATUS_HINTS = {
    intake: "Загрузите сканы ИЛС и трудовой книжки.",
    documents_received: "Документы приняты. Можно запустить проверку.",
    ocr_done: "Текст распознан, идёт классификация.",
    classified: "Типы документов определены.",
    extracted: "Периоды собраны, выполняется сверка.",
    audited: "Найдены расхождения — готовим черновик.",
    draft_ready: "Черновик заявления готов к проверке.",
    human_review: "Ждите ответа специалиста в чате бота.",
    completed: "Дело закрыто.",
    failed: "Смотрите текст ошибки ниже.",
  };

  const els = {
    boot: document.getElementById("panel-boot"),
    form: document.getElementById("panel-form"),
    panel: document.getElementById("panel-case"),
    nameInput: document.getElementById("client-name"),
    snilsInput: document.getElementById("snils-masked"),
    consent: document.getElementById("consent"),
    btnOpen: document.getElementById("btn-open"),
    status: document.getElementById("case-status"),
    statusHint: document.getElementById("case-status-hint"),
    caseId: document.getElementById("case-id"),
    caseName: document.getElementById("case-name"),
    caseDocs: document.getElementById("case-docs"),
    caseOcr: document.getElementById("case-ocr"),
    caseError: document.getElementById("case-error"),
    caseFindings: document.getElementById("case-findings"),
    fileInput: document.getElementById("file-input"),
    btnRefresh: document.getElementById("btn-refresh"),
    btnRun: document.getElementById("btn-run"),
    toast: document.getElementById("toast"),
  };

  let currentCase = null;
  let maxUserId = null;

  function show(el) {
    els.boot.classList.add("hidden");
    els.form.classList.add("hidden");
    els.panel.classList.add("hidden");
    el.classList.remove("hidden");
  }

  function toast(msg) {
    els.toast.textContent = msg;
    els.toast.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => els.toast.classList.add("hidden"), 3500);
  }

  function setBusy(busy) {
    [els.btnOpen, els.btnRefresh, els.btnRun].forEach((b) => {
      if (b) b.disabled = busy;
    });
    els.fileInput.disabled = busy;
  }

  async function api(path, options = {}) {
    const res = await fetch(`${apiBase}${path}`, options);
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

  function renderCase(c) {
    currentCase = c;
    els.status.textContent = STATUS_LABELS[c.status] || c.status;
    els.statusHint.textContent = STATUS_HINTS[c.status] || "";
    els.caseId.textContent = c.id;
    els.caseName.textContent = c.client_name;
    els.caseDocs.textContent = String(c.document_count ?? 0);
    els.caseOcr.textContent = String(c.ocr_count ?? 0);

    if (c.error) {
      els.caseError.textContent = c.error;
      els.caseError.classList.remove("hidden");
    } else {
      els.caseError.classList.add("hidden");
    }

    const findings = Array.isArray(c.findings) ? c.findings : [];
    if (findings.length) {
      els.caseFindings.innerHTML = findings
        .slice(0, 5)
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

    show(els.panel);
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

  async function openCase(extra = {}) {
    const payload = {
      max_user_id: maxUserId,
      consent_given: true,
      snils_masked: "***-***-*** **",
      ...extra,
    };
    const c = await api("/api/cases/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    localStorage.setItem("sfrfr_case_id", c.id);
    renderCase(c);
    return c;
  }

  async function refreshCase() {
    if (!currentCase?.id) return;
    const c = await api(`/api/cases/${encodeURIComponent(currentCase.id)}`);
    renderCase(c);
  }

  async function uploadFile(file) {
    if (!currentCase?.id) throw new Error("Сначала откройте дело");
    const fd = new FormData();
    fd.append("case_id", currentCase.id);
    fd.append("file", file, file.name);
    const c = await api("/api/documents/upload", { method: "POST", body: fd });
    renderCase(c);
    toast("Документ загружен");
  }

  async function runPipeline() {
    if (!currentCase?.id) return;
    const c = await api(`/api/cases/${encodeURIComponent(currentCase.id)}/run`, {
      method: "POST",
    });
    renderCase(c);
    toast("Проверка запущена");
  }

  function initBridge() {
    const wa = window.WebApp;
    if (!wa) return;
    try {
      if (typeof wa.ready === "function") wa.ready();
      if (typeof wa.expand === "function") wa.expand();
      if (wa.BackButton && typeof wa.BackButton.show === "function") {
        wa.BackButton.show();
        wa.BackButton.onClick(() => {
          if (typeof wa.close === "function") wa.close();
        });
      }
      const user = wa.initDataUnsafe?.user;
      if (user?.first_name && els.nameInput) {
        const full = [user.first_name, user.last_name].filter(Boolean).join(" ");
        els.nameInput.value = full;
      }
    } catch (err) {
      console.warn("WebApp bridge init failed", err);
    }
  }

  async function bootstrap() {
    initBridge();
    maxUserId = resolveMaxUserId();
    const bridgeName = els.nameInput.value.trim() || undefined;

    try {
      setBusy(true);
      // Есть дело у MAX-пользователя → сразу кабинет; иначе создаём
      await openCase({ client_name: bridgeName });
    } catch (err) {
      console.error(err);
      els.boot.classList.add("hidden");
      show(els.form);
      toast(`API: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  els.btnOpen.addEventListener("click", async () => {
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
      await openCase({
        client_name: name,
        snils_masked: els.snilsInput.value.trim() || "***-***-*** **",
        consent_given: true,
      });
      toast("Кабинет открыт");
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  els.btnRefresh.addEventListener("click", async () => {
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

  els.btnRun.addEventListener("click", async () => {
    try {
      setBusy(true);
      await runPipeline();
    } catch (err) {
      toast(err.message);
    } finally {
      setBusy(false);
    }
  });

  els.fileInput.addEventListener("change", async () => {
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

  bootstrap();
})();
