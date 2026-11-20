
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
MIN_ODDS = 1.20
MAX_ODDS = 4.50

BANKROLL = 400.0
UNIT_VALUE = 25.0
TEST_STAKE_UNITS = 1


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
                    price = float(item.get("price", 0))
                    name = item.get("name")
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
                    "probability": (1 / price) / overround,
                    "odds": price,
                    "bookmaker": bookmaker_name,
                })

    candidates = []

    for outcome, quotes in markets.items():
        # Jedna obserwacja na bukmachera.
        unique_quotes = {}
        for quote in quotes:
            key = quote["bookmaker"]
            if key not in unique_quotes:
                unique_quotes[key] = quote

        quotes = list(unique_quotes.values())

        if len(quotes) < MIN_BOOKMAKERS:
            continue

        probabilities = [q["probability"] for q in quotes]
        fair_probability = statistics.median(probabilities)
        best_odds = max(q["odds"] for q in quotes)

        if not MIN_ODDS <= best_odds <= MAX_ODDS:
            continue

        ev = fair_probability * best_odds - 1

        candidates.append({
            "outcome": outcome,
            "odds": best_odds,
            "probability": fair_probability,
            "ev": ev,
            "bookmakers": len(quotes),
        })

    return candidates


def classify_candidate(candidate):
    probability = candidate["probability"]
    ev = candidate["ev"]
    odds = candidate["odds"]

    # To są etykiety jakości kandydatów, nie gwarancje wyniku.
    if probability >= 0.70 and 1.20 <= odds <= 1.80:
        return "PEWNIACZKI"

    if probability >= 0.50 and ev >= 0.04:
        return "PEREŁKI"

    if probability >= 0.35 and ev >= 0.03:
        return "VALUE SINGLE"

    return None


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
        existing = await session.execute(
            select(TipRecord.id).where(
                TipRecord.record_key == record_key
            )
        )

        if existing.scalar_one_or_none() is not None:
            return False

        tip = TipRecord(
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
            stake_units=TEST_STAKE_UNITS,
            stake_amount=UNIT_VALUE * TEST_STAKE_UNITS,
            details=details,
        )

        session.add(tip)
        await session.commit()
        return True


def format_candidate(category, sport, event, candidate):
    home = event.get("home_team", "Nieznana drużyna")
    away = event.get("away_team", "Nieznana drużyna")

    return (
        f"🏆 PITOS AI | {category}\n\n"
        f"🏅 Dyscyplina: {sport}\n"
        f"⚔️ Mecz: {home} – {away}\n"
        f"🎯 Typ: {candidate['outcome']}\n\n"
        f"📈 Kurs: {candidate['odds']:.2f}\n"
        f"📊 Prawdopodobieństwo rynkowe: "
        f"{candidate['probability'] * 100:.1f}%\n"
        f"💹 Szacowane EV: {candidate['ev'] * 100:.2f}%\n"
        f"🏦 Bukmacherzy: {candidate['bookmakers']}\n\n"
        f"💰 Stawka testowa: 1j = {UNIT_VALUE:.0f} zł\n"
        f"🏦 Budżet testowy: {BANKROLL:.0f} zł\n\n"
        "⚠️ Analiza oparta na kursach rynkowych. "
        "Nie jest to niezależna prognoza ani gwarancja wygranej."
    )


async def publish_candidate(bot, chat_id, sport, event, candidate):
    category = classify_candidate(candidate)
    if not category:
        return False

    event_id = event.get("id", "")
    outcome = candidate["outcome"]
    record_key = f"{event_id}:{outcome}:{category}"

    if await already_published(record_key):
        return False

    home = event.get("home_team", "")
    away = event.get("away_team", "")

    message = format_candidate(category, sport, event, candidate)

    saved = await save_tip(
        record_key=record_key,
        category=category,
        event_id=event_id,
        sport=sport,
        home=home,
        away=away,
        selection=outcome,
        odds=candidate["odds"],
        probability=candidate["probability"],
        ev=candidate["ev"],
        details="Market consensus estimate; not independently validated.",
    )

    if not saved:
        return False

    await bot.send_message(chat_id=chat_id, text=message)
    return True


async def build_ako2(bot, chat_id, candidates):
    # AKO2 składamy tylko z dwóch różnych wydarzeń.
    eligible = [
        item for item in candidates
        if item["candidate"]["odds"] >= 1.20
        and item["candidate"]["probability"] >= 0.58
    ]

    eligible.sort(
        key=lambda x: x["candidate"]["probability"],
        reverse=True,
    )

    for first, second in combinations(eligible, 2):
        if first["event_id"] == second["event_id"]:
            continue

        odds_a = first["candidate"]["odds"]
        odds_b = second["candidate"]["odds"]
        combined_odds = odds_a * odds_b

        if combined_odds < 1.44:
            continue

        probability = (
            first["candidate"]["probability"]
            * second["candidate"]["probability"]
        )

        record_key = (
            f"AKO2:{first['event_id']}:{first['candidate']['outcome']}:"
            f"{second['event_id']}:{second['candidate']['outcome']}"
        )

        if await already_published(record_key):
            continue

        text = (
            "🎟️ PITOS AI | AKO2\n\n"
            f"1️⃣ {first['home']} – {first['away']}\n"
            f"Typ: {first['candidate']['outcome']}\n"
            f"Kurs: {odds_a:.2f}\n\n"
            f"2️⃣ {second['home']} – {second['away']}\n"
            f"Typ: {second['candidate']['outcome']}\n"
            f"Kurs: {odds_b:.2f}\n\n"
            f"📈 Kurs łączny: {combined_odds:.2f}\n"
            f"📊 Orientacyjne prawdopodobieństwo: "
            f"{probability * 100:.1f}%\n"
            f"💰 Stawka testowa: 1j = {UNIT_VALUE:.0f} zł\n\n"
            "⚠️ Prawdopodobieństwo łączone zakłada niezależność zdarzeń. "
            "To założenie może być niedokładne. Sprawdź warunki promocji "
            "i dostępność rynków u bukmachera."
        )

        saved = await save_tip(
            record_key=record_key,
            category="AKO2",
            event_id=f"{first['event_id']}+{second['event_id']}",
            sport="Mixed",
            home=first["home"],
            away=second["away"],
            selection=(
                f"{first['candidate']['outcome']} + "
                f"{second['candidate']['outcome']}"
            ),
            odds=combined_odds,
            probability=probability,
            ev=0.0,
            details="Two-leg accumulator; independence not verified.",
        )

        if saved:
            await bot.send_message(chat_id=chat_id, text=text)
            return True

    return False


async def scan_sports(api, bot, chat_id):
    logger.info("PITOS AI V2 | QUALITY FIRST SCAN STARTED")

    sports = await api.get_sports()

    selected = [
        sport for sport in sports
        if sport.get("active")
        and sport.get("group") in SUPPORTED_GROUPS
    ]

    logger.info("Supported active sport keys: %s", len(selected))

    published = 0
    ako_candidates = []
    event_count = 0

    for sport in selected:
        sport_key = sport.get("key")
        sport_name = sport.get("group", sport_key)

        try:
            events = await api.get_odds(sport_key)
            event_count += len(events)

            for event in events:
                commence = event.get("commence_time")

                if commence:
                    event_time = datetime.fromisoformat(
                        commence.replace("Z", "+00:00")
                    )
                    if event_time <= datetime.now(timezone.utc):
                        continue

                candidates = calculate_market(event)

                for candidate in candidates:
                    category = classify_candidate(candidate)
                    if not category:
                        continue

                    item = {
                        "event_id": event.get("id", ""),
                        "home": event.get("home_team", ""),
                        "away": event.get("away_team", ""),
                        "candidate": candidate,
                    }

                    ako_candidates.append(item)

                    if await publish_candidate(
                        bot, chat_id, sport_name, event, candidate
                    ):
                        published += 1

            logger.info(
                "Scanned %s | events: %s",
                sport_key,
                len(events),
            )

        except Exception:
            logger.exception("Scanner error: %s", sport_key)

    try:
        if await build_ako2(bot, chat_id, ako_candidates):
            published += 1
    except Exception:
        logger.exception("AKO2 builder error")

    logger.info(
        "QUALITY SCAN FINISHED | Events: %s | Published: %s",
        event_count,
        published,
    )

    if published == 0:
        logger.info("QUALITY FIRST: no selections passed the filters.")

    return published
