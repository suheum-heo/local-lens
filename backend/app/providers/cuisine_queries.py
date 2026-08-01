"""Expand user food intent into Kakao keyword variants.

Kakao Local classifies many Western-style places as ``패밀리레스토랑``,
``파스타``, etc. rather than ``양식``. Users search by food, so umbrella
cuisine terms fan out to those related keywords and results are merged.
"""

from __future__ import annotations

# Umbrella cuisine → Kakao keyword variants (primary term first).
# Keys are lowercased / stripped lookup forms.
_CUISINE_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "양식": (
        "양식",
        "패밀리레스토랑",
        "파스타",
        "이탈리안",
        "이탈리아",
        "스테이크",
        "피자",
        "햄버거",
        "브런치",
        "경양식",
    ),
    "western": (
        "양식",
        "패밀리레스토랑",
        "파스타",
        "이탈리안",
        "스테이크",
        "피자",
        "햄버거",
        "브런치",
    ),
    "일식": ("일식", "스시", "초밥", "라멘", "돈카츠", "이자카야", "우동"),
    "중식": ("중식", "중국집", "짜장", "짬뽕", "마라", "딤섬"),
    "한식": ("한식", "백반", "국밥", "찌개", "한정식", "고기"),
    "분식": ("분식", "떡볶이", "김밥", "라면"),
    "카페": ("카페", "커피", "디저트", "베이커리"),
    "고기": ("고기", "삼겹살", "갈비", "고기집", "육류"),
    "해물": ("해물", "횟집", "생선", "조개", "대게"),
}


def expand_food_queries(query: str) -> list[str]:
    """Return unique Kakao keyword queries for a user food search.

    Unknown / place-name queries pass through unchanged (single term).
    """
    cleaned = (query or "").strip()
    if not cleaned:
        return [cleaned]

    key = cleaned.lower()
    variants = _CUISINE_EXPANSIONS.get(key) or _CUISINE_EXPANSIONS.get(cleaned)
    if not variants:
        return [cleaned]

    seen: set[str] = set()
    out: list[str] = []
    for term in variants:
        if term not in seen:
            seen.add(term)
            out.append(term)
    # Always keep the user's exact wording if somehow missing.
    if cleaned not in seen:
        out.insert(0, cleaned)
    return out
