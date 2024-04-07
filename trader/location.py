"""A location the player can travel to to trade with Farmers.

"""
from typing import Callable, Dict

from good import Good


class Location:
    def __init__(
            self,
            name: str,
            location_x: float,
            location_y: float,
            year_length: int,
            prod_fns: Dict[Good, Callable[[float], float]]):
        self.name = name
        self.location_x = location_x
        self.location_y = location_y
        self.year_length = year_length
        self.prod_fns = prod_fns
        return

    def prod_rate(self, good: Good, day: int) -> float:
        """Calculate today's production rate for a good.

        Args:
            good (Good): Good to calculate production rate for.
            day (int): Day of the year.

        Returns:
            (float): The production rate for the good.

        """
        return self.prod_fns[good](day / self.year_length)
