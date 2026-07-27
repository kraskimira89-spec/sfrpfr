from sfrfr.api.routes.public_leads import _from_wpforms_payload


def test_wpforms_payload_does_not_invent_consent() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "value": "Иван Иванов"},
                "2": {"name": "Телефон", "value": "+7 900 000-00-00"},
            }
        }
    )

    assert payload is not None
    assert payload.consent is False


def test_wpforms_payload_keeps_explicit_consent() -> None:
    payload = _from_wpforms_payload(
        {
            "fields": {
                "1": {"name": "Имя", "value": "Иван Иванов"},
                "2": {"name": "Телефон", "value": "+7 900 000-00-00"},
                "3": {"name": "Согласие", "value": "Да"},
            }
        }
    )

    assert payload is not None
    assert payload.consent is True
