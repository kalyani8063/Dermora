import re


DIET_KEYWORDS = ("balanced", "junk", "healthy", "protein", "salad", "sugary", "clean")
STRESS_KEYWORDS = ("low", "medium", "moderate", "high")
ACTIVITY_KEYWORDS = ("walk", "workout", "gym", "yoga", "run", "exercise", "cycling")
SYMPTOM_KEYWORDS = ("acne", "redness", "dryness", "irritation", "itching", "oiliness", "sensitivity")
SUGAR_FREE_POSITIVE_PATTERNS = (
    r"\bsugar[ -]?free\b",
    r"\bno added sugar\b",
    r"\bno sugar\b",
    r"\bwithout sugar\b",
    r"\bzero sugar\b",
    r"\bcut out sugar\b",
    r"\bskipped (?:dessert|sweets)\b",
)
SUGAR_FREE_NEGATIVE_PATTERNS = (
    r"\bhad sugar\b",
    r"\bsugary\b",
    r"\bdessert\b",
    r"\bsweets?\b",
    r"\bcandy\b",
    r"\bcake\b",
    r"\bice cream\b",
    r"\bsoda\b",
    r"\bchocolate\b",
)


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
    symptoms = [keyword for keyword in SYMPTOM_KEYWORDS if keyword in lowered]
    sugar_free = None

    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in SUGAR_FREE_NEGATIVE_PATTERNS):
        sugar_free = False
    elif any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in SUGAR_FREE_POSITIVE_PATTERNS):
        sugar_free = True

    if not activity:
        duration = _extract_first(r"(\d+\s*(?:mins|minutes|hrs|hours))", lowered)
        if duration and any(keyword in lowered for keyword in ACTIVITY_KEYWORDS):
            activity = duration

    return {
        "water_intake": float(water) if water else None,
        "sugar_free": sugar_free,
        "activity": activity,
        "diet": diet,
        "sleep": float(sleep) if sleep else None,
        "stress": stress,
        "menstrual_cycle": f"day {menstrual_cycle}" if menstrual_cycle else "",
        "symptoms": symptoms,
        "notes": text.strip(),
        "source": "text_parser",
        "tags": ["text-log", "nlp"] if text.strip() else ["text-log"],
    }
