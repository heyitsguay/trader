import sys

from trader.world import World


def main(seed: int, request_url: str, debug: bool):
    world = World(seed, request_url, debug)
    advance_day = True
    while True:
        advance_day = world.step(advance_day)
    return


if __name__ == '__main__':
    args = sys.argv[1:]
    request_url = 'http://mattg-2022:5000/v1/chat/completions'
    if len(args) > 0:
        request_url = args[0]
    seed = 134
    if len(args) > 1:
        seed = int(args[1])
    debug = False
    if len(args) > 2:
        debug = int(args[2]) > 0
    main(seed, request_url, debug)
