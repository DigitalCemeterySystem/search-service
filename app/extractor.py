import re
from collections.abc import Iterable

from bs4 import BeautifulSoup


BASE_KEYWORDS = {
    "биография",
    "некролог",
    "родился",
    "родилась",
    "дата рождения",
    "рождение",
    "умер",
    "умерла",
    "скончался",
    "скончалась",
    "смерть",
    "похоронен",
    "похоронена",
    "захоронен",
    "захоронена",
    "кладбище",
    "могила",
    "памяти",
}

DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}\s+[а-яё]+\s+(?:18|19|20)\d{2}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\.\d{1,2}\.(?:18|19|20)\d{2}\b", re.IGNORECASE),
    re.compile(r"\b(?:18|19|20)\d{2}\s*г(?:\.|ода)?\b", re.IGNORECASE),
]


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def build_query(
    full_name: str,
    city: str | None = None,
    birth_date: str | None = None,
    death_date: str | None = None,
    cemetery: str | None = None,
    extra_terms: str | None = None,
) -> str:
    parts = [f'"{full_name.strip()}"']
    for value in (city, birth_date, death_date, cemetery, extra_terms):
        if value and value.strip():
            parts.append(value.strip())
    parts.extend(["биография", "некролог", "захоронение", "кладбище"])
    return " ".join(parts)


def extract_relevant_info(text: str, full_name: str, extra_keywords: Iterable[str] = ()) -> str:
    name_parts = [part.lower() for part in re.split(r"\s+", full_name.strip()) if len(part) > 1]
    surname = name_parts[0] if name_parts else ""
    keywords = set(BASE_KEYWORDS)
    keywords.update(k.lower().strip() for k in extra_keywords if k and k.strip())

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selected_indexes: set[int] = set()

    for idx, line in enumerate(lines):
        lower = line.lower()
        has_name = full_name.lower() in lower or (surname and surname in lower)
        name_hits = sum(1 for part in name_parts if part in lower)
        has_keyword = any(keyword in lower for keyword in keywords)
        has_date = any(pattern.search(line) for pattern in DATE_PATTERNS)

        if full_name.lower() in lower or name_hits >= 2 or (has_name and (has_keyword or has_date)) or (has_keyword and has_date):
            selected_indexes.update(range(max(0, idx - 1), min(len(lines), idx + 2)))

    result: list[str] = []
    seen: set[str] = set()
    for idx in sorted(selected_indexes):
        line = lines[idx]
        normalized = re.sub(r"\s+", " ", line).lower()
        if normalized in seen or len(normalized) < 3:
            continue
        seen.add(normalized)
        result.append(line)

    return "\n".join(result)


def trim_combined_text(text: str, max_chars: int = 80_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[Текст обрезан до лимита хранения релевантной информации]"
