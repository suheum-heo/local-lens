"""Shared mock catalog: stations, neighborhoods, and restaurants."""

from __future__ import annotations

from app.domain.enums import City, LocationMode
from app.domain.contracts import LocationCatalogItem
from app.domain.models import GooglePlaceData, KakaoPlaceData

# ---------------------------------------------------------------------------
# Location catalogs
# ---------------------------------------------------------------------------

STATIONS: list[LocationCatalogItem] = [
    LocationCatalogItem(
        id="st_hapjeong",
        name="합정역",
        name_en="Hapjeong Station",
        city=City.SEOUL,
        latitude=37.5496,
        longitude=126.9139,
        mode=LocationMode.STATION,
    ),
    LocationCatalogItem(
        id="st_sangsu",
        name="상수역",
        name_en="Sangsu Station",
        city=City.SEOUL,
        latitude=37.5478,
        longitude=126.9227,
        mode=LocationMode.STATION,
    ),
    LocationCatalogItem(
        id="st_hongdae",
        name="홍대입구역",
        name_en="Hongik University Station",
        city=City.SEOUL,
        latitude=37.5572,
        longitude=126.9254,
        mode=LocationMode.STATION,
    ),
    LocationCatalogItem(
        id="st_gangnam",
        name="강남역",
        name_en="Gangnam Station",
        city=City.SEOUL,
        latitude=37.4979,
        longitude=127.0276,
        mode=LocationMode.STATION,
    ),
    LocationCatalogItem(
        id="st_sinnonhyeon",
        name="신논현역",
        name_en="Sinnonhyeon Station",
        city=City.SEOUL,
        latitude=37.5045,
        longitude=127.0250,
        mode=LocationMode.STATION,
    ),
]

NEIGHBORHOODS: list[LocationCatalogItem] = [
    LocationCatalogItem(
        id="nb_samsan",
        name="삼산동",
        name_en="Samsan-dong",
        city=City.ULSAN,
        latitude=35.5412,
        longitude=129.3380,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_daldong",
        name="달동",
        name_en="Dal-dong",
        city=City.ULSAN,
        latitude=35.5350,
        longitude=129.3220,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_hyoja",
        name="효자동",
        name_en="Hyoja-dong",
        city=City.JEONJU,
        latitude=35.8400,
        longitude=127.1200,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_seosin",
        name="서신동",
        name_en="Seosin-dong",
        city=City.JEONJU,
        latitude=35.8330,
        longitude=127.1150,
        mode=LocationMode.NEIGHBORHOOD,
    ),
]


def catalog_for_city(city: City, mode: LocationMode) -> list[LocationCatalogItem]:
    source = STATIONS if mode == LocationMode.STATION else NEIGHBORHOODS
    return [item for item in source if item.city == city]


# ---------------------------------------------------------------------------
# Mock restaurant fixtures
# scenario tags:
#   both_strong          — strong Kakao + Google
#   google_missing       — no Google match
#   google_insufficient  — Google match but too few reviews
#   match_uncertain      — low match confidence (should not auto-accept)
# ---------------------------------------------------------------------------

# Hapjeong / Sangsu area (~37.55, 126.91)
HAPJEONG_KAKAO: list[KakaoPlaceData] = [
    KakaoPlaceData(
        kakao_place_id="kakao_hp_001",
        name="합정 삼겹살집",
        address="서울 마포구 합정동 123-4",
        road_address="서울 마포구 양화로 45",
        latitude=37.5501,
        longitude=126.9145,
        category="음식점 > 한식 > 육류,고기",
        place_url="https://place.map.kakao.com/kakao_hp_001",
        rating=4.5,
        review_count=842,
    ),
    KakaoPlaceData(
        kakao_place_id="kakao_hp_002",
        name="상수 로컬 국밥",
        address="서울 마포구 상수동 56-7",
        road_address="서울 마포구 독막로 88",
        latitude=37.5482,
        longitude=126.9220,
        category="음식점 > 한식 > 국밥",
        place_url="https://place.map.kakao.com/kakao_hp_002",
        rating=4.7,
        review_count=1203,
    ),
    KakaoPlaceData(
        kakao_place_id="kakao_hp_003",
        name="망원시장 분식",
        address="서울 마포구 망원동 9-1",
        road_address="서울 마포구 포은로 12",
        latitude=37.5560,
        longitude=126.9100,
        category="음식점 > 분식",
        place_url="https://place.map.kakao.com/kakao_hp_003",
        rating=4.3,
        review_count=310,
    ),
    KakaoPlaceData(
        kakao_place_id="kakao_hp_004",
        name="합정 숨은 칼국수",
        address="서울 마포구 합정동 200-1",
        road_address="서울 마포구 독막로 15",
        latitude=37.5490,
        longitude=126.9120,
        category="음식점 > 한식 > 국수",
        place_url="https://place.map.kakao.com/kakao_hp_004",
        rating=4.6,
        review_count=95,
    ),
]

# Gangnam area
GANGNAM_KAKAO: list[KakaoPlaceData] = [
    KakaoPlaceData(
        kakao_place_id="kakao_gn_001",
        name="강남 프리미엄 삼겹살",
        address="서울 강남구 역삼동 823-1",
        road_address="서울 강남구 테헤란로 152",
        latitude=37.4995,
        longitude=127.0280,
        category="음식점 > 한식 > 육류,고기",
        place_url="https://place.map.kakao.com/kakao_gn_001",
        rating=4.4,
        review_count=2100,
    ),
    KakaoPlaceData(
        kakao_place_id="kakao_gn_002",
        name="신논현 이자카야",
        address="서울 강남구 논현동 11-2",
        road_address="서울 강남구 강남대로 468",
        latitude=37.5040,
        longitude=127.0255,
        category="음식점 > 일식 > 이자카야",
        place_url="https://place.map.kakao.com/kakao_gn_002",
        rating=4.2,
        review_count=560,
    ),
    KakaoPlaceData(
        kakao_place_id="kakao_gn_003",
        name="강남역 옆 카페식당",
        address="서울 강남구 역삼동 900",
        road_address="서울 강남구 강남대로 396",
        latitude=37.4975,
        longitude=127.0270,
        category="음식점 > 카페",
        place_url="https://place.map.kakao.com/kakao_gn_003",
        rating=3.9,
        review_count=88,
    ),
]

# Ulsan Samsan-dong
ULSAN_KAKAO: list[KakaoPlaceData] = [
    KakaoPlaceData(
        kakao_place_id="kakao_ul_001",
        name="삼산 고깃집",
        address="울산 남구 삼산동 1450",
        road_address="울산 남구 삼산로 45",
        latitude=35.5415,
        longitude=129.3385,
        category="음식점 > 한식 > 육류,고기",
        place_url="https://place.map.kakao.com/kakao_ul_001",
        rating=4.6,
        review_count=980,
    ),
    KakaoPlaceData(
        kakao_place_id="kakao_ul_002",
        name="달동 해물탕",
        address="울산 남구 달동 880",
        road_address="울산 남구 삼산로 210",
        latitude=35.5360,
        longitude=129.3230,
        category="음식점 > 한식 > 해물,생선",
        place_url="https://place.map.kakao.com/kakao_ul_002",
        rating=4.5,
        review_count=420,
    ),
    KakaoPlaceData(
        kakao_place_id="kakao_ul_003",
        name="삼산동 동네 분식",
        address="울산 남구 삼산동 1501",
        road_address="울산 남구 돋질로 88",
        latitude=35.5408,
        longitude=129.3370,
        category="음식점 > 분식",
        place_url="https://place.map.kakao.com/kakao_ul_003",
        rating=4.4,
        review_count=156,
    ),
]

ALL_KAKAO: list[KakaoPlaceData] = HAPJEONG_KAKAO + GANGNAM_KAKAO + ULSAN_KAKAO

# Google places keyed by intended Kakao match (mock truth table)
GOOGLE_BY_KAKAO_ID: dict[str, GooglePlaceData | None] = {
    # both_strong — Korean Google names mirror Kakao for realistic matching
    "kakao_hp_001": GooglePlaceData(
        google_place_id="ChIJhp_samgyeopsal",
        name="합정 삼겹살집",
        address="서울특별시 마포구 양화로 45",
        latitude=37.55015,
        longitude=126.91455,
        rating=4.6,
        user_rating_count=731,
        review_metadata=[
            {"language": "en", "rating": 5, "text": "Great BBQ near the station"},
            {"language": "ko", "rating": 4, "text": "고기가 맛있어요"},
        ],
    ),
    # both_strong (local favorite leaning)
    "kakao_hp_002": GooglePlaceData(
        google_place_id="ChIJhp_sangsu_gukbap",
        name="상수 로컬 국밥",
        address="서울특별시 마포구 독막로 88",
        latitude=37.54825,
        longitude=126.92205,
        rating=4.3,
        user_rating_count=215,
        review_metadata=[],
    ),
    # google_missing
    "kakao_hp_003": None,
    # google_insufficient (only 2 reviews)
    "kakao_hp_004": GooglePlaceData(
        google_place_id="ChIJhp_kalguksu",
        name="합정 숨은 칼국수",
        address="서울특별시 마포구 독막로 15",
        latitude=37.54905,
        longitude=126.91205,
        rating=5.0,
        user_rating_count=2,
        review_metadata=[{"language": "en", "rating": 5, "text": "Amazing"}],
    ),
    # both_strong
    "kakao_gn_001": GooglePlaceData(
        google_place_id="ChIJgn_premium_bbq",
        name="강남 프리미엄 삼겹살",
        address="서울특별시 강남구 테헤란로 152",
        latitude=37.49955,
        longitude=127.02805,
        rating=4.5,
        user_rating_count=1890,
        review_metadata=[],
    ),
    # match_uncertain — deliberately different name/coords so matcher stays low
    "kakao_gn_002": GooglePlaceData(
        google_place_id="ChIJgn_wrong_match",
        name="랜덤 이자카야 다운타운",
        address="서울특별시 강남구 다른곳 1",
        latitude=37.5100,
        longitude=127.0400,
        rating=4.0,
        user_rating_count=90,
        review_metadata=[],
    ),
    # google_insufficient
    "kakao_gn_003": GooglePlaceData(
        google_place_id="ChIJgn_cafe",
        name="강남역 옆 카페식당",
        address="서울특별시 강남구 강남대로 396",
        latitude=37.49755,
        longitude=127.02705,
        rating=4.8,
        user_rating_count=3,
        review_metadata=[],
    ),
    # both_strong (local city)
    "kakao_ul_001": GooglePlaceData(
        google_place_id="ChIJul_samsan_bbq",
        name="삼산 고깃집",
        address="울산광역시 남구 삼산로 45",
        latitude=35.54155,
        longitude=129.33855,
        rating=4.4,
        user_rating_count=180,
        review_metadata=[],
    ),
    # google_missing — strong local only
    "kakao_ul_002": None,
    # google_insufficient
    "kakao_ul_003": GooglePlaceData(
        google_place_id="ChIJul_bunsik",
        name="삼산동 동네 분식",
        address="울산광역시 남구 돋질로 88",
        latitude=35.54085,
        longitude=129.33705,
        rating=4.9,
        user_rating_count=1,
        review_metadata=[],
    ),
}

# Places that exist in Google catalog for search_places (includes distractors)
ALL_GOOGLE: list[GooglePlaceData] = [
    g for g in GOOGLE_BY_KAKAO_ID.values() if g is not None
]
