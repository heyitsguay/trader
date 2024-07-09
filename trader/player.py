"""The player.

"""
from typing import Any, Dict, List, Optional, Tuple

from .farmer import Farmer
from .good import Good
from .location import Location
from .noise_controller import NoiseController


class Player:
    def __init__(
            self,
            location: Location,
            player_params: Dict[str, Any],
            noise_controller: NoiseController,
            goods: List[Good]):
        self.location = None
        self.move_location(location, 0, False)
        self.params = player_params
        self.noise_controller = noise_controller
        self.goods = goods

        self.trading_farmer = None
        self.last_farmer = None

        self.inventory = {good: 0 for good in self.goods}
        self.money = 0

        # Track buy and sell prices seen so far, to cue when there is a good
        # or bad deal in trade menus
        self.seen_buy_prices = {good: [] for good in self.goods}
        self.seen_sell_prices = {good: [] for good in self.goods}

        self.init()
        return

    def buy(
            self,
            good: Good,
            quantity: int,
            farmer: Farmer,
            price: Optional[float] = None) -> Tuple[bool, str]:
        """Buy a quantity of Goods from a Farmer.

        Args:
            good (Good): Good to buy.
            quantity (int): Quantity of goods to buy.
            farmer (Farmer): Farmer to buy from.
            price (Optional[float]): If `None`, use `good`'s default buy price
                for `farmer`, else use `buy_price` as the per-unit buy price.

        Returns:
            success (bool): Whether the buy was successful.
            message (str): Message describing the buy outcome.

        """
        if not isinstance(quantity, int) or quantity < 1:
            return False, f'Quantity ({quantity}) must be an integer greater than 0.'
        if farmer.inventory[good] < quantity:
            return False, f'{farmer.name} does not have {quantity} of {good}.'
        if price is not None and price < 0:
            return False, f'Price ({price}) must be positive.'
        elif price is None:
            price = farmer.buy_price(good)
        buy_price = round(price * quantity, 2)
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

    def location_travel_cost(self, location: Location) -> float:
        """Compute the cost of moving to `location`.

        Args:
            location (Location): Location to compute cost to.

        Returns:
            cost (float): Cost of moving to `location`.

        """
        cost = round(self.params['travel_cost_multiplier'] *
            location.distance_to(self.location)**2, 2)
        return cost

    def move_farmer(self, farmer: Farmer, day_index: int) -> Tuple[bool, str]:
        """Within a Location, move to trade with a Farmer.

        Args:
            farmer (Farmer): Farmer to move to.
            day_index (int): Index of the current day.

        Returns:
            success (bool): Whether the move was successful.
            message (str): Message describing the move outcome.

        """
        if farmer.location != self.location:
            return False, f'Farmer {farmer.name} not present at {self.location}.'
        self.set_new_farmer(farmer)
        farmer.last_visit = day_index
        return True, f'Now trading with {farmer.name}.'

    def move_location(self, location: Location, day_index: int, pay: bool = True) -> Tuple[bool, str]:
        """(Attempt to) move to another location.

        Moving incurs a cost. You can only move if you can pay the travel cost.

        Args:
            location (Location): Location to move to.
            day_index (int): Index of the current day.
            pay (bool): If True, pay a travel cost.

        Returns:
            success (bool): Whether the move was successful.
            message (str): Message describing the move outcome.

        """
        if location == self.location:
            return False, f'Already at {location}.'
        if pay:
            travel_cost = self.location_travel_cost(location)
            if travel_cost > self.money:
                return False, f'${travel_cost:.2f} required to travel to {location}.'
            self.money -= travel_cost
        else:
            travel_cost = 0
        self.location = location
        for farmer in self.location.farmers:
            farmer.seen_goods = False
        self.trading_farmer = None
        self.last_farmer = None
        location.last_visit = day_index
        return True, f'Traveled to {location} for ${travel_cost:.2f}.'

    def print_money(self) -> str:
        """Print the Player's current amount of money, properly formatted.

        Returns:
            money_str (str): Formatted string of the Player's current amount of
                money.

        """
        return f'${self.money:.2f}'

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
        sell_price = round(farmer.sell_price(good) * quantity, 2)
        if sell_price > farmer.money:
            return False, f'{farmer.name} does not have enough money to buy {quantity} of {good}. (${sell_price:.2f})'
        self.inventory[good] -= quantity
        self.money += sell_price
        farmer.inventory[good] += quantity
        farmer.money -= sell_price
        return True, f'Sold {quantity} of {good} to {farmer.name} for ${sell_price:.2f}.'

    def set_new_farmer(self, farmer: Farmer) -> None:
        """Set a new current trading Farmer.

        Args:
            farmer (Farmer): New current trading Farmer.

        Returns: None

        """
        self.last_farmer = self.trading_farmer
        self.trading_farmer = farmer
        return

    def update_price_tracking(self, farmer: Farmer, available_goods: List[Good]) -> None:
        """Update price tracking info from the given Farmer and list of Goods.

        Args:
            farmer (Farmer): Farmer whose pricing info to add to tracking.
            available_goods (List[Good]): Goods to update pricing info for.:

        Returns: None

        """
        if not farmer.seen_goods:
            for g in available_goods:
                self.seen_buy_prices[g].append(farmer.buy_price(g))
                self.seen_sell_prices[g].append(farmer.sell_price(g))
            farmer.seen_goods = True
        return
