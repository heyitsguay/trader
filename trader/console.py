"""CLI console based on the `rich` library.

"""
import math

import numpy as np

from typing import Dict, List, Tuple

from rich.console import Console as RichConsole
from rich.table import Table
from rich.text import Text

from .enums import Action, WorldState
from .farmer import Farmer
from .location import Location
from .player import Player
from .util import clean_string, rgb_interpolate

# Normalizing constant for coloring Farmer and Location names based on the time
# since their last visit
C_VISIT = 10
# Number of available nearest locations to move to
N_LOCATIONS = 10


class Console(RichConsole):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        return

    def action_table(self, state: WorldState) -> Tuple[Table, Dict[str, Action]]:
        """Create a table of available actions at the current `state`, along
        with a dict mapping action names and numbers to an `Action`.

        Example:
            Available actions for `WorldState.AT_LOCATION` are `Action.MOVE` and
            `Action.TRADE`. `World.action_table` produces a `table` with rows
            ('1.', 'Move'), ('2.', 'Trade') and an `action_dict = {
                'move': Action.MOVE,
                '1': Action.MOVE,
                'trade': Action.TRADE,
                '2': Action.TRADE
            }`.

        Args:
            state (WorldState): Current world state.

        Returns:
            table (Table): Table of available actions, enumerated from 1.
            action_dict (Dict[str, Action]): Dict mapping Action names and
                numbers to the Action they represent.

        """
        table = Table(show_header=False)
        action_dict = {}

        if state == WorldState.AT_LOCATION:
            actions = [Action.MOVE, Action.TRADE, Action.INVENTORY, Action.MAP]
        elif state == WorldState.AT_FARMER:
            actions = [Action.BACK, Action.BUY, Action.SELL, Action.INVENTORY]
        else:
            raise NotImplementedError(f'No action table for {state.name}')

        for i, action in enumerate(actions):
            table.add_row(f'{i + 1}.', action.name.capitalize())
            action_dict[action.name.lower()] = action
            action_dict[str(i + 1)] = action

        return table, action_dict

    def buy_table(self, player: Player) -> Table:
        """Compute a table of available goods at the Farmer that the Player
        is currently trading with.

        Args:
            player (Player): The Player. Pull current Farmer and money details.

        Returns:
            table (Table): Table of available goods to buy.

        """
        if player.trading_farmer is None:
            raise ValueError('No trading farmer is available')

        table = Table(show_header=False)
        table.add_column('Quantity', justify='left')
        table.add_column('Name')
        table.add_column('Price', justify='left')

        farmer = player.trading_farmer
        inventory = farmer.inventory
        available_goods = [good for good in inventory if inventory[good] > 0]
        available_goods = sorted(available_goods, key=lambda g: g.base_price)
        available_quantities = [inventory[g] for g in available_goods]
        prices = [farmer.buy_price(g) for g in available_goods]

        for good, quant, price in zip(available_goods, available_quantities, prices):
            style = self.style_budget(price, player.money)
            if style == '':
                style = self.style_price(price, player.seen_buy_prices[good], True)

            table.add_row(
                f'{quant}', good.name, f'${price:.2f}', style=style)
        if len(available_goods) == 0:
            table.add_row('  ', 'Nothing to buy!', '  ')

        # Append pricing information to Player's price tracking
        player.update_price_tracking(farmer, available_goods)

        return table

    def farmer_table(self, player: Player, day_index: int) -> Tuple[Table, Dict[str, Farmer]]:
        """Compute a table of Farmers the Player can trade with at their
        current location.

        Args:
            player (Player): The Player. Pull current location and its Farmers
                from them.
            day_index (int): Index of the current day.

        Returns:
            table (Table): Table of available Farmers to trade with.
            farmer_dict (Dict[str, Farmer]): Dict mapping Farmer names and
                numbers to the Farmer they represent.

        """
        table = Table(show_header=False)
        farmer_dict = {}
        farmers = player.location.farmers

        for i, farmer in enumerate(farmers):
            time_since_last_visit = day_index - farmer.last_visit
            style = self.style_visit(time_since_last_visit)
            table.add_row(f'{i + 1}.', farmer.name, style=style)
            farmer_dict[clean_string(farmer.name)] = farmer
            farmer_dict[str(i + 1)] = farmer

        return table, farmer_dict

    def inventory_table(self, player: Player) -> Table:
        """Create a table of the Player's current inventory.

        Args:
            player (Player): The player.

        Returns:
            table (Table): Table of the Player's current inventory.

        """
        table = Table(show_header=False)
        table.add_column('Quantity', justify='left')
        table.add_column('Name')

        inventory = player.inventory
        goods = sorted(
            [good for good in inventory], key=lambda g: g.base_price)
        quantities = [inventory[good] for good in goods]
        for quantity, good in zip(quantities, goods):
            table.add_row(str(quantity), good.name)
        if len(quantities) == 0:
            table.add_row('  ', 'No inventory')

        return table

    def location_table(self, player: Player, day_index: int) -> \
            Tuple[Table, Dict[str, Location], Dict[str, Location]]:
        """Compute a table of Locations the Player can move to from `origin`,
        along with the travel cost for each.

        Args:
            player (Player): The Player. Pull current location and other
                needed information from them.
            day_index (int): Index of the current day.

        Returns:
            table (Table): Table of available locations to move to.
            can_travel_dict (Dict[str, Location]): Dict mapping location names
                to Locations that the Player can afford to travel to.
            cannot_travel_dict (Dict[str, Location]): Dict mapping location
                names to Locations that the Player cannot afford to travel to.

        """
        origin = player.location
        other_locations = [loc for loc in origin.locations if loc != origin]
        topk_locations = sorted(
            other_locations,
            key=lambda loc: origin.location_distances[loc])[:N_LOCATIONS]
        topk_costs = [player.location_travel_cost(loc) for loc in topk_locations]

        # Split locations and costs into two for two columns of each
        col1_idx = math.ceil(len(topk_locations) / 2)
        col1_locations = topk_locations[:col1_idx]
        col1_costs = topk_costs[:col1_idx]
        col2_locations = topk_locations[col1_idx:]
        col2_costs = topk_costs[col1_idx:]

        table = Table(show_header=False)
        table.add_column('Number', justify='left')
        table.add_column('Location')
        table.add_column('Cost', justify='left')
        table.add_column('Number', justify='left')
        table.add_column('Location')
        table.add_column('Cost', justify='left')

        can_travel_dict = {}
        cannot_travel_dict = {}

        for i in range(col1_idx):
            # Populate first 2 cols, leave second two empty
            loc1 = col1_locations[i]
            c1 = col1_costs[i]
            if c1 > player.money:
                cannot_travel_dict[str(i+1)] = loc1
                cannot_travel_dict[clean_string(loc1.name)] = loc1
            else:
                can_travel_dict[str(i+1)] = loc1
                can_travel_dict[clean_string(loc1.name)] = loc1

            style1 = self.style_budget(c1, player.money)
            if style1 == '':
                style1 = self.style_visit(day_index - loc1.last_visit)

            row = [
                Text(f'{i+1}.', style=style1),
                Text(loc1.name_with_info(), style=style1),
                Text(f'${c1:.2f}', style=style1),
                '', '', '']

            if i < len(col2_locations):
                # If there's info for the second 2 cols, populate them
                loc2 = col2_locations[i]
                c2 = col2_costs[i]
                if c2 > player.money:
                    cannot_travel_dict[str(col1_idx+i+1)] = loc2
                    cannot_travel_dict[clean_string(loc2.name)] = loc2
                else:
                    can_travel_dict[str(col1_idx+i+1)] = loc2
                    can_travel_dict[clean_string(loc2.name)] = loc2

                style2 = self.style_budget(c2, player.money)
                if style2 == '':
                    style2 = self.style_visit(day_index - loc2.last_visit)

                row[3] = Text(f'{col1_idx + i + 1}.', style=style2)
                row[4] = Text(loc2.name_with_info(), style=style2)
                row[5] = Text(f'${c2:.2f}', style=style2)

            table.add_row(*row)

        return table, can_travel_dict, cannot_travel_dict

    def sell_table(self, player: Player) -> Table:
        if player.trading_farmer is None:
            raise ValueError('No trading farmer is available')

        table = Table(show_header=False)
        table.add_column('Quantity', justify='left')
        table.add_column('Name')
        table.add_column('Price', justify='left')

        farmer = player.trading_farmer
        inventory = player.inventory
        available_goods = [good for good in inventory if inventory[good] > 0]
        available_goods = sorted(available_goods, key=lambda g: g.base_price)
        available_quantities = [inventory[g] for g in available_goods]
        prices = [farmer.sell_price(g) for g in available_goods]

        for good, quant, price in zip(available_goods, available_quantities, prices):
            style = self.style_budget(price, farmer.money)
            if style == '':
                style = self.style_price(price, player.seen_sell_prices[good], False)
            table.add_row(
                f'{quant}', good.name, f'${price:.2f}', style=style)

        if len(available_goods) == 0:
            table.add_row('  ', 'Nothing to sell!', '  ')

        player.update_price_tracking(farmer, available_goods)

        return table

    @staticmethod
    def style_budget(cost: float, budget: float) -> str:
        """Compute a `Text` style that is grayed out if `cost` > `budget`, or
        else default.

        Args:
            cost (float): The cost associated with the text element.
            budget (float): The budget associated with the text element.

        Returns:
            style (str): A `Text` style name.

        """
        return 'gray53' if cost > budget else ''

    @staticmethod
    def style_price(price: float, seen_prices: List[float], buying: bool) -> str:
        """Compute a text style color code based on the z-score of `price`
        within the distribution of all prices the Player has seen so far.

        Args:
            price (float): A price of a Good (buy or sell).
            seen_prices (List[float]): A list of all relevant prices seen by the
                Player so far.
            buying (bool): If True, low prices are good (aka green). Otherwise,
                high prices are good.

        Returns:
            color_code (str): Color code of an RGB color. Goes from red to white
                as price increases from a z-score of -3- to 0, then
                white to green as z-score increases from 0 to 3+

        """
        if len(seen_prices) == 0:
            z = 0
        elif np.std(seen_prices) == 0:
            z = np.sign(price - seen_prices[0])
        else:
            z = np.clip(
                (price - np.mean(seen_prices)) / np.std(seen_prices), -3, 3)
        if buying:
            z = -z
        if z <= 0:
            z = max(z, -2)
            fraction = -z / 2
            return rgb_interpolate(
                (255, 255, 255), (255, 64, 64), fraction)
        elif z <= 2:
            fraction = z / 2
            return rgb_interpolate(
                (255, 255, 255), (64, 255, 64), fraction)
        else:
            return 'bold rgb(64,255,64)'

    @staticmethod
    def style_visit(time_since_last_visit: int) -> str:
        """Compute a text style color based on the `time_since_last_visit` of
        the player to the entity referenced by the text.

        Args:
            time_since_last_visit (int): The time since the Player last visited
                the entity referenced by the text.

        Returns:
            color_code (str): Color code of an RGB color. Goes from green when
                `time_since_last_visit` == 0 to white when
                `time_since_last_visit` >= `C_VISIT`.

        """
        fraction = min(1, time_since_last_visit / C_VISIT)
        return rgb_interpolate(
            (64, 255, 64), (255, 255, 255), fraction)
