
import logging
import statistics
from datetime import datetime, timezone

logger = logging.getLogger("PITOS_AI")

SUPPORTED_GROUPS = {
    "Soccer",
    "Basketball",
    "Tennis",
    "Ice Hockey",
    "Baseball",
}

MIN_BOOKMAKERS = 3
MIN_EV = 0.03
MIN_ODDS = 1.50
MAX_ODDS = 5.00

# Zapamiętane publikacje podczas działania procesu
published_events = set()


def calculate_market(event):
    """
    Oblicza prawdopodobieństwa rynkowe bez marży
    dla poszczególnych bukmacherów.
    """
    probabilities = {}
    best_odds = {}
    bookmaker_count = {}

    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue

            outcomes = market.get("outcomes", [])

            if len(outcomes) < 2:
                continue

            prices = [
                (item.get("name"), float(item.get("price", 0)))
                for item in outcomes
            ]

            if any(price <= 1 for _, price in prices):
                continue

            total_implied = sum(1 / price for _, price in prices)

            if total_implied <= 0:
                continue

            for name, price in prices:
                fair_probability = (1 / price) / total_implied

                probabilities.setdefault(name, []).append(
                    fair_probability
                )

                best_odds[name] = max(
                    best_odds.get(name, 0),
                    price
                )

                bookmaker_count[name] = (
                    bookmaker_count.get(name, 0) + 1
                )

    candidates = []

    for outcome, values in probabilities.items():
        if bookmaker_count.get(outcome, 0) < MIN_BOOKMAKERS:
            continue

        fair_probability = statistics.median(values)
        odds = best_odds.get(outcome, 0)

        if not MIN_ODDS <= odds <= MAX_ODDS:
            continue

        ev = (fair_probability * odds) - 1

        if ev < MIN_EV:
            continue

        candidates.append({
            "outcome": outcome,
            "odds": odds,
            "probability": fair_probability,
            "ev": ev,
            "bookmakers": bookmaker_count[outcome],
        })

    return candidates


async def scan_sports(api, bot, chat_id):
    logger.info("PITOS VALUE HUNTER: scan started")

    sports = await api.get_sports()

    selected = [
        sport for sport in sports
        if sport.get("active")
        and sport.get("group") in SUPPORTED_GROUPS
    ]

    logger.info("Selected sports: %s", len(selected))

    total_candidates = 0

    for sport in selected:
        sport_key = sport.get("key")
        sport_name = sport.get("group", sport_key)

        try:
            events = await api.get_odds(sport_key)

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

                candidates = calculate_market(event)

                for candidate in candidates:
                    unique_id = (
                        event_id,
                        candidate["outcome"],
                    )

                    if unique_id in published_events:
                        continue

                    home = event.get("home_team", "Unknown")
                    away = event.get("away_team", "Unknown")

                    message = (
                        "🔎 PITOS AI | VALUE CANDIDATE\n\n"
                        f"🏆 Dyscyplina: {sport_name}\n"
                        f"⚔️ Mecz: {home} - {away}\n"
                        f"🎯 Selekcja: {candidate['outcome']}\n\n"
                        f"📈 Najlepszy kurs: {candidate['odds']:.2f}\n"
                        f"📊 Prawdopodobieństwo rynkowe: "
                        f"{candidate['probability'] * 100:.1f}%\n"
                        f"💹 Szacowane EV: "
                        f"{candidate['ev'] * 100:.2f}%\n"
                        f"🏦 Źródła: {candidate['bookmakers']}\n\n"
                        "⚠️ Kandydat wykryty na podstawie "
                        "różnic między kursami bukmacherów. "
                        "Nie jest to niezależna prognoza ani "
                        "potwierdzona przewaga."
                    )

                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                    )

                    published_events.add(unique_id)
                    total_candidates += 1

            logger.info(
                "Scanned %s | events: %s",
                sport_key,
                len(events),
            )

        except Exception:
            logger.exception(
                "Scanner error for sport: %s",
                sport_key,
            )

    logger.info(
        "VALUE HUNTER FINISHED | Candidates: %s",
        total_candidates,
    )

    return total_candidates
