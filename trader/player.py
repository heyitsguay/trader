"""The player.

"""
import numpy as np

from typing import Any, Dict, List, Tuple

from .farmer import Farmer
from .good import Good
from .location import Location
from .noise_controller import NoiseController


class Player:
    def __init__(
            self,
            name: str,
            location: Location,
            player_params: Dict[str, Any],
            noise_controller: NoiseController,
            goods: List[Good]):
        self.name = name
        self.location = location
        self.params = player_params
        self.noise_controller = noise_controller
        self.goods = goods

        self.inventory = {good: 0 for good in self.goods}
        self.money = 0

        self.init()
        return

    def buy(self, good: Good, quantity: int, farmer: Farmer) -> Tuple[bool, str]:
        """Buy a quantity of Goods from a Farmer.

        Args:
            good (Good): Good to buy.
            quantity (int): Quantity of goods to buy.
            farmer (Farmer): Farmer to buy from.

        Returns:
            success (bool): Whether the buy was successful.
            message (str): Message describing the buy outcome.

        """
        if farmer.inventory[good] < quantity:
            return False, f'{farmer.name} does not have {quantity} of {good.name}.'
        buy_price = round(farmer.prices[good] * farmer.params['spread'] * quantity, 2)
        if buy_price > self.money:
            return False, f'You do not have enough money to buy {quantity} of {good.name} (${buy_price:.2g}).'

        farmer.inventory[good] -= quantity
        farmer.money += buy_price
        self.inventory[good] += quantity
        self.money -= buy_price
        return True, f'Bought {quantity} of {good.name} from {farmer.name} for ${buy_price:.2g}.'

    def init(self) -> None:
        """Initialize the Player.

        """
        self.money = self.init_money()
        return

    def init_money(self) -> float:
        """Initialize Player money.

        Returns:
            (float): Player money.

        """
        return self.params['init_money']

    # TODO: Sell, move

