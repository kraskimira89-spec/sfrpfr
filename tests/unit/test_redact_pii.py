def test_mask_snils() -> None:
    from sfrfr.utils.redact_pii import mask_snils

    assert mask_snils("123-456-789 01") == "***-***-789 01"
