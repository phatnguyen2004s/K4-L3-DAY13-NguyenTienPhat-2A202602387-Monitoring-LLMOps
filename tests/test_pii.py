from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd_and_credit_card() -> None:
    out = scrub_text("CCCD 001203004567, card 4111 1111 1111 1111 or 4111-1111-1111-1111")
    assert "001203004567" not in out
    assert "4111" not in out
    assert out.count("REDACTED_CREDIT_CARD") == 2
    assert "REDACTED_CCCD" in out


def test_scrub_passport() -> None:
    out = scrub_text("Passport C1234567 expires soon")
    assert "C1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_vietnamese_address_keywords() -> None:
    out = scrub_text("Giao tới số nhà 45/2 ngõ 10 Tôn Thất Tùng, Phường Bến Nghé, Quận 1, giúp tôi nhé")
    for fragment in ("45/2", "Tôn Thất Tùng", "Bến Nghé", "Quận 1"):
        assert fragment not in out
    assert "REDACTED_ADDRESS_VN" in out
    # Dấu phẩy chặn match nên phần câu phía sau địa chỉ được giữ nguyên.
    assert out.endswith(", giúp tôi nhé")


def test_scrub_keeps_normal_text() -> None:
    text = "Explain why metrics traces and logs work together"
    assert scrub_text(text) == text
