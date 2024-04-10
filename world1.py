"""First attempt at a game world

"""
import random

from trader.good import Good
from trader.location import Location
from trader.noise_controller import NoiseController

wheat = Good('wheat', 0.1, 2, 32, 2)
corn = Good('corn', 0.25, 1.6, 24, 2.5)
apples = Good('apples', 0.5, 1, 20, 3.5)
milk = Good('milk', 1.5, 1.2, 10, 4)
steak = Good('steak', 5, 0.3, 10, 5)
goods = [wheat, corn, apples, milk, steak]

year_length = 100

# Random noise generator params
seed = 89
prod_params = {
    'spatial_octaves': 4,
    'spatial_res': 128,
    'temporal_octaves': 2,
    'temporal_res': 64,
    'noise_exp': 4}

noise_controller = NoiseController(seed, goods, year_length, prod_params)

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


def main():
    for location in locations:
        print(f'{location.name}:')
        print('  ', ', '.join([f'{good.name}: {location.prod_rate(good, 0):.1f}' for good in goods]))
    return


if __name__ == '__main__':
    main()
