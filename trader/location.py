"""A location the player can travel to to trade with Farmers.

"""
import numpy as np

from typing import Dict, List

from .good import Good
from .noise_controller import NoiseController


class Location:
    def __init__(
            self,
            name: str,
            supply_sensitivity: float,
            noise_controller: NoiseController,
            goods: List[Good]):
        self.name = name
        self.supply_sensitivity = supply_sensitivity
        self.noise_controller = noise_controller
        self.goods = goods

        self.location = self.noise_controller.sample_location()

        self.location_distances: Dict['Location', float] = None
        self.locations: List['Location'] = None
        self.farmers: List['Farmer'] = []

        self.supply_scores: Dict[Good, float] = {}
        self.prices: Dict[Good, float] = {}
        return

    def __eq__(self, other: 'Location'):
        if isinstance(other, Location):
            return self.name == other.name \
                and self.location[0] == other.location[0] \
                and self.location[1] == other.location[1]
        return False

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def add_farmer(self, farmer: 'Farmer'):
        """Add a Farmer to this Location."""
        self.farmers.append(farmer)
        return

    def compute_prices(self) -> Dict[Good, float]:
        """Compute prices for all goods.

        Returns:
            prices (Dict[Good, float]): Per-good Location prices.

        """
        base_prices = {good: good.base_price for good in self.goods}
        base_abundances = {good: good.base_abundance for good in self.goods}
        prices = {
            good: round(base_prices[good] * np.clip((
                    base_abundances[good] / max(0.1, self.supply_scores[good]))**self.supply_sensitivity, 0.25, 4), 2)
            for good in self.goods}
        return prices

    def compute_supply_scores(self) -> Dict[Good, float]:
        """Compute a supply score for Goods, centered at this location.

        Supply score is a weighted average of Good inventory levels, where
        weights per-Farmer are proportional to the distance between the Farmer's
        Location and this Location.

        Returns:
            supply_scores (Dict[Good, float]): Supply scores for each Good.

        """
        farmers = [
            farmer
            for location in self.locations
            for farmer in location.farmers]
        distance_weights = np.array([
            np.exp(-self.location_distances[farmer.location]**2)
            for farmer in farmers])
        distance_weights /= distance_weights.sum()

        supply_scores = {}
        for good in self.goods:
            inventory = np.array([farmer.inventory[good] for farmer in farmers])
            supply_scores[good] = np.sum(distance_weights * inventory)

        return supply_scores

    def distance_to(self, other: 'Location') -> float:
        """Calculate the distance between two locations.

        Args:
            other (Location): Another location.

        Returns:
            (float): Distance between this Location and `other`.

        """
        x0 = self.location[0]
        y0 = self.location[1]
        x1 = other.location[0]
        y1 = other.location[1]
        return np.sqrt((x0 - x1)**2 + (y0 - y1)**2)

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

    def set_locations_info(
            self, locations: List['Location'], location_distances: np.ndarray):
        """Set information about other Locations.

        This information consists of a list of other Locations and the distances
        to them from this Location.

        Args:
            locations (List[Location]): List of all Locations.
            location_distances (np.ndarray): Distances from all Locations to
                this location.

        Returns: None

        """
        self.locations = locations
        self.location_distances = {
            location: distance
            for location, distance in zip(locations, location_distances)}
        return
    def set_location_distances(self, location_distances: np.ndarray):
        """Pass in the distances from all Locations to this Location.

        Args:
            location_distances (np.ndarray): Array of distances from all
                Locations to this Location.

        Returns: None

        """
        self.location_distances = location_distances
        return

    def set_locations(self, locations: List['Location']):
        """Set a reference to all Locations.

        Args:
            locations (List[Location]): List of all Locations.

        Returns: None

        """
        self.locations = locations
        return

    def update(self, today: int):
        """Update this Location's attributes.

        Args:
            today (int): Day of the year.

        Returns: None.

        """
        self.supply_scores = self.compute_supply_scores()
        self.prices = self.compute_prices()

        for farmer in self.farmers:
            farmer.update(today)

        return
