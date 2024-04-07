"""First attempt at a game world

"""
from math import exp

from trader.good import Good


# For shaping seasonal productivity functions

goods = {
    'wheat': Good('wheat', 0.1, 10),
    'corn': Good('corn', 0.25, 6),
    'apples': Good('apples', 0.5, 4),
    'milk': Good('milk', 1.5, 2),
    'steak': Good('steak', 5, 1)
}

def main():
