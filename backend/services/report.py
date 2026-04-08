def generate_report(data):
    summary = (
        f"Skin score is {data['score']} with {data['acne_count']} visible acne spots, "
        f"{data['severity'].lower()} severity, and {data['pigmentation_coverage']}% pigmentation coverage."
    )

    key_insights = [
        f"Highest activity appears around the {data['top_zone'].replace('_', ' ')}.",
        f"Confidence score is {data['confidence']}% for this screen-level analysis.",
    ]

    recommendations = [
        "Keep tracking symptoms consistently to improve future trend accuracy.",
    ]

    return {
        "summary": summary,
        "key_insights": key_insights,
        "recommendations": recommendations,
    }
