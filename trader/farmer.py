"""A farmer the player can trade with.

"""
import numpy as np

from typing import List

from .good import Good
from .location import Location
from .noise_controller import NoiseController


class Farmer:
    def __init__(
            self,
            name: str,
            location: Location,
            noise_controller: NoiseController,
            goods: List[Good]):
        self.name = name
        self.location = location
        self.noise_controller = noise_controller
        self.goods = goods

        self.good_dist = self.noise_controller.generate_farmer_good_dist(goods)
        self.inventory = {good: 0 for good in goods}

        self.init()
        return

    def __str__(self):
        inv_string = ', '.join([f'{k.name}: {v}' for k, v in self.inventory.items()])
        return f'{self.name}:  {inv_string}'

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
            if self.inventory[good] < good.max_amount:
                increment = self.noise_controller.sample_good_increment(farmer_prod_rate)
                self.inventory[good] = min(
                    good.max_amount, self.inventory[good] + increment)
        return

