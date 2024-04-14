"""First attempt at a game world

"""
import matplotlib.pyplot as plt
import names
import numpy as np

from typing import List

from trader.farmer import Farmer
from trader.good import Good
from trader.location import Location
from trader.noise_controller import NoiseController

debug = True

wheat = Good('wheat', 0.1, 0.8, 32, 2, 10, 100)
corn = Good('corn', 0.25, 0.8, 24, 2.5, 8, 100)
apples = Good('apples', 0.5, 0.5, 30, 3.5, 6, 80)
milk = Good('milk', 1.5, 0.6, 10, 4, 7, 50)
steak = Good('steak', 5, 0.3, 8, 4, 4, 40)
goods = [wheat, corn, apples, milk, steak]

year_length = 100

# Random noise generator params
seed = 134
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
}

farmer_parms = {
    'mean_n_goods': 2,
    'min_n_goods': 1,
}

pricing_params = {
    'location_supply_sensitivity': 1,
    'trader_supply_sensitivity': 1,
    'trader_spread_factor': 0.1,
}


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


def main():
    noise_controller = NoiseController(
        seed, goods, year_length, prod_params, location_params, farmer_parms)

    rng = np.random.default_rng(seed)

    # Load location names
    with open('data/locations.txt', 'r') as fd:
        location_names = fd.read().split('\n')
        location_names = [n.strip() for n in location_names]
    n_locations = location_params['n_locations']
    location_names = list(rng.choice(location_names, size=n_locations))
    # Create locations
    locations = [
        Location(name, pricing_params['location_supply_sensitivity'], noise_controller)
        for name in location_names]
    # Create location distance matrix
    location_distance_matrix = np.zeros((n_locations, n_locations))
    for i in range(n_locations - 1):
        for j in range(i + 1, n_locations):
            location_distance_matrix[i, j] = locations[i].distance_to(locations[j])
            location_distance_matrix[j, i] = location_distance_matrix[i, j]
    for i, location in enumerate(locations):
        location.set_locations_info(locations, location_distance_matrix[i])

    farmers = []
    for location in locations:
        n_farmers_at_location = np.minimum(4, rng.geometric(0.33))
        for n in range(n_farmers_at_location):
            farmers.append(Farmer(
                names.get_full_name(), location, noise_controller, goods))

    # Calculate base abundances (average amount per good per Farmer)
    for good in goods:
        good.set_base_abundance(calculate_base_abundance(good, farmers))

    if debug:
        print(f'# Farmers: {len(farmers)}')
        for good in goods:
            invs = [
                [farmer.inventory[good]] for farmer in farmers]
            for i in range(year_length):
                for j in range(len(farmers)):
                    farmers[j].update_inventory(i)
                    invs[j].append(farmers[j].inventory[good])

            f, ax = plt.subplots(1, 1)
            f.set_size_inches(10, 10)
            for inv in invs:
                ax.plot(inv)
            ax.set_title(good.name)
            plt.show()
    return


if __name__ == '__main__':
    main()
