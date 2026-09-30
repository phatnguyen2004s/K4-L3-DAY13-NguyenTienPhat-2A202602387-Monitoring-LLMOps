from __future__ import annotations

import hashlib
import re

_ADDRESS_KEYWORDS = r"(?:số nhà|ngõ|ngách|hẻm|kiệt|đường|phố|phường|quận|huyện|thị xã|xã|thôn|ấp|tổ dân phố)"

# Thứ tự quan trọng: chuỗi số dài (thẻ 16 số, CCCD 12 số) phải được xử lý trước
# số điện thoại để không bị redact nhầm loại hoặc chỉ redact một phần.
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "cccd": r"\b\d{12}\b",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    # Hộ chiếu Việt Nam: 1 chữ cái in hoa + 7 chữ số, ví dụ C1234567.
    "passport": r"\b[A-Z]\d{7}\b",
    # Địa chỉ: từ khóa đơn vị hành chính/đường phố + tối đa 4 từ phía sau,
    # dừng ở dấu phẩy/chấm phẩy hoặc từ khóa kế tiếp (từ khóa đó tạo match riêng).
    "address_vn": (
        r"(?i)(?:\b\d+[a-z]?(?:/\d+)*\s+)?"
        rf"\b{_ADDRESS_KEYWORDS}"
        rf"(?:\s+(?!{_ADDRESS_KEYWORDS}\b)[^\s,;]+){{1,4}}"
    ),
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
