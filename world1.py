"""First attempt at a game world

"""
import names
import numpy as np

from trader.farmer import Farmer
from trader.good import Good
from trader.location import Location
from trader.noise_controller import NoiseController

wheat = Good('wheat', 0.1, 2, 32, 2, 10, 100)
corn = Good('corn', 0.25, 1.6, 24, 2.5, 8, 100)
apples = Good('apples', 0.5, 1, 30, 3.5, 6, 80)
milk = Good('milk', 1.5, 1.2, 10, 4, 7, 50)
steak = Good('steak', 5, 0.6, 10, 5, 4, 40)
goods = [wheat, corn, apples, milk, steak]

year_length = 100

# Random noise generator params
seed = 89
prod_params = {
    'spatial_octaves': 4,
    'spatial_res': 128,
    'temporal_octaves': 2,
    'temporal_res': 64,
}

farmer_parms = {
    'mean_n_goods': 2,
    'min_n_goods': 1,
}

noise_controller = NoiseController(
    seed, goods, year_length, prod_params, farmer_parms)

rng = np.random.default_rng(seed)

locations = [
    Location('Mansfield', noise_controller),
    Location('Lebanon', noise_controller),
    Location('Frederick', noise_controller),
    Location('Calistoga', noise_controller),
    Location('Plainview', noise_controller),
    Location('New Windsor', noise_controller),
    Location('Fort Wayne', noise_controller),
    Location('Pacific Grove', noise_controller),
    Location('Pendleton', noise_controller),
    Location('Ogdensburg', noise_controller),
    Location('Elisabethton', noise_controller),
    Location('Burlingame', noise_controller),
]

farmers = []
for location in locations:
    n_farmers_at_location = np.minimum(4, rng.geometric(0.55))
    for n in range(n_farmers_at_location):
        farmers.append(Farmer(
            names.get_full_name(), location, noise_controller, goods))


def main():
    for farmer in farmers:
        print(farmer)
    return


if __name__ == '__main__':
    main()
