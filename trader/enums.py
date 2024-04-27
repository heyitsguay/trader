"""Enums that are used across multiple files.

"""
from enum import Enum


class Action(Enum):
    BACK = 'Back'
    MOVE = 'Move'
    TRADE = 'Trade'
    BUY = 'Buy'
    SELL = 'Sell'



class WorldState(Enum):
    INIT = 1
    AT_LOCATION = 2
    AT_FARMER = 3
    MOVE_TO_LOCATION = 4
    MOVE_TO_FARMER = 5
    BUYING = 6
    SELLING = 7
    GAME_OVER = 8
