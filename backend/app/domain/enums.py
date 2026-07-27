"""Domain enums and shared value types."""

from enum import Enum


class LocationMode(str, Enum):
    STATION = "station"
    NEIGHBORHOOD = "neighborhood"


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


class City(str, Enum):
    SEOUL = "seoul"
    BUSAN = "busan"
    DAEGU = "daegu"
    INCHEON = "incheon"
    GWANGJU = "gwangju"
    DAEJEON = "daejeon"
    ULSAN = "ulsan"
    JEONJU = "jeonju"
    OTHER = "other"
