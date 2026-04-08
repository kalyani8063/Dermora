def send_to_n8n(payload):
    structured_payload = {
        "analysis": payload.get("analysis", {}),
        "user": payload.get("user", {}),
        "logs": payload.get("logs", []),
        "previous": payload.get("previous", {}),
    }

    return {
        "queued": False,
        "destination": "n8n_webhook_placeholder",
        "payload_preview": structured_payload,
    }
