"""A location the player can travel to to trade with Farmers.

"""
from .good import Good
from .noise_controller import NoiseController


class Location:
    def __init__(
            self,
            name: str,
            noise_controller: NoiseController):
        self.name = name
        self.noise_controller = noise_controller
        self.location = self.noise_controller.sample_location()
        return

    def prod_rate(self, good: Good, day: int) -> float:
        """Calculate today's production rate for a good.

        Args:
            good (Good): Good to calculate production rate for.
            day (int): Day of the year.

        Returns:
            (float): The production rate for the good.

        """
        return good.base_prod_rate + self.noise_controller.sample_good_prod(
            good, day, self.location) * good.prod_rate_multiplier
