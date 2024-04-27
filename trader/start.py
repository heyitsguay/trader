import sys

from trader.world import World


def main(seed: int, debug: bool):
    world = World(seed, debug)
    advance_day = True
    while True:
        advance_day = world.step(advance_day)
    return


if __name__ == '__main__':
    args = sys.argv[1:]
    seed = 134
    if len(args) > 0:
        seed = int(args[0])
    debug = False
    if len(args) > 1:
        debug = int(args[1]) > 0
    main(seed, debug)
