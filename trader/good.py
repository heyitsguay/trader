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
            base_prod_rate: float,
            prod_rate_multiplier: float,
            prod_rate_exponent: float,
            popularity: float,
            max_amount: int):
        self.name = name
        self.base_price = base_price
        self.base_prod_rate = base_prod_rate
        self.prod_rate_multiplier = prod_rate_multiplier
        self.prod_rate_exponent = prod_rate_exponent
        self.popularity = popularity
        self.max_amount = max_amount

        # Calculated after initialization
        self.base_abundance = None
        return

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def set_base_abundance(self, abundance: float):
        self.base_abundance = abundance
        return
