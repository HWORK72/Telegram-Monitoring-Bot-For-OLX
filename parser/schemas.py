from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True, frozen=True)
class OfferDTO:
    olx_offer_id: str
    title: str
    url: str
    price: Optional[str] = None
    photo_url: Optional[str] = None
    location: Optional[str] = None
    published_at: Optional[str] = None
    phone: Optional[str] = None
    category_name: Optional[str] = None
    seller_id: Optional[str] = None
    is_bumped: bool = False
    is_promoted: bool = False
    is_too_old: bool = False