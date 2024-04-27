"""CLI console based on the `rich` library.

"""
import math

from rich.console import Console as RichConsole
from rich.table import Table
from rich.text import Text

from typing import Dict, Tuple

from .enums import Action, WorldState
from .farmer import Farmer
from .location import Location
from .player import Player
from .util import clean_string

# Number of available nearest locations to move to
N_LOCATIONS = 9


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
            actions = [Action.MOVE, Action.TRADE]
        else:
            raise NotImplementedError(f'No action table for {state.name}')

        for i, action in enumerate(actions):
            table.add_row(f'{i + 1}.', action.name.capitalize())
            action_dict[action.name.lower()] = action
            action_dict[str(i + 1)] = action

        return table, action_dict

    def farmer_table(self, player: Player) -> \
            Tuple[Table, Dict[str, Farmer]]:
        """Compute a table of Farmers the Player can trade with at their
        current location.

        Args:
            player (Player): The Player. Pull current location and its Farmers
                from them.

        Returns:
            table (Table): Table of available Farmers to trade with.
            farmer_dict (Dict[str, Farmer]): Dict mapping Farmer names and
                numbers to the Farmer they represent.

        """
        table = Table(show_header=False)
        farmer_dict = {}
        farmers = player.location.farmers

        for i, farmer in enumerate(farmers):
            table.add_row(f'{i + 1}.', farmer.name)
            farmer_dict[clean_string(farmer.name)] = farmer
            farmer_dict[str(i + 1)] = farmer

        return table, farmer_dict

    def location_table(self, player: Player) -> \
            Tuple[Table, Dict[str, Location], Dict[str, Location]]:
        """Compute a table of Locations the Player can move to from `origin`,
        along with the travel cost for each.

        Args:
            player (Player): The Player. Pull current location and other
                needed information from them.

        Returns:
            table (Table): Table of available locations to move to.
            can_travel_dict (Dict[str, Location]): Dict mapping location names
                to Locations that the Player can afford to travel to.
            cannot_travel_dict (Dict[str, Location]): Dict mapping location
                names to Locations that the Player cannot afford to travel to.

        """
        origin = player.location
        topk_locations = sorted(
            origin.locations,
            key=lambda loc: origin.location_distances[loc])[:N_LOCATIONS]
        topk_costs = [player.location_travel_cost(loc) for loc in topk_locations]

        # Split locations and costs into two for two columns of each
        col1_idx = math.ceil(len(topk_locations) / 2)
        col1_locations = topk_locations[:col1_idx]
        col1_costs = topk_costs[:col1_idx]
        col2_locations = topk_locations[col1_idx:]
        col2_costs = topk_costs[col1_idx:]

        table = Table(show_header=False)
        table.add_column('Location')
        table.add_column('Cost')
        table.add_column('Location')
        table.add_column('Cost')

        can_travel_dict = {}
        cannot_travel_dict = {}

        for i in range(col1_idx):
            # Populate first 2 cols, leave second two empty
            loc1 = col1_locations[i]
            c1 = col1_costs[i]
            if c1 > player.money:
                cannot_travel_dict[loc1.name.lower()] = loc1
            else:
                can_travel_dict[loc1.name.lower()] = loc1

            style1 = self.style_budget(c1, player.money)

            row = [
                Text(loc1.name, style=style1),
                Text(f'${c1:.2f}', style=style1),
                '', '']

            if i < len(col2_locations):
                # If there's info for the second 2 cols, populate them
                loc2 = col2_locations[i]
                c2 = col2_costs[i]
                if c2 > player.money:
                    cannot_travel_dict[loc2.name.lower()] = loc2
                else:
                    can_travel_dict[loc2.name.lower()] = loc2

                style2 = self.style_budget(c2, player.money)

                row[3] = Text(loc2.name, style=style2)
                row[4] = Text(f'${c2:.2f}', style=style2)

            table.add_row(*row)

        return table, can_travel_dict, cannot_travel_dict

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
