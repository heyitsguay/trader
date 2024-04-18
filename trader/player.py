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

        self.trading_farmer = None

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
        if not isinstance(quantity, int) or quantity < 1:
            return False, f'Quantity ({quantity}) must be an integer greater than 0.'
        if farmer.inventory[good] < quantity:
            return False, f'{farmer.name} does not have {quantity} of {good}.'
        buy_price = round(farmer.prices[good] * (1 + farmer.params['spread']) * quantity, 2)
        if buy_price > self.money:
            return False, f'You do not have enough money to buy {quantity} of {good} (${buy_price:.2f}).'

        farmer.inventory[good] -= quantity
        farmer.money += buy_price
        self.inventory[good] += quantity
        self.money -= buy_price
        return True, f'Bought {quantity} of {good} from {farmer.name} for ${buy_price:.2f}.'

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

    def move_farmer(self, farmer: Farmer) -> Tuple[bool, str]:
        """Within a Location, move to trade with a Farmer.

        Args:
            farmer (Farmer): Farmer to move to.

        Returns:
            success (bool): Whether the move was successful.
            message (str): Message describing the move outcome.

        """
        if farmer.location != self.location:
            return False, f'Farmer {farmer.name} not present at {self.location}.'
        self.trading_farmer = farmer
        return True, f'Now trading with {farmer.name}.'

    def move_location(self, location: Location) -> Tuple[bool, str]:
        """(Attempt to) move to another location.

        Moving incurs a cost. You can only move if you can pay the travel cost.

        Args:
            location (Location): Location to move to.

        Returns:
            success (bool): Whether the move was successful.
            message (str): Message describing the move outcome.

        """
        if location == self.location:
            return False, f'Already at {location}.'
        travel_cost = round(self.params['travel_cost_multiplier'] *
            location.distance_to(self.location), 2)
        if travel_cost > self.money:
            return False, f'${travel_cost:.2f} required to travel to {location}.'
        self.money -= travel_cost
        self.location = location
        self.trading_farmer = None
        return True, f'Traveled to {location} for ${travel_cost:.2f}.'

    def sell(self, good: Good, quantity: int, farmer: Farmer) -> Tuple[bool, str]:
        """Sell a quantity of a Good to a Farmer.

        Args:
            good (Good): Good to sell.
            quantity (int): Quantity of goods to sell.
            farmer (Farmer): Farmer to sell to.

        Returns:
            success (bool): True if the sell was successful.
            message (str): Message describing the sell outcome.

        """
        if not isinstance(quantity, int) or quantity < 1:
            return False, f'Quantity ({quantity}) must be an integer greater than 0.'
        if self.inventory[good] < quantity:
            return False, f'You do not have {quantity} of {good}.'
        sell_price = round(farmer.prices[good] * (1 - farmer.params['spread']) * quantity, 2)
        if sell_price > farmer.money:
            return False, f'{farmer.name} does not have enough money to buy {quantity} of {good}. (${sell_price:.2f})'
        self.inventory[good] -= quantity
        self.money += sell_price
        farmer.inventory[good] += quantity
        farmer.money -= sell_price
        return True, f'Sold {quantity} of {good} to {farmer.name} for ${sell_price:.2f}.'

