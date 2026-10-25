from sfrfr.services.brief_reply_polish import (
    dedupe_sentences,
    polish_brief_reply,
    position_said_recently,
)

DRAFT = (
    "Пока данных недостаточно, чтобы сказать, есть ли расхождение.\n\n"
    "Ваш вопрос — по северному / льготному стажу. Чтобы это проверить, сверим периоды "
    "в выписке ИЛС и в трудовой книжке.\n\n"
    "Напишите, пожалуйста, какие периоды — годы и место работы — по-вашему, учтены неверно.\n\n"
    "Подаёте обращение вы сами, решение принимает СФР."
)

CLIENT_ASKED = [
    {
        "author_kind": "client",
        "body": "Дайте краткий комментарий: нужна платная диагностика или нет?",
    },
]

POSITION_SAID = [
    {
        "author_kind": "staff",
        "body": "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
        "Решение принимает СФР.",
    },
    *CLIENT_ASKED,
]


class FakeLLM:
    def __init__(self, reply: str, available: bool = True) -> None:
        self.reply = reply
        self.available = available
        self.calls: list[str] = []

    def chat(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        self.calls.append(user)
        return self.reply


def test_position_said_recently_detects_sfr_line() -> None:
    assert position_said_recently(POSITION_SAID) is True
    assert position_said_recently(CLIENT_ASKED) is False


def test_dedupe_sentences_and_double_label() -> None:
    text = "Следующий шаг: Следующий шаг: пришлите ИЛС. Пришлите ИЛС. Спасибо."
    out = dedupe_sentences(text)
    assert out.count("Следующий шаг") <= 1
    assert out.lower().count("пришлите илс") == 1


def test_ai_reply_used_when_valid_and_answers_client() -> None:
    llm = FakeLLM(
        "Здравствуйте, Наталия Фёдоровна! Платная диагностика пока не нужна: сначала сверим "
        "периоды в выписке ИЛС и трудовой книжке. Подскажите, какие годы и место работы, "
        "по-вашему, учтены неверно?"
    )
    out = polish_brief_reply(
        draft=DRAFT, messages=CLIENT_ASKED, client_name="Лопакова Наталия Фёдоровна", llm=llm
    )
    assert out["source"] == "ai"
    assert "диагностика пока не нужна" in out["text"]
    assert "нужна платная диагностика" in llm.calls[0]


def test_position_stripped_when_said_recently() -> None:
    out = polish_brief_reply(draft=DRAFT, messages=POSITION_SAID, client_name=None, llm=None)
    assert out["source"] == "template"
    assert "СФР" not in out["text"]


def test_position_kept_when_not_said() -> None:
    out = polish_brief_reply(draft=DRAFT, messages=CLIENT_ASKED, client_name=None, llm=None)
    assert "решение принимает СФР" in out["text"]


def test_ai_reply_with_bot_text_falls_back() -> None:
    llm = FakeLLM("Если нужен разбор — ответьте кнопкой ниже или напишите /help.")
    out = polish_brief_reply(draft=DRAFT, messages=CLIENT_ASKED, client_name=None, llm=llm)
    assert out["source"] == "template"
    assert "/help" not in out["text"]


def test_ai_reply_with_new_amount_falls_back() -> None:
    llm = FakeLLM(
        "Здравствуйте! Предлагаем подробный разбор за 5 000 ₽ — сверим периоды ИЛС и трудовой."
    )
    out = polish_brief_reply(draft=DRAFT, messages=CLIENT_ASKED, client_name=None, llm=llm)
    assert out["source"] == "template"
    assert "5 000" not in out["text"]


def test_ai_reply_with_promise_falls_back() -> None:
    llm = FakeLLM("Здравствуйте! Гарантируем перерасчёт пенсии после проверки.")
    out = polish_brief_reply(draft=DRAFT, messages=CLIENT_ASKED, client_name=None, llm=llm)
    assert out["source"] == "template"


def test_ai_drops_position_if_said_recently() -> None:
    llm = FakeLLM(
        "Здравствуйте! Сверим периоды ИЛС и трудовой. Напишите, какие годы учтены неверно. "
        "Решение принимает СФР."
    )
    out = polish_brief_reply(draft=DRAFT, messages=POSITION_SAID, client_name=None, llm=llm)
    assert out["source"] == "ai"
    assert "СФР" not in out["text"]
