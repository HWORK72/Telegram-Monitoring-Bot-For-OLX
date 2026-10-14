import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote
from selectolax.lexbor import LexborHTMLParser, LexborNode
from core.config import get_settings
from parser.normalizer import to_absolute_url
from parser.schemas import OfferDTO

logger: logging.Logger = logging.getLogger("app.parser.extractor")
settings = get_settings()

CATEGORY_RULES: List[Tuple[str, List[str]]] = [
    ("🏠 Недвижимость", ["imobiliare", "apartament", "garsonier", "casa", "case", "vila", "vile", "duplex", "teren", "terenuri", "chirie", "inchiri", "storia", "bloc nou", "decomandat", "dormitor", "camere", "rezidential"]),
    ("🚗 Автозапчасти", ["piese", "auto", "dezmembr", "motor", "diferential", "cutie viteze", "jante", "anvelope", "cauciuc", "bmw", "audi", "mercedes", "skoda", "volkswagen", "vw", "renault", "opel", "dacia", "ford", "camion", "utilaj", "parbriz", "bara", "pompa", "chiuloasa", "injector", "aripa", "volan", "etrier", "timonerie", "caddy", "crafter", "passat", "iveco"]),
    ("📱 Электроника", ["electronice", "telefon", "iphone", "samsung", "xiaomi", "laptop", "pc", "televizor", "tv", "vape", "audio", "casti", "playstation", "ps5", "ps4", "xbox", "ipad", "airpods", "calculator", "electrocasnice", "frigider", "aragaz", "cuptor", "aspirator"]),
    ("👗 Мода", ["moda", "haine", "incaltaminte", "adidasi", "pantofi", "rochie", "geaca", "tricou", "geanta", "inel", "aur", "argint", "ceas", "parfum", "costum", "dama", "barbati", "papuci", "pantaloni", "hanorac"]),
    ("🌻 Дом и сад", ["casa-gradina", "mobila", "canapea", "pat", "masa", "dulap", "bucatarie", "scule", "bormasina", "gradina", "foisor", "flori", "termopan", "usi", "lemn", "containere", "generator"]),
    ("⚽ Спорт и хобби", ["sport", "bicicleta", "trotinet", "pescuit", "fitness", "muzica", "chitara", "jocuri", "carti", "enciclopedi"]),
    ("👶 Детский мир", ["mama", "copil", "carucior", "patut", "bebe", "jucari", "hainute"]),
    ("🐾 Животные", ["animale", "caine", "pisica", "catel", "acvariu", "papagal", "ciobanesc"]),
    ("💼 Работа и услуги", ["locuri", "munca", "job", "angaj", "sofer", "servicii", "reparatii", "transport", "curierat"]),
]


def detect_smart_category(title: str, raw_cat: Optional[str], url: str) -> str:
    combined_text = f"{title} {raw_cat or ''} {url}".lower()
    for cat_label, keywords in CATEGORY_RULES:
        if any(kw in combined_text for kw in keywords):
            return cat_label
    return "📦 Другое"


def _evaluate_timestamps(
    created_str: Optional[str],
    refreshed_str: Optional[str],
    max_age_minutes: int,
) -> Tuple[bool, bool]:
    if not created_str and not refreshed_str:
        return False, False

    try:
        now_utc: datetime = datetime.now(timezone.utc)
        created_utc: Optional[datetime] = None
        refreshed_utc: Optional[datetime] = None

        if created_str:
            dt_c = datetime.fromisoformat(created_str)
            if dt_c.tzinfo is None:
                dt_c = dt_c.replace(tzinfo=timezone.utc)
            created_utc = dt_c.astimezone(timezone.utc)

        if refreshed_str:
            dt_r = datetime.fromisoformat(refreshed_str)
            if dt_r.tzinfo is None:
                dt_r = dt_r.replace(tzinfo=timezone.utc)
            refreshed_utc = dt_r.astimezone(timezone.utc)

        effective_utc: datetime = (
            created_utc if settings.IGNORE_BUMPED_OFFERS else (refreshed_utc or created_utc)
        )

        age_seconds: float = (now_utc - effective_utc).total_seconds()
        is_too_old: bool = age_seconds > (max_age_minutes * 60)

        is_bumped: bool = False
        if created_utc and refreshed_utc:
            bump_delta: float = (refreshed_utc - created_utc).total_seconds()
            if bump_delta > 14400.0 or created_utc.date() != refreshed_utc.date():
                is_bumped = True

        return is_bumped, is_too_old
    except Exception:
        return False, False


def _find_offers_in_dict(payload: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(payload, dict):
        for candidate_key in ("ads", "data", "offers"):
            val = payload.get(candidate_key)
            if isinstance(val, list) and len(val) > 0:
                sample = val[0]
                if isinstance(sample, dict) and "id" in sample and ("photos" in sample or "created_time" in sample):
                    return val

        for val in payload.values():
            result = _find_offers_in_dict(val)
            if result is not None:
                return result

    elif isinstance(payload, list):
        if len(payload) > 0:
            sample = payload[0]
            if isinstance(sample, dict) and "id" in sample and ("photos" in sample or "created_time" in sample):
                return payload
        for elem in payload:
            result = _find_offers_in_dict(elem)
            if result is not None:
                return result

    return None


def parse_json_offer(item: Dict[str, Any], base_url: str) -> Optional[OfferDTO]:
    try:
        offer_id: Optional[str] = str(item.get("id")) if item.get("id") else None
        title: Optional[str] = item.get("title")
        raw_url: Optional[str] = item.get("url")

        if not offer_id or not title or not raw_url:
            return None

        full_url: str = to_absolute_url(base_url, raw_url)

        price: Optional[str] = None
        params: List[Dict[str, Any]] = item.get("params", [])
        for param in params:
            if param.get("key") == "price":
                val = param.get("value")
                if isinstance(val, dict):
                    price = val.get("label")
                elif isinstance(val, str):
                    price = val
                break

        if not price and "price" in item:
            p_val = item["price"]
            if isinstance(p_val, dict):
                price = p_val.get("displayValue") or str(p_val.get("value"))
            elif isinstance(p_val, (str, int, float)):
                price = str(p_val)

        if price:
            price = price.split(".css-")[0].split("{")[0].strip()[:100]

        photo_url: Optional[str] = None
        photos: List[Any] = item.get("photos", [])
        if photos:
            first_photo = photos[0]
            if isinstance(first_photo, dict):
                photo_url = first_photo.get("link")
            elif isinstance(first_photo, str):
                photo_url = first_photo

            if photo_url:
                photo_url = photo_url.split(";")[0]

        location_str: Optional[str] = None
        location_data = item.get("location")
        if isinstance(location_data, dict):
            city_name = location_data.get("city", {}).get("name")
            district_name = location_data.get("district", {}).get("name")
            parts = [p for p in (city_name, district_name) if p]
            if parts:
                location_str = ", ".join(parts)[:255]

        category_obj = item.get("category", {})
        raw_cat_name: Optional[str] = category_obj.get("name") if isinstance(category_obj, dict) else None

        category_name: str = detect_smart_category(title, raw_cat_name, full_url)

        user_obj = item.get("user", {})
        seller_id: Optional[str] = str(user_obj.get("id")) if isinstance(user_obj, dict) and user_obj.get("id") else None

        created_at_str: Optional[str] = item.get("created_time")
        refreshed_at_str: Optional[str] = item.get("last_refresh_time")

        is_bumped, is_too_old = _evaluate_timestamps(
            created_str=created_at_str,
            refreshed_str=refreshed_at_str,
            max_age_minutes=settings.MAX_OFFER_AGE_MINUTES,
        )

        promo_info = item.get("promotion", {})
        is_promoted: bool = bool(promo_info.get("top_ad") or promo_info.get("highlighted"))

        return OfferDTO(
            olx_offer_id=offer_id,
            title=title.strip()[:255],
            url=full_url,
            price=price,
            photo_url=photo_url,
            location=location_str,
            published_at=created_at_str or refreshed_at_str,
            phone=None,
            category_name=category_name,
            seller_id=seller_id,
            is_bumped=is_bumped,
            is_promoted=is_promoted,
            is_too_old=is_too_old,
        )
    except Exception as exc:
        logger.debug("Failed parsing JSON offer item: %s", exc)
        return None


def _extract_image_url(card: LexborNode, base_url: str) -> Optional[str]:
    for elem in card.css("source, img"):
        for attr in ("srcset", "data-srcset", "src", "data-src"):
            raw_val = elem.attributes.get(attr)
            if not raw_val or raw_val.startswith("data:image"):
                continue

            decoded_val = unquote(raw_val)
            match = re.search(r"(https?://[^\s\"\'&,]+apollo\.olxcdn\.com/v1/files/[a-zA-Z0-9_-]+)", decoded_val)
            if match:
                base_img = match.group(1).rstrip("/")
                if base_img.endswith("/image"):
                    return base_img
                return f"{base_img}/image"

            if decoded_val.startswith("http://") or decoded_val.startswith("https://"):
                return decoded_val.split(" ")[0].strip()

            if decoded_val.startswith("/"):
                return to_absolute_url(base_url, decoded_val.split(" ")[0].strip())

    return None


def _fallback_parse_dom(parser: LexborHTMLParser, base_url: str) -> List[OfferDTO]:
    offers: List[OfferDTO] = []
    cards = parser.css("div[data-cy='l-card']")
    for card in cards:
        try:
            link_node: Optional[LexborNode] = card.css_first("a[href]")
            if not link_node:
                continue

            href = link_node.attributes.get("href", "")
            if not href:
                continue

            full_url = to_absolute_url(base_url, href)

            title_node: Optional[LexborNode] = card.css_first("h4, h6")
            title = title_node.text(strip=True)[:255] if title_node else "No title"

            price_node: Optional[LexborNode] = card.css_first("p[data-testid='ad-price']")
            price: Optional[str] = None
            if price_node:
                for style_tag in price_node.css("style"):
                    style_tag.decompose()
                raw_price: str = price_node.text(strip=True)
                if raw_price:
                    price = raw_price.split(".css-")[0].split("{")[0].strip()[:100]

            loc_node: Optional[LexborNode] = card.css_first("p[data-testid='location-date']")
            location_val: Optional[str] = None
            raw_date_str: str = ""
            if loc_node:
                full_loc_text = loc_node.text(strip=True)
                parts = full_loc_text.split(" - ")
                location_val = parts[0][:100]
                if len(parts) > 1:
                    raw_date_str = parts[1].lower()

            is_bumped: bool = False
            today_keywords = ("сегодня", "dzisiaj", "сьогодні", "today", "azi")
            if raw_date_str and not any(kw in raw_date_str for kw in today_keywords):
                is_bumped = True

            is_promoted: bool = False
            for badge in card.css("span, div"):
                badge_text = badge.text(strip=True).upper()
                if badge_text in {"ТОП", "TOP", "PROMO", "WYRÓŻNIONE"}:
                    is_promoted = True
                    break

            photo_url: Optional[str] = _extract_image_url(card, base_url)

            card_id: str = str(card.attributes.get("id", ""))
            if not card_id:
                id_parts = href.split("-ID")
                card_id = id_parts[-1].split(".")[0] if len(id_parts) > 1 else str(abs(hash(href)))

            category_name = detect_smart_category(title, None, full_url)

            offers.append(
                OfferDTO(
                    olx_offer_id=card_id,
                    title=title,
                    url=full_url,
                    price=price,
                    photo_url=photo_url,
                    location=location_val,
                    published_at=raw_date_str or None,
                    phone=None,
                    category_name=category_name,
                    seller_id=None,
                    is_bumped=is_bumped,
                    is_promoted=is_promoted,
                    is_too_old=False,
                )
            )
        except Exception as exc:
            logger.debug("DOM fallback card parse error: %s", exc)
            continue
    return offers


def extract_offers(html_content: str, base_url: str) -> List[OfferDTO]:
    try:
        parser = LexborHTMLParser(html_content)
        next_data_script = parser.css_first("script#__NEXT_DATA__")

        if next_data_script and next_data_script.text():
            try:
                payload: Dict[str, Any] = json.loads(next_data_script.text())
                raw_offers = _find_offers_in_dict(payload)
                if raw_offers:
                    parsed_offers: List[OfferDTO] = []
                    for item in raw_offers:
                        dto = parse_json_offer(item, base_url)
                        if dto:
                            parsed_offers.append(dto)
                    if parsed_offers:
                        logger.info("Successfully extracted %d offers via clean JSON payload", len(parsed_offers))
                        return parsed_offers
            except json.JSONDecodeError as json_exc:
                logger.warning("Failed to decode __NEXT_DATA__ JSON: %s", json_exc)

        logger.info("Falling back to DOM selector parsing")
        dom_offers = _fallback_parse_dom(parser, base_url)
        logger.info("Extracted %d offers via DOM fallback", len(dom_offers))
        return dom_offers
    except Exception as exc:
        logger.error("Global extract_offers failure: %s", exc, exc_info=True)
        return []