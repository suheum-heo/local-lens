"""Expand user food intent into Kakao keyword variants.

Kakao Local classifies many Western-style places as ``패밀리레스토랑``,
``파스타``, etc. rather than ``양식``. Users search by food, so umbrella
cuisine terms fan out to those related keywords and results are merged.

Specific dish keywords (``햄버거``, ``파스타``, …) are also filtered after
search: Kakao often returns sibling cuisine hits (bare ``양식``, bakery,
unrelated 일식) that do not actually match the dish. Umbrella terms like
``양식`` / ``일식`` stay unfiltered.

Cafe intent is special in Korea: ``카페`` means a coffee shop, not a
restaurant. Those queries use Kakao category ``CE7`` (see ``kakao_category_group``)
and stay on coffee-focused keywords — not dessert/bakery restaurant fan-out.

Nightlife is fine-grained: ``술집`` fans out broadly, but ``펍`` / ``호프``
stay beer-pub oriented (no 포차 / 이자카야). Bare ``바`` is not expanded —
too ambiguous for Kakao keyword search. No place-name hardcoding.
"""

from __future__ import annotations

# Kakao Local category_group_code: FD6 = food, CE7 = cafe.
KAKAO_CATEGORY_FOOD = "FD6"
KAKAO_CATEGORY_CAFE = "CE7"

# User terms that mean coffee shops (not restaurants).
_CAFE_INTENT_KEYS = frozenset(
    {
        "카페",
        "커피",
        "cafe",
        "coffee",
        "카페거리",
        "커피숍",
        "커피샵",
    }
)

# Shared nightlife keyword packs (no place lists).
_SULJIP_VARIANTS = (
    "술집",
    "호프",
    "펍",
    "이자카야",
    "포차",
    "와인바",
    "칵테일바",
    "요리주점",
)
_PUB_VARIANTS = ("펍", "호프", "맥주")
_HOF_VARIANTS = ("호프", "펍", "맥주")

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
    # Coffee shops only — 디저트/베이커리 under FD6 pulled in restaurants.
    "카페": ("카페", "커피"),
    "커피": ("커피", "카페"),
    "cafe": ("카페", "커피"),
    "coffee": ("커피", "카페"),
    "고기": ("고기", "삼겹살", "갈비", "고기집", "육류"),
    "해물": ("해물", "횟집", "생선", "조개", "대게"),
    # Nightlife — broad vs fine-grained (see module docstring).
    "술집": _SULJIP_VARIANTS,
    "주점": _SULJIP_VARIANTS,
    "펍": _PUB_VARIANTS,
    "pub": _PUB_VARIANTS,
    "호프": _HOF_VARIANTS,
    "hof": _HOF_VARIANTS,
    "이자카야": ("이자카야", "일식주점"),
    "izakaya": ("이자카야", "일식주점"),
    "포차": ("포차", "포장마차"),
    "와인바": ("와인바", "와인"),
    "wine bar": ("와인바", "와인"),
    "칵테일바": ("칵테일바", "칵테일"),
    "cocktail bar": ("칵테일바", "칵테일"),
}


def is_cafe_intent(query: str) -> bool:
    """True when the user is looking for coffee shops, not restaurants."""
    cleaned = (query or "").strip().lower()
    return cleaned in _CAFE_INTENT_KEYS


def kakao_category_group(query: str) -> str:
    """Kakao Local category_group_code for this food intent."""
    return KAKAO_CATEGORY_CAFE if is_cafe_intent(query) else KAKAO_CATEGORY_FOOD


# Specific dish / style keywords → tokens that must appear in Kakao
# place_name or category_name. Umbrella keys (양식, 일식, …) are omitted on
# purpose so broad searches stay broad.
_DISH_RELEVANCE_TOKENS: dict[str, tuple[str, ...]] = {
    "햄버거": (
        "햄버거",
        "버거",
        "burger",
        "hamburger",
        "맥도날드",
        "버거킹",
        "롯데리아",
        "맘스터치",
        "쉐이크쉑",
        "노브랜드버거",
        "수제버거",
        "크라제버거",
        "파이브가이즈",
    ),
    "파스타": ("파스타", "pasta", "스파게티", "spaghetti", "링귀니", "까르보나라"),
    "피자": ("피자", "pizza"),
    "스테이크": ("스테이크", "steak", "립", "바베큐", "바비큐", "barbeque", "barbecue"),
    "브런치": ("브런치", "brunch"),
    "경양식": ("경양식",),
    "패밀리레스토랑": ("패밀리레스토랑", "패밀리 레스토랑", "family"),
    "이탈리안": ("이탈리안", "이탈리아", "italian", "파스타", "피자"),
    "이탈리아": ("이탈리안", "이탈리아", "italian", "파스타", "피자"),
    "스시": ("스시", "초밥", "sushi", "회"),
    "초밥": ("초밥", "스시", "sushi"),
    "라멘": ("라멘", "ramen"),
    "돈카츠": ("돈카츠", "돈가스", "katsu"),
    "우동": ("우동",),
    "짜장": ("짜장",),
    "짬뽕": ("짬뽕",),
    "마라": ("마라",),
    "딤섬": ("딤섬", "만두"),
    "떡볶이": ("떡볶이",),
    "김밥": ("김밥",),
    "삼겹살": ("삼겹",),
    "갈비": ("갈비",),
    "이자카야": ("이자카야", "일식주점"),
    "일식주점": ("이자카야", "일식주점"),
    "포차": ("포차", "포장마차"),
    "포장마차": ("포차", "포장마차"),
    "와인바": ("와인바", "와인"),
    "칵테일바": ("칵테일바", "칵테일"),
    "맥주": ("맥주", "호프", "펍", "beer"),
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


def dish_relevance_tokens(keyword: str) -> tuple[str, ...] | None:
    """Return relevance tokens for a specific dish keyword, or None if unfiltered."""
    cleaned = (keyword or "").strip()
    if not cleaned:
        return None
    return _DISH_RELEVANCE_TOKENS.get(cleaned.lower()) or _DISH_RELEVANCE_TOKENS.get(
        cleaned
    )


def place_matches_food_keyword(
    keyword: str,
    *,
    name: str,
    category: str | None = None,
) -> bool:
    """True when a Kakao hit is on-topic for ``keyword``.

    Specific dishes require a token hit in name/category. Umbrella and
    unknown keywords accept all hits (Kakao already keyword-scoped them).
    """
    tokens = dish_relevance_tokens(keyword)
    if not tokens:
        return True
    haystack = f"{name or ''} {category or ''}".lower()
    return any(token.lower() in haystack for token in tokens)
