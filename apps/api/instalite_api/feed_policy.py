from typing import Any

FEED_SESSION_LIMIT = 25


def apply_feed_policy(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in item.items() if key != "policy"}
        for item in items
        if not item["policy"]["isSuggested"]
        and not item["policy"]["isSponsored"]
        and not item["policy"]["isReel"]
        and item["policy"].get("isFollowing") is not False
    ][:FEED_SESSION_LIMIT]
