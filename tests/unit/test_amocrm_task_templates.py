"""Тесты шаблонов задач amo."""

from __future__ import annotations

from sfrfr.integrations.amocrm.task_templates import AMO_TASK_TEMPLATES, TASK_FIRST_CONTACT


def test_task_templates_fit_amo_limit() -> None:
    for key, tpl in AMO_TASK_TEMPLATES.items():
        text = str(tpl["text"])
        assert len(text) <= 5000, key
        assert tpl["task_type_id"] in {1, 2}


def test_first_contact_has_checklist() -> None:
    assert "Чеклист: первый контакт" in TASK_FIRST_CONTACT
    assert "CONSENT" in TASK_FIRST_CONTACT
