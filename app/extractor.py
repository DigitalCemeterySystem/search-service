import re
import unicodedata
from collections.abc import Iterable

from bs4 import BeautifulSoup


BASE_KEYWORDS = {
    "биография",
    "некролог",
    "родился",
    "родилась",
    "дата рождения",
    "место рождения",
    "рождение",
    "умер",
    "умерла",
    "дата смерти",
    "место смерти",
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
    "род деятельности",
    "известен как",
    "известна как",
    "биограф",
    "семья",
}

DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}\s+[а-яё]+\s+(?:18|19|20)\d{2}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\.\d{1,2}\.(?:18|19|20)\d{2}\b", re.IGNORECASE),
    re.compile(r"\b(?:18|19|20)\d{2}-\d{2}-\d{2}\b", re.IGNORECASE),
    re.compile(r"\b(?:18|19|20)\d{2}\s*г(?:\.|ода)?\b", re.IGNORECASE),
    re.compile(r"\b(?:18|19|20)\d{2}\b", re.IGNORECASE),
]

CONTENT_SELECTORS = ("#mw-content-text", "main", "article", "[role='main']")
JUNK_SELECTORS = (
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "form",
    "nav",
    "footer",
    "header",
    "sup.reference",
    ".mw-editsection",
    ".reflist",
    ".references",
    ".navbox",
    ".metadata",
    ".catlinks",
    ".printfooter",
)
STOP_SECTION_TITLES = {
    "примечания",
    "литература",
    "ссылки",
    "внешние ссылки",
    "см также",
    "см. также",
    "библиография",
}
BIO_SECTION_TITLES = {
    "биография",
    "семья",
    "память",
    "научные интересы",
    "личность и общественная позиция",
    "звания и награды",
}


def _normalize_for_match(value: str) -> str:
    without_accents = "".join(
        char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn"
    )
    normalized = without_accents.lower().replace("ё", "е")
    normalized = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


NORMALIZED_STOP_SECTION_TITLES = {_normalize_for_match(title) for title in STOP_SECTION_TITLES}
NORMALIZED_BIO_SECTION_TITLES = {_normalize_for_match(title) for title in BIO_SECTION_TITLES}


def _clean_block_text(text: str) -> str:
    text = re.sub(r"\[\s*\d+\s*\]", "", text)
    text = re.sub(r"\[\s*править(?:\s+код)?\s*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\n\r:;")


def _is_stop_section(text: str) -> bool:
    normalized = _normalize_for_match(text)
    return normalized in NORMALIZED_STOP_SECTION_TITLES


def _tag_text(tag) -> str:
    return _clean_block_text(tag.get_text(" ", strip=True))


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select(", ".join(JUNK_SELECTORS)):
        tag.decompose()

    root = next((node for selector in CONTENT_SELECTORS if (node := soup.select_one(selector))), soup)
    blocks: list[str] = []

    for tag in root.find_all(["h1", "h2", "h3", "p", "li", "tr"]):
        if tag.name in {"h1", "h2", "h3"}:
            text = _tag_text(tag)
            if _is_stop_section(text):
                break
        elif tag.name == "tr":
            cells = tag.find_all(["th", "td"], recursive=False)
            if len(cells) >= 2:
                title = _tag_text(cells[0])
                value = _tag_text(cells[1])
                text = f"{title}: {value}" if title and value else title or value
            else:
                text = _tag_text(tag)
        else:
            if tag.find_parent("table"):
                continue
            text = _tag_text(tag)

        if text and len(text) >= 3:
            blocks.append(text)

    if not blocks:
        text = soup.get_text(separator="\n")
        blocks = [line.strip() for line in text.splitlines() if line.strip()]

    result: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        normalized = _normalize_for_match(block)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(block)

    return "\n".join(result)


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
    name_parts = [part for part in re.split(r"\s+", _normalize_for_match(full_name)) if len(part) > 1]
    surname = name_parts[0] if name_parts else ""
    keywords = set(BASE_KEYWORDS)
    keywords.update(k.lower().strip() for k in extra_keywords if k and k.strip())
    normalized_keywords = {_normalize_for_match(keyword) for keyword in keywords if _normalize_for_match(keyword)}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selected_indexes: set[int] = set()
    in_bio_section = False

    for idx, line in enumerate(lines):
        normalized_line = _normalize_for_match(line)
        if not normalized_line:
            continue

        if normalized_line in NORMALIZED_STOP_SECTION_TITLES:
            break
        if normalized_line in NORMALIZED_BIO_SECTION_TITLES:
            in_bio_section = True
            selected_indexes.add(idx)
            continue

        has_name = bool(surname and re.search(rf"\b{re.escape(surname)}\b", normalized_line))
        name_hits = sum(1 for part in name_parts if re.search(rf"\b{re.escape(part)}\b", normalized_line))
        has_keyword = any(keyword in normalized_line for keyword in normalized_keywords)
        has_date = any(pattern.search(line) for pattern in DATE_PATTERNS)
        has_full_name_words = name_hits >= min(2, len(name_parts)) if name_parts else False

        if has_full_name_words or (has_name and (has_keyword or has_date)) or (has_keyword and has_date) or (in_bio_section and has_date):
            before = 1
            after = 4 if has_keyword and len(line) < 80 else 1
            selected_indexes.update(range(max(0, idx - before), min(len(lines), idx + after + 1)))

    result: list[str] = []
    seen: set[str] = set()
    for idx in sorted(selected_indexes):
        line = lines[idx]
        normalized = _normalize_for_match(line)
        if normalized in NORMALIZED_STOP_SECTION_TITLES:
            break
        if normalized in seen or len(normalized) < 3:
            continue
        seen.add(normalized)
        result.append(line)

    return "\n".join(result)


def trim_combined_text(text: str, max_chars: int = 80_000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[Текст обрезан до лимита хранения релевантной информации]"
