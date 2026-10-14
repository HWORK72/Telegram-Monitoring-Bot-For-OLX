import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
from parser.schemas import OfferDTO

CATEGORY_RULES: List[Tuple[str, List[str]]] = [
    ("🏠 Недвижимость и дом", [
        "imobiliare", "apartament", "garsonier", "casa", "case", "vila", "vile", "duplex",
        "teren", "terenuri", "chirie", "inchiri", "storia", "bloc nou", "decomandat",
        "dormitor", "camere", "rezidential", "casa-gradina", "mobila", "canapea", "pat",
        "masa", "dulap", "bucatarie", "scule", "bormasina", "gradina", "foisor", "flori",
        "termopan", "usi", "lemn", "containere", "generator", "constructii", "sanitar"
    ]),
    ("🚗 Автозапчасти", [
        "piese", "auto", "dezmembr", "motor", "diferential", "cutie viteze", "jante",
        "anvelope", "cauciuc", "bmw", "audi", "mercedes", "skoda", "volkswagen", "vw",
        "renault", "opel", "dacia", "ford", "camion", "utilaj", "parbriz", "bara",
        "pompa", "chiuloasa", "injector", "aripa", "volan", "etrier", "timonerie",
        "caddy", "crafter", "passat", "iveco"
    ]),
    ("📱 Электроника", [
        "electronice", "telefon", "iphone", "samsung", "xiaomi", "laptop", "pc",
        "televizor", "tv", "vape", "audio", "casti", "playstation", "ps5", "ps4",
        "xbox", "ipad", "airpods", "calculator", "electrocasnice", "frigider",
        "aragaz", "cuptor", "aspirator"
    ]),
    ("👗 Мода", [
        "moda", "haine", "incaltaminte", "adidasi", "pantofi", "rochie", "geaca",
        "tricou", "geanta", "inel", "aur", "argint", "ceas", "parfum", "costum",
        "dama", "barbati", "papuci", "pantaloni", "hanorac"
    ]),
    ("⚽ Спорт и хобби", [
        "sport", "bicicleta", "trotinet", "pescuit", "fitness", "muzica", "chitara",
        "jocuri", "carti", "enciclopedi"
    ]),
    ("👶 Детский мир", [
        "mama", "copil", "carucior", "patut", "bebe", "jucari", "hainute"
    ]),
    ("🐾 Животные", [
        "animale", "caine", "pisica", "catel", "acvariu", "papagal", "ciobanesc"
    ]),
    ("💼 Работа и услуги", [
        "locuri", "munca", "job", "angaj", "sofer", "servicii", "reparatii",
        "transport", "curierat"
    ]),
]


def _detect_smart_category(title: str, raw_cat: Optional[str], url: str) -> str:
    combined_text: str = f"{title} {raw_cat or ''} {url}".lower()
    for cat_label, keywords in CATEGORY_RULES:
        if any(kw in combined_text for kw in keywords):
            return cat_label
    return "📦 Другое"


def balance_and_filter_leads(
    offers: List[OfferDTO],
    batch_limit: int = 12,
    max_per_category: int = 2,
    blacklist: Optional[Set[str]] = None,
    stopwords: Optional[Set[str]] = None,
) -> Tuple[List[OfferDTO], str]:
    start_time: float = time.perf_counter()

    bl: Set[str] = blacklist or set()
    sw: Set[str] = stopwords or set()

    filtered_offers: List[OfferDTO] = []
    personal_blacklist_hits: int = 0
    stopwords_hits: int = 0

    for item in offers:
        if item.seller_id and item.seller_id in bl:
            personal_blacklist_hits += 1
            continue

        title_lower: str = item.title.lower()
        if any(w in title_lower for w in sw):
            stopwords_hits += 1
            continue

        filtered_offers.append(item)

    by_category: Dict[str, List[OfferDTO]] = defaultdict(list)
    for item in filtered_offers:
        cat_label: str = item.category_name or _detect_smart_category(item.title, None, item.url)
        by_category[cat_label].append(item)

    for cat_label in by_category:
        by_category[cat_label].sort(
            key=lambda x: str(x.published_at or ""),
            reverse=True,
        )

    selected_offers: List[OfferDTO] = []
    category_counts: Dict[str, int] = defaultdict(int)

    cycle_added: bool = True
    while cycle_added and len(selected_offers) < batch_limit:
        cycle_added = False
        for cat_label, cat_items in list(by_category.items()):
            if len(selected_offers) >= batch_limit:
                break
            if category_counts[cat_label] >= max_per_category:
                continue
            if cat_items:
                chosen: OfferDTO = cat_items.pop(0)
                selected_offers.append(chosen)
                category_counts[cat_label] += 1
                cycle_added = True

    elapsed: float = time.perf_counter() - start_time

    breakdown_lines: List[str] = []
    for cat_name, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        breakdown_lines.append(f"{cat_name}: {count}")

    breakdown_block: str = "\n".join(breakdown_lines) if breakdown_lines else "Общие категории"

    summary_card: str = (
        f"<code>На выдачу: • {len(selected_offers)}шт</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{breakdown_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Результат поиска</b> | <b>ОТСЕЯНО</b>\n"
        f"Нашлось: {len(offers)}  | Личный ЧС: {personal_blacklist_hits}\n"
        f"Итого: {len(selected_offers)}/{batch_limit}   | Стоп-слова: {stopwords_hits}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>Время:</b> {elapsed:.2f} сек"
    )

    return selected_offers, summary_card