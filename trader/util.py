from math import exp
from typing import Callable

e_const = exp(1)


def bump(a: float, b: float) -> Callable[[float], float]:
    """Construct a bump function supported on [a, b].

    Args:
        a (float): Lower bound of the support interval.
        b (float): Upper bound of the support interval.

    Returns:
        bump_fn (Callable[[float], float]): Bump function.

    """
    if a >= b:
        raise ValueError("a must be less than b.")

    # Standard bump function exp(-1/(1-x^2)) is supported on [-1, 1]. Transform
    # the input variable for support on [a, b].
    def bump_fn(x: float) -> float:
        if x <= a or x >= b: return 0
        y = (x - a) / (b - a)  # Map [a, b] to [0, 1]
        z = 2 * y - 1  # Map [0, 1] to [-1, 1]
        return e_const * exp(-1/(1-z**2))

    return bump_fn
