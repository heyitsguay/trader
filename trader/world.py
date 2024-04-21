"""Game world.

"""
import os

import matplotlib.pyplot as plt
import names
import numpy as np

from enum import Enum
from typing import List

from .farmer import Farmer
from .good import Good
from .location import Location
from .noise_controller import NoiseController
from .player import Player

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
LOCATIONS_FILE = os.path.join(DATA_DIR, 'locations.txt')


class WorldState(Enum):
    INIT = 1
    AT_LOCATION = 2
    AT_FARMER = 3
    MOVE_TO_LOCATION = 4
    MOVE_TO_FARMER = 5
    BUYING = 6
    SELLING = 7
    GAME_OVER = 8


class World:
    wheat = Good('wheat', 0.1, 0.8, 32, 2, 10, 100)
    corn = Good('corn', 0.25, 0.8, 24, 2.5, 8, 100)
    apples = Good('apples', 0.5, 0.5, 30, 3.5, 6, 80)
    milk = Good('milk', 1.5, 0.6, 10, 4, 7, 50)
    steak = Good('steak', 5, 0.3, 8, 4, 4, 40)
    goods = [wheat, corn, apples, milk, steak]

    year_length = 100

    prod_params = {
        'spatial_octaves': 4,
        'spatial_res': 128,
        'temporal_octaves': 2,
        'temporal_res': 64,
    }

    location_params = {
        'n_locations': 20,
        'n_clusters': 5,
        'amp_min': 0.025,
        'amp_max': 0.075,
        'std_min': 0.08,
        'std_max': 0.25,
        'supply_sensitivity': 1,
    }

    farmer_params = {
        'mean_n_goods': 2,
        'min_n_goods': 1,
        'supply_sensitivity': 1,
        'spread': 0.1,
        'lower_money_multiplier': 10,
        'upper_money_multiplier': 30,
        'money_growth_factor': 1.5,
        'p_money_growth': 0.36,
        'money_decay_factor': 0.9,
        'p_money_decay': 0.4,
    }

    player_params = {
        'init_money': 10,
        'travel_cost_multiplier': 2,
    }

    def __init__(self, seed: int, debug: bool = False):
        """Constructor.

        Args:
            seed (int): RNG seed.
            debug (bool): If True, produce debug information.

        """
        self.seed = seed
        self.debug = debug

        # Current day
        self.today = -1

        self.noise_controller = NoiseController(
            self.seed, self.goods, self.year_length, self.prod_params, self.location_params, self.farmer_params)
        self.rng = np.random.default_rng(self.seed * 2)

        self.locations = self.init_locations(LOCATIONS_FILE)
        self.farmers = self.init_farmers()

        # Calculate base abundance (average amount of good per farmer)
        for good in self.goods:
            good.set_base_abundance(self.calculate_base_abundance(good, self.farmers))

        self.player = Player(self.locations[0], self.player_params, self.noise_controller, self.goods)

        self.state = WorldState.INIT

        # Initial debug information
        if self.debug:
            print(f'# Farmers: {len(self.farmers)}')
            for good in self.goods:
                invs = [
                    [farmer.inventory[good]] for farmer in self.farmers]
                for i in range(self.year_length):
                    for j in range(len(self.farmers)):
                        self.farmers[j].update_inventory(i)
                        invs[j].append(self.farmers[j].inventory[good])

                f, ax = plt.subplots(1, 1)
                f.set_size_inches(10, 10)
                for inv in invs:
                    ax.plot(inv)
                ax.set_title(good)
                plt.show()
        return

    @staticmethod
    def calculate_base_abundance(good: Good, farmers: List[Farmer]) -> float:
        """Calculate baseline abundance for a good.

            Baseline abundance is average quantity of the good per farmer.

            Args:
                good (Good): Good to calculate baseline abundance for.
                farmers (List[Farmer]): List of all Farmers.

            Returns:
                baseline_abundance (float): Baseline abundance.

            """
        n_farmers = len(farmers)
        total_inventory = sum([f.inventory[good] for f in farmers])
        baseline_abundance = total_inventory / n_farmers
        return baseline_abundance

    def init_farmers(self) -> List[Farmer]:
        farmers = []
        for location in self.locations:
            n_farmers_at_location = np.minimum(4, self.rng.geometric(0.33))
            for n in range(n_farmers_at_location):
                farmers.append(Farmer(
                    names.get_full_name(), location, self.farmer_params, self.noise_controller, self.goods))
        return farmers

    def init_locations(self, locations_file: str) -> List[Location]:
        """Initialize World Locations.

        Args:
            locations_file (str): File with location names.

        Returns:
            locations (List[Location]): List of Locations.

        """
        with open(locations_file, 'r') as fd:
            location_names = fd.read().split('\n')
            location_names = [n.strip() for n in location_names]
        n_locations = self.location_params['n_locations']
        location_names = list(self.rng.choice(location_names, size=n_locations))
        locations = [
            Location(name, self.location_params['supply_sensitivity'], self.noise_controller, self.goods)
            for name in location_names]
        # Set inter-location distances
        location_distance_matrix = np.zeros((n_locations, n_locations))
        for i in range(n_locations - 1):
            for j in range(i + 1, n_locations):
                location_distance_matrix[i, j] = locations[i].distance_to(locations[j])
                location_distance_matrix[j, i] = location_distance_matrix[i, j]
        for i, location in enumerate(locations):
            location.set_locations_info(locations, location_distance_matrix[i])

        return locations

    def next_day(self) -> int:
        """Calculate the next day of the year, resetting at the end of the year.

        Returns:
            tomorrow (int): Tomorrow.

        """
        tomorrow = (self.today + 1) % self.year_length
        return tomorrow

    def step(self):
        if self.state == WorldState.INIT:
            print('Welcome to TRADER.')
            print(f'You arrive at {self.player.location} with '
                  f'{self.player.print_money()} in your pocket and a dream to'
                  f'find your fortune.')
            self.state = WorldState.AT_LOCATION

        if self.state == WorldState.AT_LOCATION:
            self.today = self.next_day()
            n_farmers = len(self.player.location.farmers)
            print(f'Day {self.today+1}/{self.year_length} at {self.player.location}. You can trade with:')
            for i, farmer in enumerate(self.player.location.farmers):
                print(f' {i+1}. {farmer.name}')
