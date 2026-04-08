import re


DIET_KEYWORDS = ("balanced", "junk", "healthy", "protein", "salad", "sugary", "clean")
STRESS_KEYWORDS = ("low", "medium", "moderate", "high")
ACTIVITY_KEYWORDS = ("walk", "workout", "gym", "yoga", "run", "exercise", "cycling")


def _extract_first(pattern: str, text: str):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def parse_health_text(text):
    lowered = text.lower()

    water = _extract_first(r"(\d+(?:\.\d+)?)\s*(?:l|liter|liters|litre|litres)\b", lowered)
    sleep = _extract_first(r"(\d+(?:\.\d+)?)\s*(?:hours|hour|hrs|hr)\s*(?:of\s*)?sleep", lowered)
    menstrual_cycle = _extract_first(r"day\s*(\d+)", lowered)

    activity = ""
    activity_match = re.search(
        r"((?:walk|workout|gym|yoga|run|exercise|cycling)[^,.!;]*)",
        lowered,
        flags=re.IGNORECASE,
    )
    if activity_match:
        activity = activity_match.group(1).strip()

    diet = next((keyword for keyword in DIET_KEYWORDS if keyword in lowered), "")
    stress = next((keyword for keyword in STRESS_KEYWORDS if keyword in lowered), "")

    if not activity:
        duration = _extract_first(r"(\d+\s*(?:mins|minutes|hrs|hours))", lowered)
        if duration and any(keyword in lowered for keyword in ACTIVITY_KEYWORDS):
            activity = duration

    return {
        "water_intake": float(water) if water else None,
        "activity": activity,
        "diet": diet,
        "sleep": float(sleep) if sleep else None,
        "stress": stress,
        "menstrual_cycle": f"day {menstrual_cycle}" if menstrual_cycle else "",
    }
