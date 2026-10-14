import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse
from curl_cffi.requests import AsyncSession, Response
from core.config import get_settings
from parser.extractor import extract_offers, parse_json_offer
from parser.schemas import OfferDTO

logger: logging.Logger = logging.getLogger("app.parser.client")
settings = get_settings()


class OLXClient:
    def __init__(self) -> None:
        self._session: Optional[AsyncSession] = None
        self._timeout: int = settings.REQUEST_TIMEOUT
        self._impersonate: str = settings.CURL_IMPERSONATE
        self._proxy: Optional[str] = settings.PROXY_URL
        self._phone_cooldown_until: float = 0.0

    @property
    def phone_cooldown_until(self) -> float:
        return self._phone_cooldown_until

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession(
                impersonate=self._impersonate,
                timeout=self._timeout,
                proxy=self._proxy,
            )
        return self._session

    async def fetch_html(self, url: str, max_retries: int = 3) -> Optional[str]:
        session = await self._get_session()
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }

        for attempt in range(1, max_retries + 1):
            try:
                response: Response = await session.get(url, headers=headers, allow_redirects=True)
                if response.status_code == 200:
                    return response.text

                if response.status_code in {403, 429}:
                    logger.warning(
                        "Rate-limited or challenged (HTTP %d) on attempt %d for URL: %s",
                        response.status_code,
                        attempt,
                        url,
                    )
                    await asyncio.sleep(2.0 * attempt)
                    continue

                logger.warning(
                    "Unexpected HTTP status %d on attempt %d for URL: %s",
                    response.status_code,
                    attempt,
                    url,
                )
            except Exception as exc:
                logger.error(
                    "Network error on attempt %d for URL %s: %s",
                    attempt,
                    url,
                    exc,
                )
                await asyncio.sleep(1.5 * attempt)

        logger.error("Failed to fetch HTML after %d attempts for URL: %s", max_retries, url)
        return None

    async def _try_fetch_api_offers(self, url: str) -> Optional[List[OfferDTO]]:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or "www.olx.ro"
            query_word = ""

            if "/q-" in parsed.path:
                parts = parsed.path.split("/q-")
                if len(parts) > 1:
                    query_word = parts[1].strip("/").split("/")[0]

            qs = parse_qs(parsed.query)
            if not query_word and "query" in qs:
                query_word = qs["query"][0]

            query_param = f"&query={query_word}" if query_word else ""
            api_endpoint = f"https://{domain}/api/v1/offers/?offset=0&limit=50&sort_by=created_at:desc{query_param}"
            session = await self._get_session()

            headers = {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }

            resp: Response = await session.get(api_endpoint, headers=headers, allow_redirects=True)
            if resp.status_code == 200:
                payload = resp.json()
                data_list = payload.get("data", [])
                if data_list and isinstance(data_list, list):
                    parsed_dtos: List[OfferDTO] = []
                    for raw_item in data_list:
                        dto = parse_json_offer(raw_item, base_url=f"https://{domain}")
                        if dto:
                            parsed_dtos.append(dto)
                    if parsed_dtos:
                        logger.info("Successfully fetched %d offers via direct Mobile REST API for %s", len(parsed_dtos), domain)
                        return parsed_dtos
        except Exception as exc:
            logger.debug("Direct API attempt skipped for %s: %s", url, exc)

        return None

    async def fetch_phone_number(self, offer_id: str, offer_url: str) -> Optional[str]:
        current_time: float = time.time()
        if current_time < self._phone_cooldown_until:
            return None

        try:
            session = await self._get_session()
            parsed = urlparse(offer_url)
            domain = parsed.netloc or "www.olx.ro"
            phone_api_url = f"https://{domain}/api/v1/offers/{offer_id}/limited-phones/"

            headers = {
                "Accept": "*/*",
                "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": offer_url,
                "Origin": f"https://{domain}",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
            resp: Response = await session.get(phone_api_url, headers=headers, allow_redirects=True)

            if resp.status_code == 200:
                payload: Dict[str, Any] = resp.json()
                data = payload.get("data", {})
                phones: List[str] = data.get("phones", [])
                if phones:
                    return ", ".join(phones)
                phone_str: Optional[str] = data.get("phone")
                if phone_str:
                    return phone_str
                return None

            if resp.status_code in {429, 403}:
                logger.warning("OLX phone rate-limit reached. Pausing phone requests for 10 minutes.")
                self._phone_cooldown_until = time.time() + 600.0
                return None

            return None
        except Exception as exc:
            logger.debug("Could not extract phone for offer %s: %s", offer_id, exc)
            return None

    async def get_offers(self, url: str) -> List[OfferDTO]:
        api_offers = await self._try_fetch_api_offers(url)
        if api_offers:
            return api_offers

        html = await self.fetch_html(url)
        if not html:
            return []
        return extract_offers(html, base_url=url)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("OLXClient session closed.")