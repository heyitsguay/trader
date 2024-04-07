"""A trade good.

Each Good has a base price and base production rate.

The production rate is modified at Locations, which in turn affects final
buy/sell prices at each location.

"""


class Good:
    def __init__(
            self,
            name: str,
            base_price: float,
            base_prod_rate: float):
        self.name = name
        self.base_price = base_price
        self.base_prod_rate = base_prod_rate
        return
