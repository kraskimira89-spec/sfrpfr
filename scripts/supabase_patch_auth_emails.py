#!/usr/bin/env python3
"""Применить русские шаблоны Auth-писем в Supabase Cloud (Management API).

Нужен Personal Access Token:
  https://supabase.com/dashboard/account/tokens
Положить в secrets/supabase-access.env:
  SUPABASE_ACCESS_TOKEN=sbp_...
  SUPABASE_PROJECT_REF=frualvycousvvyjivybu
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "supabase" / "templates"
SECRETS = ROOT / "secrets" / "supabase-access.env"
DEFAULT_REF = "frualvycousvvyjivybu"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _html(name: str) -> str:
    path = TEMPLATES / name
    text = path.read_text(encoding="utf-8").strip()
    # Management API принимает HTML одной строкой
    return text


def main() -> int:
    _load_dotenv(SECRETS)
    token = (os.environ.get("SUPABASE_ACCESS_TOKEN") or "").strip()
    ref = (os.environ.get("SUPABASE_PROJECT_REF") or DEFAULT_REF).strip()
    if not token:
        print(
            "Нет SUPABASE_ACCESS_TOKEN.\n"
            "1) Создайте токен: https://supabase.com/dashboard/account/tokens\n"
            "2) Запишите в secrets/supabase-access.env:\n"
            "   SUPABASE_ACCESS_TOKEN=sbp_...\n"
            "   SUPABASE_PROJECT_REF=frualvycousvvyjivybu\n"
            "3) Запустите снова: python scripts/supabase_patch_auth_emails.py",
            file=sys.stderr,
        )
        return 2

    payload = {
        "mailer_subjects_confirmation": "Код для кабинета «Проверка стажа»: {{ .Token }}",
        "mailer_templates_confirmation_content": _html("confirmation.html"),
        "mailer_subjects_magic_link": "Код для входа в «Проверка стажа»: {{ .Token }}",
        "mailer_templates_magic_link_content": _html("magic_link.html"),
        "mailer_subjects_recovery": "Восстановление пароля — «Проверка стажа»",
        "mailer_templates_recovery_content": _html("recovery.html"),
        "mailer_subjects_email_change": "Подтвердите новый email — «Проверка стажа»",
        "mailer_templates_email_change_content": (
            "<h2>Подтвердите новый email</h2>"
            "<p>Здравствуйте!</p>"
            "<p>Чтобы подтвердить новый адрес {{ .NewEmail }}, введите код "
            "<strong>{{ .Token }}</strong> или перейдите по ссылке:</p>"
            '<p><a href="{{ .ConfirmationURL }}">Подтвердить email</a></p>'
            "<p>Если вы не меняли адрес — проигнорируйте письмо.</p>"
        ),
        "mailer_subjects_invite": "Приглашение в кабинет «Проверка стажа»",
        "mailer_templates_invite_content": (
            "<h2>Вас пригласили в кабинет «Проверка стажа»</h2>"
            "<p>Перейдите по ссылке, чтобы принять приглашение:</p>"
            '<p><a href="{{ .ConfirmationURL }}">Принять приглашение</a></p>'
        ),
        "mailer_subjects_reauthentication": "{{ .Token }} — код подтверждения «Проверка стажа»",
        "mailer_templates_reauthentication_content": (
            "<h2>Код подтверждения</h2>"
            "<p>Ваш код: <strong style=\"font-size:24px\">{{ .Token }}</strong></p>"
            "<p>Он действует короткое время.</p>"
        ),
    }

    url = f"https://api.supabase.com/v1/projects/{ref}/config/auth"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "sfrfr-ops/1.0",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"OK HTTP {resp.status}: шаблоны Auth обновлены (project={ref})")
            # не печатаем полный ответ — там могут быть секреты SMTP
            keys = [k for k in payload if k.startswith("mailer_subjects_")]
            print("subjects:", ", ".join(payload[k] for k in keys))
            if body:
                print("response_bytes=", len(body))
            return 0
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {err[:800]}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
