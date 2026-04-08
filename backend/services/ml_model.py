from pathlib import Path
import random


def analyze_image(image):
    """
    Placeholder ML boundary.

    Replace this function with a real detector later, such as a YOLO-based
    model, without changing the analyzer, schemas, routes, or frontend.
    """

    image_path = Path(image)
    seed = image_path.stat().st_size if image_path.exists() else 1
    rng = random.Random(seed)

    acne_count = 6 + (seed % 7)
    boxes = []
    for _ in range(acne_count):
        x1 = rng.randint(20, 260)
        y1 = rng.randint(20, 320)
        width = rng.randint(24, 72)
        height = rng.randint(24, 72)
        boxes.append([x1, y1, x1 + width, y1 + height])

    return {
        "boxes": boxes,
        "acne_count": acne_count,
    }
