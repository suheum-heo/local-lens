"""Domain enums and shared value types."""

from enum import Enum


class LocationMode(str, Enum):
    STATION = "station"
    BUS_STOP = "bus_stop"
    NEIGHBORHOOD = "neighborhood"
    STREET = "street"


class DataAvailability(str, Enum):
    """First-class state for platform data completeness."""

    AVAILABLE = "available"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAVAILABLE = "unavailable"
    UNMATCHED = "unmatched"


class MatchConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class RestaurantLabel(str, Enum):
    CONSENSUS_PICK = "consensus_pick"
    LOCAL_FAVORITE = "local_favorite"
    GLOBAL_FAVORITE = "global_favorite"
    LIMITED_DATA = "limited_data"


class RatingCoverage(str, Enum):
    """Which platforms expose a numeric rating for this restaurant."""

    BOTH = "both"
    KAKAO_ONLY = "kakao_only"
    GOOGLE_ONLY = "google_only"
    NONE = "none"


class City(str, Enum):
    SEOUL = "seoul"
    BUSAN = "busan"
    DAEGU = "daegu"
    INCHEON = "incheon"
    GWANGJU = "gwangju"
    DAEJEON = "daejeon"
    ULSAN = "ulsan"
    JEONJU = "jeonju"
    GYEONGJU = "gyeongju"
    OTHER = "other"
