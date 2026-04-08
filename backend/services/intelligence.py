def _latest_log(logs: list[dict]):
    return logs[0] if logs else {}


def _average_numeric(logs: list[dict], key: str):
    values = [log[key] for log in logs if isinstance(log.get(key), (int, float))]
    if not values:
        return None
    return sum(values) / len(values)


def _top_zone(zones: dict):
    if not zones:
        return ""
    return max(zones, key=lambda zone: zones[zone].get("count", 0))


def generate_recommendations(data):
    recommendations = []
    severity = data.get("severity", "")
    skin_type = data.get("skin_type", "")
    stress = data.get("stress", "")
    average_sleep = data.get("average_sleep")
    average_water = data.get("average_water")

    if severity in {"Moderate", "High"}:
        recommendations.append("Use a gentle salicylic acid treatment in the evening")
    if skin_type.lower() == "oily":
        recommendations.append("Choose a lightweight non-comedogenic moisturizer for oily skin")
    elif skin_type.lower() == "dry":
        recommendations.append("Support your barrier with a richer moisturizer after cleansing")
    elif skin_type.lower() == "combination":
        recommendations.append("Balance oily areas with a light gel moisturizer and gentle cleanser")

    if stress.lower() in {"high", "moderate", "medium"}:
        recommendations.append("Build in a short stress reset routine because flare-ups often follow high-stress days")
    if average_sleep is not None and average_sleep < 7:
        recommendations.append("Aim for at least 7 hours of sleep to support skin recovery")
    if average_water is not None and average_water < 2:
        recommendations.append("Increase water intake closer to 2 liters for steadier hydration")
    if not recommendations:
        recommendations.append("Maintain your current routine and keep tracking for stronger trend signals")

    return recommendations


def generate_insights(current, previous, user, logs):
    current_count = current.get("acne_count", 0)
    previous_count = (previous or {}).get("acne_count", current_count)
    change = current_count - previous_count

    if previous is None:
        trend_status = "Baseline"
    elif change < 0:
        trend_status = "Improving"
    elif change > 0:
        trend_status = "Worsening"
    else:
        trend_status = "Stable"

    latest_log = _latest_log(logs)
    average_sleep = _average_numeric(logs, "sleep")
    average_water = _average_numeric(logs, "water_intake")
    top_zone = _top_zone(current.get("zones", {})).replace("_", " ")

    correlations = []
    stress_value = str(latest_log.get("stress", "")).lower()
    if stress_value in {"high", "moderate", "medium"} and current_count >= 8:
        correlations.append("Recent higher stress entries line up with elevated acne activity.")
    elif stress_value:
        correlations.append(f"Recent stress level was logged as {stress_value}, which can influence breakouts over time.")

    if average_sleep is not None and average_sleep < 7:
        correlations.append("Shorter sleep patterns may be contributing to slower skin recovery.")
    elif average_sleep is not None:
        correlations.append("Sleep duration is trending in a supportive range for recovery.")

    if average_water is not None and average_water < 2:
        correlations.append("Hydration logs suggest water intake could be improved for steadier skin support.")

    if trend_status == "Improving":
        prediction = "Likely improvement if current routine and recent health habits stay consistent."
    elif trend_status == "Worsening":
        prediction = "Breakouts may worsen unless stress, sleep, or irritation triggers are reduced soon."
    elif trend_status == "Stable":
        prediction = "Skin condition is likely to stay near the current level without routine changes."
    else:
        prediction = "Need more historical analyses to make a stronger trend prediction."

    insights = [
        f"Primary breakout concentration appears on the {top_zone or 'face'}.",
        f"Skin type context: {user.get('skin_type', 'not set')}.",
        f"Trend status is {trend_status.lower()} compared with the previous analysis.",
    ]
    insights.extend(correlations)

    recommendation_input = {
        "severity": current.get("severity", ""),
        "skin_type": user.get("skin_type", ""),
        "stress": latest_log.get("stress", ""),
        "average_sleep": average_sleep,
        "average_water": average_water,
    }

    return {
        "trend_status": trend_status,
        "change": change,
        "correlations": correlations,
        "prediction": prediction,
        "insights": insights,
        "recommendations": generate_recommendations(recommendation_input),
    }
