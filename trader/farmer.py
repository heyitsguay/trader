"""A farmer the player can trade with.

"""
import numpy as np

from typing import Any, Dict, List

from .good import Good
from .location import Location
from .noise_controller import NoiseController


class Farmer:
    def __init__(
            self,
            name: str,
            location: Location,
            farmer_params: Dict[str, Any],
            noise_controller: NoiseController,
            goods: List[Good]):
        self.name = name
        self.location = location
        self.params = farmer_params
        self.noise_controller = noise_controller
        self.goods = goods

        self.location.add_farmer(self)

        self.good_dist = self.noise_controller.generate_farmer_good_dist(goods)
        self.inventory = {good: 0 for good in goods}
        self.prices: Dict[Good, float] = {}

        # Daily production value
        self.dpv = -1
        self.money = -1
        self.max_money = -1

        self.init()
        return

    def __str__(self):
        inv_string = ', '.join([f'{k.name}: {v}' for k, v in self.inventory.items()])
        return f'{self.name}:  {inv_string}'

    def buy_price(self, good) -> float:
        """Compute the buy price of a given Good based on the computed price
        and spread.

        Args:
            good (Good): Good to compute the buy price of.

        Returns:
            price (float): Buy price of the given Good.

        """
        return round(self.prices[good] * (1 + self.params['spread']), 2)

    def compute_prices(self) -> Dict[Good, float]:
        """Compute prices for all Goods.

        Returns:
            prices (Dict[Good, float]): Per-Good Farmer prices.

        """
        base_prices = self.location.prices
        base_abundances = self.location.supply_scores
        prices = {}
        for good in self.goods:
            if self.good_dist[good] == 0:
                prices[good] = base_prices[good]
            else:
                sensitivity = self.params['supply_sensitivity']
                prices[good] = base_prices[good] * np.clip((
                    base_abundances[good] / max(0.1, self.inventory[good]))**sensitivity, 0.5, 2)
        return prices

    def init(self) -> None:
        """Initialize the farmer.

        """
        self.init_inventory()
        self.money = self.init_money()
        return

    def init_inventory(self) -> None:
        """Initialize inventory as an accumulation of the first ten days'
        worth of production.

        Returns: None

        """
        for day in range(10):
            self.update_inventory(day)
        return

    def init_money(self) -> float:
        """Initialize the money of the Farmer.

        Each Farmer has a `lower_money_multiplier` and `upper_money_multiplier`
        param, which get scaled by the Farmer's daily production value (daily
        production rate of all goods multiplied by the goods' baseline prices).
        When the Farmer's money drops below the lower bound, that money grows
        multiplicatively by `money_growth_factor` with a probability of
        `p_growth` on each turn. Likewise, when the Farmer's money exceeds the
        upper bound, that money decays by `money_decay_factor` with a
        probability of `p_decay` on each turn.

        Returns:
            money (float): Money of the Farmer.

        """
        lower_mult = self.params['lower_money_multiplier']
        upper_mult = self.params['upper_money_multiplier']
        # Daily production value
        self.dpv = sum([
            self.good_dist[good] * good.base_price for good in self.goods])
        assert self.dpv > 0, f'Calculated invalid DPV {self.dpv}'
        mult = lower_mult + (upper_mult - lower_mult) * self.noise_controller.rng.random()
        return mult * self.dpv

    def sell_price(self, good) -> float:
        """Compute the sell price of a given Good based on the computed price
        and spread.

        Args:
            good (Good): Good to compute the sell price of.

        Returns:
            price (float): Sell price of the given Good.

        """
        return round(self.prices[good] * (1 - self.params['spread']), 2)

    def update(self, today: int) -> None:
        """Update farmer variables.

        Args:
            today (int): Day of the year.

        Returns: None

        """
        self.update_inventory(today)
        self.prices = self.compute_prices()
        self.money = self.update_money()
        return

    def update_inventory(self, today: int) -> None:
        """Update farmer inventory.

        Args:
            today (int): Day of the year.

        Returns: None.

        """
        for good in self.goods:
            location_prod_rate = self.location.prod_rate(good, today)
            farmer_prod_rate = location_prod_rate * self.good_dist[good]
            delta = self.noise_controller.sample_good_delta(
                farmer_prod_rate, self.inventory[good], good.max_amount)
            self.inventory[good] = min(good.max_amount, max(0,
                self.inventory[good] + delta))
        return

    def update_money(self) -> float:
        """Update the Farmer's money.

        Returns:
            money (float): The new money of the Farmer.

        """
        new_money = self.money

        lower_mult = self.params['lower_money_multiplier']
        upper_mult = self.params['upper_money_multiplier']

        if lower_mult <= self.money / self.dpv <= upper_mult:
            return new_money

        if self.money < lower_mult * self.dpv:
            p_growth = self.params['p_money_growth']
            growth_factor = self.params['money_growth_factor']
            if self.noise_controller.rng.random() < p_growth:
                # If money is very low, replace with a fraction of DPV. Else
                # grow multiplicatively
                if self.money < 0.25 * self.dpv:
                    new_money = 0.25 * self.dpv
                else:
                    new_money = self.money * growth_factor
            return new_money

        # If we're here, self.money > upper_mult * dpv
        p_decay = self.params['p_money_decay']
        decay_factor = self.params['money_decay_factor']
        if self.noise_controller.rng.random() < p_decay:
            new_money *= decay_factor
        return new_money
