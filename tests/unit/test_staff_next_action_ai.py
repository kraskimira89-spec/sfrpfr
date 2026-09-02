"""Подсказка шага без вызова LLM: эвристика."""

from sfrfr.services.staff_next_action_ai import suggest_next_action


def test_suggest_falls_back_when_llm_unavailable(monkeypatch) -> None:
    class Fake:
        available = False

    monkeypatch.setattr(
        "sfrfr.services.staff_next_action_ai.LLMClient.for_analyze",
        classmethod(lambda cls: Fake()),
    )
    out = suggest_next_action(
        {
            "pipeline_status": "intake",
            "b2c_status": "lead",
            "checklist_items": [],
            "clients": {},
            "orders": [],
        }
    )
    assert out["source"] == "heuristic"
    assert out["waiting_on"] == "staff"
    assert out["next_action"]
    assert isinstance(out.get("chat_messages"), list)
    assert out["chat_messages"]
    assert {m["kind"] for m in out["chat_messages"]} == {"full", "short", "cabinet_howto"}
    assert all(m["text"] for m in out["chat_messages"])
    joined = " ".join(m["text"] for m in out["chat_messages"])
    assert "этот чат MAX" in joined
    assert "cabinet.proverkastaza.ru" in joined or "кабинет на сайте" in joined
    assert "только в личном кабинете" not in joined
    assert "не в этот чат" not in joined.lower()


def test_suggest_falls_back_when_llm_errors(monkeypatch) -> None:
    class Fake:
        available = True

        def chat(self, **_kwargs):
            raise RuntimeError("401 AuthenticationError")

    monkeypatch.setattr(
        "sfrfr.services.staff_next_action_ai.LLMClient.for_analyze",
        classmethod(lambda cls: Fake()),
    )
    out = suggest_next_action(
        {
            "pipeline_status": "intake",
            "b2c_status": "lead",
            "checklist_items": [],
            "clients": {},
            "orders": [],
        }
    )
    assert out["source"] == "heuristic"
    assert out["next_action"]
