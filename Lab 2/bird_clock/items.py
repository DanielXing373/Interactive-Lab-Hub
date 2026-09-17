"""Power-up hooks. First version does not spawn items or apply numbers."""

from typing import Optional

from .config import ItemConfig


class Item:
    kind = "base"

    def apply(self, game) -> None:
        raise NotImplementedError


class Coin(Item):
    kind = "coin"

    def apply(self, game) -> None:
        game.add_bonus_score(game.config.items.coin_score)


class Invincibility(Item):
    kind = "invincible"

    def apply(self, game) -> None:
        game.grant_invincibility(game.config.items.invincible_seconds)


def maybe_roll_item(cfg: ItemConfig) -> Optional[Item]:
    if not cfg.spawn_enabled or cfg.top_item_chance <= 0:
        return None
    import random

    if random.random() > cfg.top_item_chance:
        return None
    # When spawning is enabled later, pick coin vs invincible here.
    return Coin()
