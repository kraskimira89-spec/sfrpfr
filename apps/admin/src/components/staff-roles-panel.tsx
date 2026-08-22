"use client";

import { labelStaffRole, labelStaffStatus } from "@/lib/ui-labels";
import { FormEvent, useEffect, useMemo, useState } from "react";

export type StaffMember = {
  user_id: string;
  email?: string | null;
  display_name?: string | null;
  role: string;
  status: string;
  last_sign_in_at?: string | null;
  invited_at?: string | null;
  invite_expires_at?: string | null;
  created_at?: string | null;
};

export type StaffAuditRow = {
  id: number;
  at: string;
  actor_id?: string | null;
  event: string;
  old_role?: string | null;
  new_role?: string | null;
  old_status?: string | null;
  new_status?: string | null;
  result: string;
};

type Props = {
  token: string;
  meUserId: string;
  apiFetch: <T>(path: string, token: string, init?: RequestInit) => Promise<T>;
  onNotice: (text: string) => void;
};

function formatWhen(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function memberTitle(row: StaffMember): string {
  return (row.display_name || row.email || "Сотрудник").trim();
}

export function StaffRolesPanel({ token, meUserId, apiFetch, onNotice }: Props) {
  const [rows, setRows] = useState<StaffMember[]>([]);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("active");
  const [selected, setSelected] = useState<StaffMember | null>(null);
  const [audit, setAudit] = useState<StaffAuditRow[]>([]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("operator");
  const [confirmAdmin, setConfirmAdmin] = useState(false);
  const [editRole, setEditRole] = useState("operator");
  const [editStatus, setEditStatus] = useState("active");

  async function reload() {
    setBusy(true);
    try {
      let data: StaffMember[];
      try {
        data = await apiFetch<StaffMember[]>("/api/portal/admin/staff", token);
      } catch {
        data = await apiFetch<StaffMember[]>("/api/portal/admin/staff-roles", token);
      }
      setRows(
        data.map((row) => ({
          ...row,
          status: row.status || "active",
        })),
      );
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Не удалось загрузить сотрудников");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        let data: StaffMember[];
        try {
          data = await apiFetch<StaffMember[]>("/api/portal/admin/staff", token);
        } catch {
          data = await apiFetch<StaffMember[]>("/api/portal/admin/staff-roles", token);
        }
        if (cancelled) return;
        setRows(
          data.map((row) => ({
            ...row,
            status: row.status || "active",
          })),
        );
      } catch (err) {
        if (!cancelled) {
          onNotice(err instanceof Error ? err.message : "Не удалось загрузить сотрудников");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((row) => {
      if (roleFilter !== "all" && row.role !== roleFilter) return false;
      if (statusFilter !== "all" && (row.status || "active") !== statusFilter) return false;
      if (!needle) return true;
      const hay = `${row.display_name || ""} ${row.email || ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [rows, q, roleFilter, statusFilter]);

  async function openMember(row: StaffMember) {
    setSelected(row);
    setEditRole(row.role);
    setEditStatus(row.status || "active");
    setConfirmAdmin(false);
    try {
      const items = await apiFetch<StaffAuditRow[]>(
        `/api/portal/admin/staff/${row.user_id}/audit`,
        token,
      );
      setAudit(items);
    } catch {
      setAudit([]);
    }
  }

  async function submitInvite(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await apiFetch("/api/portal/admin/staff/invites", token, {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail.trim(),
          display_name: inviteName.trim(),
          role: inviteRole,
          confirm_admin_grant: inviteRole === "admin" ? confirmAdmin : false,
        }),
      });
      onNotice("Приглашение отправлено");
      setInviteOpen(false);
      setInviteEmail("");
      setInviteName("");
      setInviteRole("operator");
      setConfirmAdmin(false);
      await reload();
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Ошибка приглашения");
    } finally {
      setBusy(false);
    }
  }

  async function saveMember() {
    if (!selected) return;
    if (selected.user_id === meUserId) {
      onNotice("Нельзя менять свою роль или статус");
      return;
    }
    const grantingAdmin =
      editRole === "admin" &&
      (selected.role !== "admin" || (selected.status || "active") !== "active");
    if (grantingAdmin && !confirmAdmin) {
      onNotice("Подтвердите назначение роли администратора");
      return;
    }
    setBusy(true);
    try {
      const updated = await apiFetch<StaffMember>(`/api/portal/admin/staff/${selected.user_id}`, token, {
        method: "PATCH",
        body: JSON.stringify({
          role: editRole,
          status: editStatus,
          confirm_admin_grant: grantingAdmin ? confirmAdmin : false,
        }),
      });
      onNotice("Доступ обновлён");
      setSelected(updated);
      await reload();
      await openMember(updated);
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Ошибка сохранения");
    } finally {
      setBusy(false);
    }
  }

  async function revokeInvite(row: StaffMember) {
    if (!window.confirm(`Отозвать приглашение для ${memberTitle(row)}?`)) return;
    setBusy(true);
    try {
      await apiFetch(`/api/portal/admin/staff/invites/${row.user_id}/revoke`, token, {
        method: "POST",
      });
      onNotice("Приглашение отозвано");
      setSelected(null);
      await reload();
    } catch (err) {
      onNotice(err instanceof Error ? err.message : "Ошибка отзыва");
    } finally {
      setBusy(false);
    }
  }

  async function copyUserId(userId: string) {
    try {
      await navigator.clipboard.writeText(userId);
      onNotice("ID скопирован");
    } catch {
      onNotice(userId);
    }
  }

  return (
    <section className="stack staff-roles">
      <header className="staff-roles-header">
        <div>
          <h1>Роли и доступ сотрудников</h1>
          <p className="lead-compact">
            Управляйте доступом к делам, документам, оплатам и аналитике. Изменения ролей
            фиксируются в журнале безопасности.
          </p>
        </div>
        <button type="button" className="primary" onClick={() => setInviteOpen(true)}>
          + Пригласить сотрудника
        </button>
      </header>

      <div className="staff-filters">
        <input
          placeholder="Поиск по имени или e-mail"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
          <option value="all">Все роли</option>
          <option value="admin">{labelStaffRole("admin")}</option>
          <option value="expert">{labelStaffRole("expert")}</option>
          <option value="operator">{labelStaffRole("operator")}</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">Все статусы</option>
          <option value="active">{labelStaffStatus("active")}</option>
          <option value="invited">{labelStaffStatus("invited")}</option>
          <option value="suspended">{labelStaffStatus("suspended")}</option>
          <option value="archived">{labelStaffStatus("archived")}</option>
        </select>
      </div>

      <p className="hint">Сотрудники ({filtered.length})</p>

      {filtered.length === 0 ? (
        <div className="card empty-state">
          <p>Сотрудники ещё не приглашены.</p>
          <button type="button" className="primary" onClick={() => setInviteOpen(true)}>
            Пригласить сотрудника
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table staff-table">
            <thead>
              <tr>
                <th>Сотрудник</th>
                <th>E-mail</th>
                <th>Роль</th>
                <th>Статус</th>
                <th>Последний вход</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.user_id}>
                  <td>
                    <button type="button" className="linkish" onClick={() => void openMember(row)}>
                      {memberTitle(row)}
                    </button>
                  </td>
                  <td>{row.email || "—"}</td>
                  <td>{labelStaffRole(row.role)}</td>
                  <td>{labelStaffStatus(row.status || "active")}</td>
                  <td>{formatWhen(row.last_sign_in_at)}</td>
                  <td>
                    <button type="button" onClick={() => void openMember(row)}>
                      Изменить
                    </button>
                    {row.status === "invited" && (
                      <button type="button" onClick={() => void revokeInvite(row)}>
                        Отозвать
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <details className="card">
        <summary>Роли и права (справка P0)</summary>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Возможность</th>
                <th>Админ</th>
                <th>Специалист</th>
                <th>Оператор</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Все дела</td>
                <td>✓</td>
                <td>Назначенные</td>
                <td>✓</td>
              </tr>
              <tr>
                <td>Документы / OCR</td>
                <td>✓</td>
                <td>✓</td>
                <td>—</td>
              </tr>
              <tr>
                <td>Финансы / счета</td>
                <td>✓</td>
                <td>—</td>
                <td>—</td>
              </tr>
              <tr>
                <td>Управление ролями</td>
                <td>✓</td>
                <td>—</td>
                <td>—</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>

      {inviteOpen && (
        <div className="finance-modal card">
          <h2>Пригласить сотрудника</h2>
          <form className="stack" onSubmit={submitInvite}>
            <label>
              Рабочий e-mail *
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </label>
            <label>
              Имя и фамилия *
              <input
                required
                value={inviteName}
                onChange={(e) => setInviteName(e.target.value)}
              />
            </label>
            <label>
              Роль *
              <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
                <option value="operator">{labelStaffRole("operator")}</option>
                <option value="expert">{labelStaffRole("expert")}</option>
                <option value="admin">{labelStaffRole("admin")}</option>
              </select>
            </label>
            {inviteRole === "admin" && (
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={confirmAdmin}
                  onChange={(e) => setConfirmAdmin(e.target.checked)}
                />
                Подтверждаю выдачу прав администратора
              </label>
            )}
            <div className="inline-form">
              <button type="submit" className="primary" disabled={busy}>
                Отправить приглашение
              </button>
              <button type="button" onClick={() => setInviteOpen(false)}>
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {selected && (
        <aside className="card staff-drawer">
          <header className="staff-drawer-head">
            <h2>{memberTitle(selected)}</h2>
            <button type="button" onClick={() => setSelected(null)}>
              Закрыть
            </button>
          </header>
          <p>
            E-mail: {selected.email || "—"}
            <br />
            Статус: {labelStaffStatus(selected.status || "active")}
            <br />
            Роль: {labelStaffRole(selected.role)}
            <br />
            Последний вход: {formatWhen(selected.last_sign_in_at)}
          </p>

          {selected.user_id !== meUserId ? (
            <div className="stack">
              <label>
                Роль
                <select value={editRole} onChange={(e) => setEditRole(e.target.value)}>
                  <option value="operator">{labelStaffRole("operator")}</option>
                  <option value="expert">{labelStaffRole("expert")}</option>
                  <option value="admin">{labelStaffRole("admin")}</option>
                </select>
              </label>
              <label>
                Статус
                <select value={editStatus} onChange={(e) => setEditStatus(e.target.value)}>
                  <option value="active">{labelStaffStatus("active")}</option>
                  <option value="suspended">{labelStaffStatus("suspended")}</option>
                  <option value="archived">{labelStaffStatus("archived")}</option>
                </select>
              </label>
              {editRole === "admin" && selected.role !== "admin" && (
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={confirmAdmin}
                    onChange={(e) => setConfirmAdmin(e.target.checked)}
                  />
                  Подтверждаю назначение администратора
                </label>
              )}
              <button type="button" className="primary" disabled={busy} onClick={() => void saveMember()}>
                Сохранить изменения
              </button>
              {selected.status === "invited" && (
                <button type="button" onClick={() => void revokeInvite(selected)}>
                  Отозвать приглашение
                </button>
              )}
            </div>
          ) : (
            <p className="hint">Свою роль через интерфейс менять нельзя.</p>
          )}

          <details>
            <summary>Служебные сведения</summary>
            <p className="hint">Технический идентификатор (не показывать в переписке с клиентом).</p>
            <code className="mono">{selected.user_id}</code>
            <button type="button" onClick={() => void copyUserId(selected.user_id)}>
              Копировать ID
            </button>
          </details>

          <h3>Журнал последних действий</h3>
          {audit.length === 0 ? (
            <p className="hint">Записей пока нет</p>
          ) : (
            <ul className="plain-list">
              {audit.map((item) => (
                <li key={item.id}>
                  {formatWhen(item.at)} — {item.event}
                  {item.old_role || item.new_role
                    ? `: ${item.old_role || "—"} → ${item.new_role || "—"}`
                    : ""}
                  {item.result !== "success" ? ` (${item.result})` : ""}
                </li>
              ))}
            </ul>
          )}
        </aside>
      )}
    </section>
  );
}
