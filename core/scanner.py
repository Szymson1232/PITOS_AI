
import logging
import statistics
from datetime import datetime, timezone
from itertools import combinations

from sqlalchemy import select

from database.connection import SessionLocal
from database.models import TipRecord

logger = logging.getLogger("PITOS_AI")

SUPPORTED_GROUPS = {
    "Soccer",
    "Basketball",
    "Tennis",
    "Ice Hockey",
    "Baseball",
}

MIN_BOOKMAKERS = 5
MAX_ODDS = 4.50

BANKROLL = 400.0
UNIT_VALUE = 25.0
MAX_PUBLICATIONS = 10

# Ostrożne progi startowe. To nadal estymacje rynkowe,
# a nie zweryfikowany model predykcyjny.
AKO_MIN_PROBABILITY = 0.65
AKO_MIN_EV = 0.00
AKO_MIN_COMBINED_PROBABILITY = 0.42

SINGLE_MIN_PROBABILITY = 0.35
SINGLE_MIN_EV = 0.05


def calculate_market(event):
    markets = {}

    for bookmaker in event.get("bookmakers", []):
        bookmaker_name = bookmaker.get("key", "")

        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue

            outcomes = market.get("outcomes", [])
            if len(outcomes) < 2:
                continue

            prices = {}

            for item in outcomes:
                try:
                    name = item.get("name")
                    price = float(item.get("price", 0))

                    if name and price > 1:
                        prices[name] = price
                except (TypeError, ValueError):
                    continue

            if len(prices) != len(outcomes):
                continue

            overround = sum(1 / price for price in prices.values())

            if overround <= 0:
                continue

            for name, price in prices.items():
                markets.setdefault(name, []).append({
                    "bookmaker": bookmaker_name,
                    "probability": (1 / price) / overround,
                    "odds": price,
                })

    candidates = []

    for outcome, quotes in markets.items():
        unique_quotes = {}

        for quote in quotes:
            bookmaker = quote["bookmaker"]

            if bookmaker and bookmaker not in unique_quotes:
                unique_quotes[bookmaker] = quote

        quotes = list(unique_quotes.values())

        if len(quotes) < MIN_BOOKMAKERS:
            continue

        probability = statistics.median(
            quote["probability"] for quote in quotes
        )

        best_odds = max(
            quote["odds"] for quote in quotes
        )

        if not 1.20 <= best_odds <= MAX_ODDS:
            continue

        ev = probability * best_odds - 1

        candidates.append({
            "outcome": outcome,
            "odds": best_odds,
            "probability": probability,
            "ev": ev,
            "bookmakers": len(quotes),
        })

    return candidates


async def already_published(record_key):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TipRecord.id).where(
                TipRecord.record_key == record_key
            )
        )
        return result.scalar_one_or_none() is not None


async def save_tip(
    record_key,
    category,
    event_id,
    sport,
    home,
    away,
    selection,
    odds,
    probability,
    ev,
    details="",
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TipRecord.id).where(
                TipRecord.record_key == record_key
            )
        )

        if result.scalar_one_or_none() is not None:
            return False

        session.add(
            TipRecord(
                record_key=record_key,
                category=category,
                event_id=event_id,
                sport=sport,
                home_team=home,
                away_team=away,
                selection=selection,
                odds=odds,
                probability=probability,
                ev=ev,
                stake_units=1,
                stake_amount=UNIT_VALUE,
                details=details,
            )
        )

        await session.commit()
        return True


def value_single_ok(candidate):
    return (
        candidate["probability"] >= SINGLE_MIN_PROBABILITY
        and candidate["ev"] >= SINGLE_MIN_EV
        and 1.50 <= candidate["odds"] <= MAX_ODDS
    )


def ako_leg_ok(candidate):
    return (
        candidate["probability"] >= AKO_MIN_PROBABILITY
        and candidate["ev"] >= AKO_MIN_EV
        and candidate["odds"] >= 1.20
        and candidate["bookmakers"] >= MIN_BOOKMAKERS
    )


async def publish_single(bot, chat_id, item):
    event = item["event"]
    candidate = item["candidate"]

    event_id = item["event_id"]
    selection = candidate["outcome"]

    record_key = f"VALUE_SINGLE:{event_id}:{selection}"

    if await already_published(record_key):
        return False

    message = (
        "📈 PITOS AI | VALUE SINGLE\n\n"
        f"🏆 Dyscyplina: {item['sport']}\n"
        f"⚔️ Mecz: {event['home_team']} – {event['away_team']}\n"
        f"🎯 Typ: {selection}\n\n"
        f"📊 Kurs: {candidate['odds']:.2f}\n"
        f"📉 Prawdopodobieństwo rynkowe: "
        f"{candidate['probability'] * 100:.1f}%\n"
        f"💹 Orientacyjne EV: {candidate['ev'] * 100:.2f}%\n"
        f"🏦 Źródła: {candidate['bookmakers']}\n\n"
        f"💰 Stawka testowa: 1j = {UNIT_VALUE:.0f} zł\n"
        f"🏦 Budżet testowy: {BANKROLL:.0f} zł\n\n"
        "⚠️ VALUE SINGLE oznacza wyższe ryzyko. "
        "EV wyliczono z kursów rynkowych i nie jest potwierdzoną przewagą."
    )

    await bot.send_message(chat_id=chat_id, text=message)

    return await save_tip(
        record_key=record_key,
        category="VALUE SINGLE",
        event_id=event_id,
        sport=item["sport"],
        home=event["home_team"],
        away=event["away_team"],
        selection=selection,
        odds=candidate["odds"],
        probability=candidate["probability"],
        ev=candidate["ev"],
        details="Market-derived estimate; not independently validated.",
    )


async def publish_ako2(bot, chat_id, first, second):
    a = first["candidate"]
    b = second["candidate"]

    combined_odds = a["odds"] * b["odds"]
    combined_probability = a["probability"] * b["probability"]

    if combined_odds < 1.44:
        return False

    if combined_probability < AKO_MIN_COMBINED_PROBABILITY:
        return False

    # Stabilny klucz, niezależny od kolejności pary.
    legs = sorted([
        (first["event_id"], a["outcome"]),
        (second["event_id"], b["outcome"]),
    ])

    record_key = (
        f"AKO2:{legs[0][0]}:{legs[0][1]}:"
        f"{legs[1][0]}:{legs[1][1]}"
    )

    if await already_published(record_key):
        return False

    message = (
        "🎟️ PITOS AI | QUALITY AKO2\n\n"
        "1️⃣ "
        f"{first['event']['home_team']} – "
        f"{first['event']['away_team']}\n"
        f"Typ: {a['outcome']}\n"
        f"Kurs: {a['odds']:.2f}\n\n"
        "2️⃣ "
        f"{second['event']['home_team']} – "
        f"{second['event']['away_team']}\n"
        f"Typ: {b['outcome']}\n"
        f"Kurs: {b['odds']:.2f}\n\n"
        f"📈 Kurs łączny: {combined_odds:.2f}\n"
        f"📊 Orientacyjne prawdopodobieństwo: "
        f"{combined_probability * 100:.1f}%\n\n"
        f"💰 Stawka testowa: 1j = {UNIT_VALUE:.0f} zł\n"
        f"🏦 Budżet testowy: {BANKROLL:.0f} zł\n\n"
        "⚠️ Wyliczenie łącznego prawdopodobieństwa zakłada "
        "niezależność zdarzeń. Korelacja nie jest jeszcze modelowana. "
        "Sprawdź warunki promocji u bukmachera."
    )

    await bot.send_message(chat_id=chat_id, text=message)

    return await save_tip(
        record_key=record_key,
        category="AKO2",
        event_id=f"{first['event_id']}+{second['event_id']}",
        sport="Mixed",
        home=first["event"]["home_team"],
        away=second["event"]["away_team"],
        selection=f"{a['outcome']} + {b['outcome']}",
        odds=combined_odds,
        probability=combined_probability,
        ev=0.0,
        details="Two-leg accumulator; independence not verified.",
    )


async def scan_sports(api, bot, chat_id):
    logger.info("PITOS QUALITY FIRST SCAN STARTED")

    sports = await api.get_sports()

    selected = [
        sport for sport in sports
        if sport.get("active")
        and sport.get("group") in SUPPORTED_GROUPS
    ]

    logger.info("Supported sport keys: %s", len(selected))

    all_items = []
    event_count = 0

    for sport in selected:
        sport_key = sport.get("key")
        sport_name = sport.get("group", sport_key)

        try:
            events = await api.get_odds(sport_key)
            event_count += len(events)

            for event in events:
                event_id = event.get("id")

                if not event_id:
                    continue

                commence = event.get("commence_time")

                if commence:
                    event_time = datetime.fromisoformat(
                        commence.replace("Z", "+00:00")
                    )

                    if event_time <= datetime.now(timezone.utc):
                        continue

                for candidate in calculate_market(event):
                    all_items.append({
                        "event_id": event_id,
                        "event": event,
                        "sport": sport_name,
                        "candidate": candidate,
                    })

            logger.info(
                "Scanned %s | events: %s",
                sport_key,
                len(events),
            )

        except Exception:
            logger.exception("Scanner error: %s", sport_key)

    # Najpierw budujemy pulę jakościowych nóg AKO2.
    ako_pool = [
        item for item in all_items
        if ako_leg_ok(item["candidate"])
    ]

    # Sortowanie po prawdopodobieństwie, potem EV.
    ako_pool.sort(
        key=lambda item: (
            item["candidate"]["probability"],
            item["candidate"]["ev"],
        ),
        reverse=True,
    )

    publications = 0
    used_events = set()

    # Publikujemy najwyżej 10 kuponów łącznie.
    for first, second in combinations(ako_pool, 2):
        if publications >= MAX_PUBLICATIONS:
            break

        if first["event_id"] == second["event_id"]:
            continue

        if first["event_id"] in used_events:
            continue

        if second["event_id"] in used_events:
            continue

        combined_probability = (
            first["candidate"]["probability"]
            * second["candidate"]["probability"]
        )

        combined_odds = (
            first["candidate"]["odds"]
            * second["candidate"]["odds"]
        )

        if combined_probability < AKO_MIN_COMBINED_PROBABILITY:
            continue

        if combined_odds < 1.44:
            continue

        try:
            published = await publish_ako2(
                bot, chat_id, first, second
            )

            if published:
                publications += 1
                used_events.add(first["event_id"])
                used_events.add(second["event_id"])

        except Exception:
            logger.exception("AKO2 publication failed")

    # Dopiero potem ewentualne VALUE SINGLE.
    singles = [
        item for item in all_items
        if value_single_ok(item["candidate"])
        and item["event_id"] not in used_events
    ]

    singles.sort(
        key=lambda item: (
            item["candidate"]["ev"],
            item["candidate"]["probability"],
        ),
        reverse=True,
    )

    for item in singles:
        if publications >= MAX_PUBLICATIONS:
            break

        try:
            published = await publish_single(bot, chat_id, item)

            if published:
                publications += 1
                used_events.add(item["event_id"])

        except Exception:
            logger.exception("VALUE SINGLE publication failed")

    logger.info(
        "QUALITY SCAN FINISHED | Events: %s | Publications: %s/%s",
        event_count,
        publications,
        MAX_PUBLICATIONS,
    )

    return publications
