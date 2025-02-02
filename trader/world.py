"""Game world.

"""
import os
import tkinter as tk

import matplotlib.pyplot as plt
import names
import numpy as np

from typing import List, Optional, Tuple

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from rich.live import Live
from rich.prompt import Prompt
from rich.spinner import Spinner

from .console import Console, C_VISIT
from .enums import Action, WorldState
from .farmer import Farmer
from .good import Good
from .location import Location
from .model import Model
from .noise_controller import NoiseController
from .player import Player
from .util import clean_string, parse_transaction, rgb_interpolate

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
LOCATIONS_FILE = os.path.join(DATA_DIR, 'locations.txt')


class World:
    wheat = Good('wheat', 0.1, 0.8, 32, 2, 10, 100)
    corn = Good('corn', 0.25, 0.8, 24, 2.5, 8, 100)
    apples = Good('apple', 0.5, 0.5, 30, 3.5, 6, 80)
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
        'lower_money_multiplier': 25,
        'upper_money_multiplier': 50,
        'money_growth_factor': 1.7,
        'p_money_growth': 0.36,
        'money_decay_factor': 0.9,
        'p_money_decay': 0.4,
    }

    player_params = {
        'init_money': 10,
        'travel_cost_multiplier': 30,
    }

    con_params = {
        'buy_threshold': 0.2,
        'sell_threshold': 2,
    }

    def __init__(self, seed: int, request_url: str, debug: bool = False):
        """Constructor.

        Args:
            seed (int): RNG seed.
            request_url (str): URL for LLM requests.
            debug (bool): If True, produce debug information.

        """
        self.seed = seed
        self.request_url = request_url
        self.debug = debug

        # Current day
        self.today = -1
        # Current day index (i.e. increases linearly, doesn't wrap for years)
        self.day_index = -1

        self.noise_controller = NoiseController(
            self.seed, self.goods, self.year_length, self.prod_params, self.location_params, self.farmer_params)
        self.rng = np.random.default_rng(self.seed * 2)

        self.locations = self.init_locations(LOCATIONS_FILE)
        self.farmers = self.init_farmers()
        # Keep track of all buy and sell prices

        # Calculate base abundance (average amount of good per farmer)
        for good in self.goods:
            good.set_base_abundance(self.calculate_base_abundance(good, self.farmers))

        self.player = Player(self.locations[0], self.player_params, self.noise_controller, self.goods)

        self.state = WorldState.INIT

        self.console = Console()

        self.model = Model(
            self.request_url, self.player, self.goods, self.con_params)

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
        Location, view inventory, switch to SELL mode, or actually buy
        something. If actually buying something, returns the desired Good and
        buy quantity, else returns just the BACK, SELL, or INVENTORY action and
        `None` for the Good and quantity.

        Returns:
            action (Action): `Action.BUY` if actually buying, `Action.BACK` if
                returning to the current trading Farmer's Location,
                `Action.SELL` if switching to SELL mode with the current Farmer,
                or `Action.INVENTORY` if viewing inventory.
            good (Optional[Good]): The Good to buy, if buying, else None.
            quantity (int): The quantity to buy, if buying, else None.

        """
        valid_input = False
        quantity = None
        matched_goods = []
        while not valid_input:
            raw_input = input(f'({self.player.print_money()}) > ')
            if clean_string(raw_input) == 'back':
                return Action.BACK, None, None
            elif clean_string(raw_input) == 'negotiate':
                return Action.BUY_NEGOTIATION, None, None
            elif clean_string(raw_input) == 'sell':
                return Action.SELL, None, None
            elif clean_string(raw_input) == 'inventory':
                return Action.INVENTORY, None, None
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
            raw_input = input(f'({self.player.print_money()}) > ')
            if clean_string(raw_input) == 'back':
                return Action.BACK, None, None
            elif clean_string(raw_input) == 'negotiate':
                return Action.SELL_NEGOTIATION, None, None
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

    def get_yesno_input(self, color: Optional[str] = None) -> bool:
        """Get an input from the user that must be 'yes' (or 'y') or 'no'
        (or 'n').

        Args:
            color (Optional[str]): Input prompt color as a Rich console style.

        Returns:
            answer (bool): `True` if yes, `False` if no.

        """
        while True:
            style_start = f'[{color}]' if color else ''
            style_end = '[/]' if color else ''
            raw_input = Prompt.ask(f'{style_start}({self.player.print_money()}) > {style_end}')
            clean_input = clean_string(raw_input)
            if clean_input in ['yes', 'y']:
                return True
            elif clean_input in ['no', 'n']:
                return False
            else:
                self.console.print('Invalid input! Should be "yes" or "no".')

    def init_farmers(self) -> List[Farmer]:
        farmers = []
        for location in self.locations:
            n_farmers_at_location = np.minimum(4, self.rng.geometric(0.28))
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
                '\n\nWhat would you like to do?'
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
                self.console.print(f'Invalid action! ({action})')
        return next_action

    def show_map(self):
        # Create the main window
        root = tk.Tk()
        root.title("World Map")

        # Get screen size to create a window that takes up 95% of the screen
        w_pix = root.winfo_screenwidth()
        w_mm = root.winfo_screenmmwidth()
        w_inch = w_mm / 25.4
        dpi = int(w_pix / w_inch)
        h_mm = root.winfo_screenmmheight()
        h_inch = h_mm / 25.4
        s_window = 0.95 * min(w_inch, h_inch)

        fig = Figure(figsize=(s_window, s_window), dpi=dpi)
        ax = fig.add_subplot(111)
        plt.autoscale(tight=True)

        # Gather points from Location locations
        xs = []
        ys = []
        labels = []
        player_present = []
        colors = []
        sizes = []
        font_weights = []
        for location in self.locations:
            xs.append(1000*location.location[0])
            ys.append(1000*location.location[1])
            labels.append(location.name_with_info())
            is_present = location == self.player.location
            player_present.append(is_present)
            if is_present:
                colors.append('#4444ff')
                sizes.append(12*12)
                font_weights.append('bold')
            else:
                time_since_last_visit = self.day_index - location.last_visit
                fraction = min(1, time_since_last_visit / C_VISIT)
                colors.append(rgb_interpolate((64, 255, 64), (16, 16, 16), fraction, hex_code=True))
                sizes.append(18*18)
                font_weights.append('regular')

        ax.scatter(xs, ys, c=colors, s=None, marker='o')
        ax.set_xlim(0, 1000)
        ax.set_ylim(0, 1000)

        for x, y, label, weight in zip(xs, ys, labels, font_weights):
            ax.annotate(label, (x, y), textcoords='offset points', xytext=(0, 10), ha='center', weight=weight)

        ax.tick_params(top=False, bottom=False, left=False, right=False,
                       labelleft=False, labelbottom=False)
        ax.set_title("Press 'Q' to quit")

        # Embed the figure in the tkinter window
        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        def on_key_press(event):
            if event.char == 'q' or event.char == 'Q':
                root.quit()
                root.destroy()

        # Bind the key press event
        root.bind("<KeyPress>", on_key_press)

        # Start the GUI event loop
        root.mainloop()

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

        elif self.state == WorldState.BUY_NEGOTIATION:
            advance_next = self.step_buying_negotiation(advance_day)

        elif self.state == WorldState.SELL_NEGOTIATION:
            advance_next = self.step_selling_negotiation(advance_day)

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
            self.update()
        self.console.print(
            f'\n\nDay {self.today + 1}/{self.year_length} in {self.player.location}'
            f' trading with {self.player.trading_farmer.name}.'
        )

        next_action = self.select_action()
        while next_action == Action.INVENTORY:
            self.view_inventory()
            next_action = self.select_action()

        if next_action == Action.BACK:
            # Go back to the Location where the current trading Farmer is
            self.state = WorldState.AT_LOCATION
            self.player.set_new_farmer(None)
        elif next_action == Action.BUY:
            self.state = WorldState.BUYING
        elif next_action == Action.SELL:
            self.state = WorldState.SELLING
        elif next_action == Action.BUY_NEGOTIATION:
            self.state = WorldState.BUY_NEGOTIATION
        elif next_action == Action.SELL_NEGOTIATION:
            self.state = WorldState.SELL_NEGOTIATION

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
            self.update()
        self.console.print(
            f'\n\nDay {self.today + 1}/{self.year_length} in {self.player.location}.'
        )

        next_action = self.select_action()
        while next_action == Action.INVENTORY:
            self.view_inventory()
            next_action = self.select_action()

        if next_action == Action.MOVE:
            valid_location_selected = False

            self.console.print(
                f"\nWhere do you want to move to?"
                f"\nType a location name, or\n'back' for the previous menu, or\n'map' for the map:"
            )
            table, can_travel_dict, cannot_travel_dict = \
                self.console.location_table(self.player, self.day_index)
            self.console.print(table)
            while not valid_location_selected:
                location_name = clean_string(
                    input(f'({player_money}) > ')
                )
                if location_name == 'back':
                    return False
                elif location_name == 'map':
                    self.show_map()
                elif location_name in cannot_travel_dict:
                    loc = cannot_travel_dict[location_name]
                    self.console.print(f'Insufficient funds to travel to {loc}.')
                elif location_name in can_travel_dict:
                    loc = can_travel_dict[location_name]
                    valid_location_selected = True
                    success, message = self.player.move_location(loc, self.day_index)
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
            table, farmer_dict = self.console.farmer_table(self.player, self.day_index)
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
                    success, message = self.player.move_farmer(farmer, self.day_index)
                    assert success, message
                    self.console.print(message)
                    self.state = WorldState.AT_FARMER
                    return False

        elif next_action == Action.MAP:
            self.show_map()
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
        current_farmer = self.player.trading_farmer
        self.console.print(
            f'\n\nDay {self.today + 1}/{self.year_length} in {self.player.location}'
            f' buying from {current_farmer.name}.'
        )
        self.console.print('Type the name and quantity of items to buy.')
        self.console.print(f"Or, type 'negotiate' to haggle a better buy price.")
        self.console.print(f"Or, type 'back' to return to {self.player.location}.")
        self.console.print(f"Or, type 'sell' to sell to {current_farmer.name}.")
        self.console.print(f"Or, type 'inventory' to view your inventory.")

        table = self.console.buy_table(self.player)
        self.console.print(table)

        valid_purchase = False
        while not valid_purchase:
            action, buy_good, buy_quantity = self.get_buy_input()
            if action == Action.BACK:
                self.state = WorldState.AT_LOCATION
                self.player.set_new_farmer(None)
                return False
            elif action == Action.BUY_NEGOTIATION:
                self.state = WorldState.BUY_NEGOTIATION
                return False
            elif action == Action.SELL:
                self.state = WorldState.SELLING
                return False
            elif action == Action.INVENTORY:
                self.view_inventory()
                return False

            # Otherwise, assume we are in fact trying to buy something
            valid_purchase, message = self.player.buy(
                buy_good, buy_quantity, current_farmer)
            self.console.print(message)
        return False

    def step_buying_negotiation(self, advance_day: bool) -> bool:
        """Logic for a world step in the BUY_NEGOTIATION world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next(bool): If True, next call to `step` will advance the
                day, else not.

        """
        current_farmer = self.player.trading_farmer
        self.console.print(
            f'[#cccccc]\n\nDay {self.today + 1}/{self.year_length} in {self.player.location}. '
            f'Negotiate a purchase with {current_farmer.name}.[/]')
        self.console.print(f"[#cccccc]Or, type 'back' to return to {self.player.location}.[/]")
        self.console.print(f"[#cccccc]Or, type 'buy' to buy from {current_farmer.name} without negotiating.[/]")
        self.console.print(f"[#cccccc]Or, type 'sell' to sell to {current_farmer.name}.[/]")
        self.console.print(f"[#cccccc]Or, type 'inventory' to view your inventory.[/]")
        table = self.console.buy_table(self.player)
        self.console.print(table)

        # Reset the model's random seed in a predictable way
        self.model.reset(current_farmer)

        # Introduction from the farmer
        with Live(Spinner('simpleDots', text='[#cccccc]Thinking[/]'), refresh_per_second=3) as live:
            message = self.model.introduce(
                current_farmer, WorldState.BUY_NEGOTIATION)
            live.update(f'» {message}\n')

        while True:
            raw_input = ''
            while raw_input == '':
                raw_input = input(f'({self.player.print_money()}) > ')
            with Live(Spinner('simpleDots', text='[#cccccc]Thinking[/]'), refresh_per_second=3) as live:
                action, purchase_info, message = self.model.negotiate_buy(
                    current_farmer, raw_input)
                if action == Action.BACK:
                    self.state = WorldState.AT_LOCATION
                    self.player.set_new_farmer(None)
                    return False
                elif action == Action.BUY:
                    self.state = WorldState.BUYING
                    return False
                elif action == Action.SELL:
                    self.state = WorldState.SELLING
                    return False
                elif action == Action.INVENTORY:
                    live.update('')
                else:
                    live.update(f'\n» {message.lstrip("TRADER: ")}\n')
            if action == Action.INVENTORY:
                self.view_inventory()

            valid_purchase = purchase_info['valid']
            if valid_purchase:
                good = purchase_info['good']
                quantity = purchase_info['quantity']
                price = purchase_info['price']
                total_price = round(quantity * price, 2)
                self.console.print(f'[#ff9900]Make a buy for {quantity} of {good} for ${price:.2f} each (total: ${total_price:.2f})?[/] \[yes/no]')
                make_deal = self.get_yesno_input(color='#ff9900')

                if make_deal:
                    valid_purchase, purchase_message = self.player.buy(
                        good, quantity, current_farmer, price)

                    if valid_purchase:
                        # Check to see if the current Farmer has been conned
                        base_price = current_farmer.buy_price(good)
                        if price / base_price < self.con_params['buy_threshold']:
                            self.model.summarize_buy_con(base_price, price)

                    self.model.chat_history.append(
                        {'role': 'user', 'content': 'USER: ' + purchase_message.replace('You do', 'User does')})

                    self.console.print(f'[#cccccc]{purchase_message}[/]')

    def step_selling_negotiation(self, advance_day: bool) -> bool:
        """Logic for a world step in the SELL_NEGOTIATION world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next(bool): If True, next call to `step` will advance the
                day, else not.

        """
        current_farmer = self.player.trading_farmer
        self.console.print(
            f'[#cccccc]\n\nDay {self.today + 1}/{self.year_length} in {self.player.location}. '
            f'Negotiate a sale with {current_farmer.name}.[/]')
        self.console.print(f"[#cccccc]Or, type 'back' to return to {self.player.location}.[/]")
        self.console.print(f"[#cccccc]Or, type 'buy' to buy from {current_farmer.name}.[/]")
        self.console.print(f"[#cccccc]Or, type 'sell' to sell to {current_farmer.name} without negotiating.[/]")
        self.console.print(f"[#cccccc]Or, type 'inventory' to view your inventory.[/]")
        table = self.console.sell_table(self.player)
        self.console.print(f"[#cccccc]{current_farmer.name}'s money: ${current_farmer.money:.2f}[/]")
        self.console.print(table)

        # Reset the model's random seed in a predictable way
        self.model.reset(current_farmer)

        # Introduction from the farmer
        with Live(Spinner('simpleDots', text='[#cccccc]Thinking[/]'), refresh_per_second=3) as live:
            message = self.model.introduce(
                current_farmer, WorldState.SELL_NEGOTIATION)
            live.update(f'» {message}\n')

        while True:
            raw_input = ''
            while raw_input == '':
                raw_input = input(f'({self.player.print_money()}) > ')
            with Live(Spinner('simpleDots', text='[#cccccc]Thinking[/]'), refresh_per_second=3) as live:
                action, sale_info, message = self.model.negotiate_sell(raw_input)
                if action == Action.BACK:
                    self.state = WorldState.AT_LOCATION
                    self.player.set_new_farmer(None)
                    return False
                elif action == Action.BUY:
                    self.state = WorldState.BUYING
                    return False
                elif action == Action.SELL:
                    self.state = WorldState.SELLING
                    return False
                elif action == Action.INVENTORY:
                    self.view_inventory()
                    return False

                live.update(f'\n» {message.lstrip("TRADER: ")}\n')

            valid_sale = sale_info['valid']
            if valid_sale:
                good = sale_info['good']
                quantity = sale_info['quantity']
                price = sale_info['price']
                total_price = round(quantity * price, 2)
                self.console.print(f'[#ff9900]Make a sale for {quantity} of {good} for ${price:.2f} each (total: ${total_price:.2f})?[/] \[yes/no]')
                make_deal = self.get_yesno_input(color='#ff9900')

                if make_deal:
                    valid_sale, sale_message = self.player.sell(
                        good, quantity, current_farmer, price)

                    if valid_sale:
                        # Check to see if the current Farmer has been conned
                        base_price = current_farmer.sell_price(good)
                        if price / base_price > self.con_params['sell_threshold']:
                            self.model.summarize_sell_con(base_price, price)

                    self.model.chat_history.append(
                        {'role': 'user', 'content': sale_message.replace('You do', 'User does')})

                    self.console.print(f'[#cccccc]{sale_message}[/]')

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
            f'{player_money} in your pocket and a dream to '
            f'find your fortune.'
        )
        self.state = WorldState.AT_LOCATION
        return True

    def step_selling(self, advance_day: bool) -> bool:
        """Logic for a world step in the SELLING world state.

        Args:
            advance_day (bool): If True, advance the game day when applicable.

        Returns:
            advance_next (bool): If True, next call to `step` will advance the
                day, else not.

        """
        current_farmer = self.player.trading_farmer
        self.console.print(
            f'\n\nDay {self.today + 1}/{self.year_length} in {self.player.location} '
            f'selling to {current_farmer.name}.'
        )
        self.console.print('Type the name and quantity of items to sell.')
        self.console.print(f"Or, type 'back' to return to {self.player.location}.")
        self.console.print(f"Or, type 'negotiate' to haggle a better sale price.")
        self.console.print(f"Or, type 'buy' to buy from {current_farmer.name}.")

        table = self.console.sell_table(self.player)
        self.console.print(f"{current_farmer.name}'s money: ${current_farmer.money:.2f}")
        self.console.print(table)

        valid_sale = False
        while not valid_sale:
            action, sell_good, sell_quantity = self.get_sell_input()
            if action == Action.BACK:
                self.state = WorldState.AT_LOCATION
                self.player.set_new_farmer(None)
                return False
            elif action == Action.SELL_NEGOTIATION:
                self.state = WorldState.SELL_NEGOTIATION
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
        self.today = self.next_day()
        self.day_index += 1
        for location in self.locations:
            location.update(self.today)
        return

    def view_inventory(self) -> None:
        """Print Player inventory and money.

        Returns: None

        """
        self.console.print('Your inventory:')
        self.console.print(f'Money: {self.player.print_money()}')
        self.console.print(self.console.inventory_table(self.player))
        self.console.input('[#cccccc]Press any key to continue[/]')
        return
