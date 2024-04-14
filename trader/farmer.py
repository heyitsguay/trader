"""A farmer the player can trade with.

"""
import numpy as np

from typing import Dict, List

from .good import Good
from .location import Location
from .noise_controller import NoiseController


class Farmer:
    def __init__(
            self,
            name: str,
            location: Location,
            supply_sensitivity: float,
            spread_factor: float,
            noise_controller: NoiseController,
            goods: List[Good]):
        self.name = name
        self.location = location
        self.supply_sensitivity = supply_sensitivity
        self.spread_factor = spread_factor
        self.noise_controller = noise_controller
        self.goods = goods

        self.location.add_farmer(self)

        self.good_dist = self.noise_controller.generate_farmer_good_dist(goods)
        self.inventory = {good: 0 for good in goods}
        self.prices: Dict[Good, float] = {}

        self.init()
        return

    def __str__(self):
        inv_string = ', '.join([f'{k.name}: {v}' for k, v in self.inventory.items()])
        return f'{self.name}:  {inv_string}'

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
                prices[good] = round(base_prices[good] * np.clip((
                    base_abundances[good] / (0.1 + self.inventory[good]))**self.supply_sensitivity, 0.5, 2), 2)
        return prices

    def init(self) -> None:
        """Initialize the farmer.

        """
        self.init_inventory()
        return

    def init_inventory(self) -> None:
        """Initialize inventory as an accumulation of the first ten days'
        worth of production.

        Returns: None

        """
        for day in range(10):
            self.update_inventory(day)
        return

    def update(self, today: int) -> None:
        """Update farmer variables.

        Args:
            today (int): Day of the year.

        Returns: None

        """
        self.update_inventory(today)
        self.prices = self.compute_prices()
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

