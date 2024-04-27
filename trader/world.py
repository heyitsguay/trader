"""Game world.

"""
import os

import matplotlib.pyplot as plt
import names
import numpy as np

from typing import List, Optional, Tuple

from .console import Console
from .enums import Action, WorldState
from .farmer import Farmer
from .good import Good
from .location import Location
from .noise_controller import NoiseController
from .player import Player
from .util import clean_string, parse_transaction

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
LOCATIONS_FILE = os.path.join(DATA_DIR, 'locations.txt')


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

        self.console = Console()

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

    def get_buy_input(self) -> Tuple[Action, Optional[Good], Optional[int]]:
        """Parse a user input during a buy transaction.

        Determine if the user wants to go back to the current trading Farmer's
        Location, switch to SELL mode, or actually buy something. If actually
        buying something, returns the desired Good and buy quantity, else
        returns just the BACK or SELL action and `None` for the Good and
        quantity.

        Returns:
            action (Action): `Action.BUY` if actually buying, `Action.BACK` if
                returning to the current trading Farmer's Location, or
                `Action.SELL` if switching to SELL mode with the current Farmer.
            good (Optional[Good]): The Good to buy, if buying, else None.
            quantity (int): The quantity to buy, if buying, else None.

        """
        valid_input = False
        quantity = None
        matched_goods = []
        while not valid_input:
            raw_input = input(f'{self.player.print_money()} > ')
            if clean_string(raw_input) == 'back':
                return Action.BACK, None, None
            elif clean_string(raw_input) == 'sell':
                return Action.SELL, None, None
            else:
                # Actually buying
                quantity, good_name = parse_transaction(raw_input)
                if quantity is not None:
                    matched_goods = [good for good in self.goods if good.name == good_name]
                    if len(matched_goods) == 0:
                        self.console.print('Invalid input!')
                    elif len(matched_goods) > 1:
                        raise ValueError(f'More than one matched good found in {matched_goods}.')
                    else:
                        valid_input = True
                else:
                    self.console.print('Invalid input!')
            return Action.BUY, matched_goods[0], quantity

    def get_sell_input(self) -> Tuple[Action, Optional[Good], Optional[int]]:
        """Parse a user input during a sell transaction.

        Determine if the user wants to go back to the current trading Farmer's
        Location, switch to BUY mode, or actually sell something. If actually
        selling something, returns the desired Good and sell quantity, else
        returns just the BACK or BUY action and `None` for the Good and
        quantity.

        Returns:
            action (Action): `Action.SELL` if actually selling, `Action.BACK` if
                returning to the current trading Farmer's Location, or
                `Action.BUY` if switching to BUY mode with the current Farmer.
            good (Optional[Good]): The Good to sell, if selling, else None.
            quantity (int): The quantity to sell, if selling, else None.

        """
        valid_input = False
        quantity = None
        matched_goods = []
        while not valid_input:
            raw_input = input(f'{self.player.print_money()} > ')
            if clean_string(raw_input) == 'back':
                return Action.BACK, None, None
            elif clean_string(raw_input) == 'buy':
                return Action.BUY, None, None
            else:
                # Actually buying
                quantity, good_name = parse_transaction(raw_input)
                if quantity is not None:
                    matched_goods = [good for good in self.goods if good.name == good_name]
                    if len(matched_goods) == 0:
                        self.console.print('Invalid input!')
                    elif len(matched_goods) > 1:
                        raise ValueError(f'More than one matched good found in {matched_goods}.')
                    else:
                        valid_input = True
                else:
                    self.console.print('Invalid input!')
        return Action.SELL, matched_goods[0], quantity

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

    def select_action(self) -> Action:
        """Display dialog and handle input for selecting an Action.

        Returns:
            next_action (Action): Next Action.

        """
        valid_action_selected = False
        next_action = None
        while not valid_action_selected:
            self.console.print(
                'What would you like to do?'
                '\nType an action number or name:'
            )
            table, action_dict = self.console.action_table(self.state)
            self.console.print(table)
            action = clean_string(
                input(f'({self.player.print_money()}) > ')
            )
            if action in action_dict:
                next_action = action_dict[action]
                valid_action_selected = True
            else:
                self.console.print('Invalid action!')
        return next_action

    def step(self, advance_day: bool) -> bool:
        """Take one step in the game.

        Args:
            advance_day (bool): If True, game states where the day can advance
                will have the day advance.

        Returns:
            advance_next (bool): If True, next call to `step` will advance the
                day, else not.

        """

        if self.state == WorldState.INIT:
            advance_next = self.step_init(advance_day)

        elif self.state == WorldState.AT_LOCATION:
            advance_next = self.step_at_location(advance_day)

        elif self.state == WorldState.AT_FARMER:
            advance_next = self.step_at_farmer(advance_day)

        elif self.state == WorldState.BUYING:
            advance_next = self.step_buying(advance_day)

        elif self.state == WorldState.SELLING:
            advance_next = self.step_selling(advance_day)

        else:
            raise NotImplementedError

        return advance_next

    def step_at_farmer(self, advance_day: bool) -> bool:
        """Logic for a world step in the AT_FARMER world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next (bool): If True, next call to `step` will advance the
                day, else not.

        """
        if advance_day:
            self.today = self.next_day()
        self.update()
        self.console.print(
            f'\nDay {self.today + 1}/{self.year_length} in {self.player.location}'
            f'trading with {self.player.trading_farmer}.'
        )

        next_action = self.select_action()

        if next_action == Action.BACK:
            # Go back to the Location where the current trading Farmer is
            self.state = WorldState.AT_LOCATION
            self.player.set_new_farmer(None)
        elif next_action == Action.BUY:
            self.state = WorldState.BUYING
        elif next_action == Action.SELL:
            self.state = WorldState.SELLING

        return False

    def step_at_location(self, advance_day: bool) -> bool:
        """Logic for a world step in the AT_LOCATION world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next (bool): If True, next call to `step` will advance the
                day, else not.

        """
        player_money = self.player.print_money()
        if advance_day:
            self.today = self.next_day()
        self.update()
        self.console.print(
            f'\nDay {self.today + 1}/{self.year_length} in {self.player.location}.'
        )

        next_action = self.select_action()

        if next_action == Action.MOVE:
            valid_location_selected = False

            self.console.print(
                f"\nWhere do you want to move to?"
                f"\nType a location name or 'back' for the previous menu:"
            )
            table, can_travel_dict, cannot_travel_dict = \
                self.console.location_table(self.player)
            self.console.print(table)
            while not valid_location_selected:
                location_name = clean_string(
                    input(f'({player_money}) > ')
                )
                if location_name == 'back':
                    return False
                elif location_name in cannot_travel_dict:
                    loc = cannot_travel_dict[location_name]
                    self.console.print(f'Insufficient funds to travel to {loc}.')
                elif location_name in can_travel_dict:
                    loc = can_travel_dict[location_name]
                    valid_location_selected = True
                    success, message = self.player.move_location(loc)
                    assert success, message
                    self.console.print(message)
                    return True
                else:
                    self.console.print('Invalid location!')

        elif next_action == Action.TRADE:
            valid_farmer_selected = False

            self.console.print(
                f"\nWhom do you want to trade with?"
                f"\nType a farmer's number or name, or 'back' for the previous menu:"
            )
            table, farmer_dict = self.console.farmer_table(self.player)
            self.console.print(table)
            while not valid_farmer_selected:
                farmer_name = clean_string(
                    input(f'({player_money}) > ')
                )
                if farmer_name == 'back':
                    return False
                elif farmer_name in farmer_dict:
                    farmer = farmer_dict[farmer_name]
                    valid_farmer_selected = True
                    # Don't advance the day if the Player is returning to the
                    # Farmer they just visited
                    advance_day = farmer != self.player.last_farmer
                    success, message = self.player.move_farmer(farmer)
                    assert success, message
                    self.console.print(message)
                    self.state = WorldState.AT_FARMER
                    return advance_day
        # It should not be possible to get here
        else:
            raise ValueError(f'Invalid Action state {next_action.name} reached.')

    def step_buying(self, advance_day: bool) -> bool:
        """Logic for a world step in the BUYING world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next (bool): If True, next call to `step` will advance the
                day, else not.

        """
        self.update()

        current_farmer = self.player.trading_farmer
        self.console.print(
            f'\nDay {self.today + 1}/{self.year_length} buying from '
            f'{current_farmer.name}.'
        )
        self.console.print('Type the name and quantity of items to buy.')
        self.console.print(f"Or, type 'back' to return to {self.player.location}.")
        self.console.print(f"Or, type 'sell' to sell to {current_farmer.name}.")

        table = self.console.buy_table(self.player)
        self.console.print(table)

        valid_purchase = False
        while not valid_purchase:
            action, buy_good, buy_quantity = self.get_buy_input()
            if action == Action.BACK:
                self.state = WorldState.AT_LOCATION
                self.player.set_new_farmer(None)
                return False
            elif action == Action.SELL:
                self.state = WorldState.SELLING
                return False

            # Otherwise, assume we are in fact trying to buy something
            valid_purchase, message = self.player.buy(
                buy_good, buy_quantity, current_farmer)
            self.console.print(message)
        return False

    def step_init(self, advance_day: bool) -> bool:
        """Logic for a world step in the INIT world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next (bool): If True, next call to `step` will advance the
                day, else not.

        """
        player_money = self.player.print_money()
        self.console.print('Welcome to TRADER.')
        self.console.print(
            f'You arrive at {self.player.location} with '
            f'{player_money} in your pocket and a dream to'
            f'find your fortune.'
        )
        self.state = WorldState.AT_LOCATION
        return False

    def step_selling(self, advance_day: bool) -> bool:
        """Logic for a world step in the SELLING world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next (bool): If True, next call to `step` will advance the
                day, else not.

        """
        self.update()

        current_farmer = self.player.trading_farmer
        self.console.print(
            f'\nDay {self.today + 1}/{self.year_length} selling to '
            f'{current_farmer.name}.'
        )
        self.console.print('Type the name and quantity of items to sell.')
        self.console.print(f"Or, type 'back' to return to {self.player.location}.")
        self.console.print(f"Or, type 'buy' to buy from {current_farmer.name}.")

        table = self.console.sell_table(self.player)
        self.console.print(table)

        valid_sale = False
        while not valid_sale:
            action, sell_good, sell_quantity = self.get_sell_input()
            if action == Action.BACK:
                self.state = WorldState.AT_LOCATION
                self.player.set_new_farmer(None)
                return False
            elif action == Action.BUY:
                self.state = WorldState.BUYING
                return False

            # Otherwise, assume we are in fact trying to buy something
            valid_sale, message = self.player.sell(
                sell_good, sell_quantity, current_farmer)
            self.console.print(message)
        return False

    def update(self):
        for location in self.locations:
            location.update(self.today)
        return
