from app.privacy.pii import scrub_pii


def test_emails_phones_and_names_are_anonymized() -> None:
    text = (
        "Hallo Anna,\nmein Name ist Max Mustermann. Ruft mich an unter +49 (0) 171 1234567 "
        "oder schreibt an max.mustermann@gmail.com.\nMit freundlichen Grüßen\nMax Mustermann"
    )
    result = scrub_pii(text)
    assert "Mustermann" not in result.text
    assert "Anna" not in result.text
    assert "1234567" not in result.text
    assert "gmail" not in result.text
    assert result.text.count("[ANONYMOUS_NAME]") == 3
    assert result.entities == {"NAME": 3, "PHONE": 1, "EMAIL": 1}


def test_order_numbers_survive_and_are_detected() -> None:
    result = scrub_pii("Wo bleibt meine Bestellung 4711-2025? Order #1001 und ORD-889911 auch.")
    assert "4711-2025" in result.text
    assert "#1001" in result.text
    assert "ORD-889911" in result.text
    assert result.order_references == ["4711-2025", "1001", "ORD-889911"]
    assert result.entities == {}


def test_tracking_numbers_are_not_mistaken_for_phone_numbers() -> None:
    result = scrub_pii("Sendungsnummer 00340434161234567890, Kundennummer 0012345678")
    assert "00340434161234567890" in result.text
    assert "0012345678" in result.text
    assert not result.order_reference_detected


def test_payment_data_is_validated_before_masking() -> None:
    result = scrub_pii("IBAN DE89 3704 0044 0532 0130 00, Karte 4111 1111 1111 1111, Ref 1234 5678 9012 3456")
    assert "[ANONYMOUS_IBAN]" in result.text
    assert "[ANONYMOUS_CARD]" in result.text
    # Luhn-ungültige Ziffernfolge bleibt erhalten.
    assert "1234 5678 9012 3456" in result.text


def test_address_salutation_ip_and_obfuscated_email() -> None:
    result = scrub_pii(
        "Sehr geehrte Frau Schmidt, Lieferadresse: Musterstraße 12, 10115 Berlin. "
        "IP 192.168.0.12, Mail: jane [at] example [dot] com"
    )
    assert result.text == (
        "Sehr geehrte Frau [ANONYMOUS_NAME], Lieferadresse: [ANONYMOUS_ADDRESS]. "
        "IP [ANONYMOUS_IP], Mail: [ANONYMOUS_EMAIL]"
    )


def test_dates_and_common_nouns_are_not_redacted() -> None:
    text = "Am 12.03.2024 bestellt. Ich bin Kunde seit Jahren. Gruß aus Hamburg. Der Betrag war 0815 Euro."
    result = scrub_pii(text)
    assert result.text == text
    assert not result.redacted


def test_english_sign_off_and_intro() -> None:
    result = scrub_pii("Hi, this is John Smith. Call me at (555) 123-4567.\nBest,\nSarah Connor")
    assert result.text == "Hi, this is [ANONYMOUS_NAME]. Call me at [ANONYMOUS_PHONE].\nBest,\n[ANONYMOUS_NAME]"


def test_unicode_surnames_are_masked() -> None:
    result = scrub_pii("My name is Łukasz Wójcik.\nViele Grüße\nSarah Yılmaz")

    assert "Łukasz" not in result.text
    assert "Wójcik" not in result.text
    assert "Sarah" not in result.text
    assert "Yılmaz" not in result.text
    assert result.entities["NAME"] == 2


def test_nul_bytes_cannot_corrupt_reference_protection() -> None:
    result = scrub_pii("Bestellung 12345 \x000\x00 test@example.com")
    assert "\x00" not in result.text
    assert "12345" in result.text
