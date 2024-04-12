"""Hold references to noise objects used in random feature generation.

"""
import random

import numpy as np

from typing import Dict, List, Tuple

from perlin_numpy import generate_perlin_noise_3d

from .good import Good

MIN_FARMER_PROD_PROBABILITY = 0.15


class NoiseController:
    def __init__(
            self,
            seed: int,
            goods: List[Good],
            year_length: int,
            prod_params: Dict[str, int],
            farmer_params: Dict[str, int]):
        """

        Args:
            seed (int): Base RNG seed
            goods (List[Good]): List of available goods.
            year_length (int): Length of each year.
            prod_params (Dict[str, int]): Production generation params:
                spatial_octaves (int): Number of spatial perlin noise octaves.
                spatial_res (int): Spatial perlin noise resolution.
                temporal_octaves (int): Number of temporal perlin noise octaves.
                temporal_res (int): Temporal perlin noise resolution.
            farmer_params (Dict[str, int]): Farmer random generation params:
                mean_n_goods (float): Mean number of goods a farmer produces.
                min_n_goods (float): Minimum number of goods a farmer produces.
        """
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

        self.year_length = year_length
        self.prod_params = prod_params
        self.farmer_params = farmer_params

        self.good_prod_maps = {
            good: self.generate_good_prod(good)
            for good in goods}
        return

    def generate_farmer_good_dist(self, goods: List[Good]) -> Dict[Good, float]:
        """Produce a farmer production distribution over available goods.

        Args:
            goods (List[Good]): List of available goods.:

        Returns:
            good_dist (Dict[Good, float]): Farmer production rates per good.

        """
        mean_n_goods = self.farmer_params['mean_n_goods']
        min_n_goods = self.farmer_params['min_n_goods']

        popularities = np.array([good.popularity for good in goods])
        pop_probs = popularities / np.sum(popularities)
        scaled_pop_probs = np.minimum(mean_n_goods * pop_probs, 1)
        # Keep trying to generate a subset until the min is achieved
        found_n_goods = -1
        while found_n_goods < min_n_goods:
            selections = np.random.rand(len(goods)) < scaled_pop_probs
            found_n_goods = selections.sum()
        prod_rates = np.maximum(
            np.random.rand(len(goods)), MIN_FARMER_PROD_PROBABILITY)
        selected_prod_rates = selections * prod_rates
        return {good: rate for good, rate in zip(goods, selected_prod_rates)}

    def generate_good_prod(self, good: Good) -> np.ndarray:
        """Generate a 3D good production rate map.

        Args:
            good (Good): Good this production rate map is for.

        Returns:
            prod_map (np.ndarray): 3D good production rate map.

        """
        nx = self.prod_params['spatial_res']
        ox = self.prod_params['spatial_octaves']
        nt = self.prod_params['temporal_res']
        ot = self.prod_params['temporal_octaves']
        noise = generate_perlin_noise_3d(
            (nt, nx, nx), (ot, ox, ox), tileable=(True, False, False))
        # Rescale and exponentiate
        noise = (noise - noise.min()) / (noise.max() - noise.min())
        noise = noise ** good.prod_rate_exponent
        return noise

    def sample_good_prod(
            self, good: Good, day: int, location: Tuple[float, float]) -> float:
        """Sample a good's production rate map at a time and location.

        Args:
            good (good): Good to sample a production map for.
            day (int): Day to sample for.
            location (Tuple[float, float]): Location to sample for.

        Returns:
            sample_value (float): Sample value.

        """
        return self.sample_3d(
            self.good_prod_maps[good],
            day / self.year_length,
            location[0],
            location[1])

    def sample_good_increment(self, prod_rate: float) -> int:
        """Calculate a good's per-turn quantity increment based on its
        production rate.

        Args:
            prod_rate (float): Per-turn production rate

        Returns:
            increment (int): Good quantity increment.

        """
        if prod_rate == 0:
            return 0
        if prod_rate <= 1:
            return round(np.random.exponential(prod_rate))
        return np.maximum(0, round(np.random.exponential(prod_rate + 1) - 1))

    def sample_location(self) -> Tuple[float, float]:
        """Sample a 2D "location" in the range [0,1]x[0,1].

        Returns:
            location_x: X location.
            location_y: Y location.

        """
        location_x = random.random()
        location_y = random.random()
        return location_x, location_y

    @staticmethod
    def sample_3d(arr: np.ndarray, tp: float, yp: float, xp: float) -> float:
        """Sample a 3D array using trilinear interpolation.

        Args:
            arr (np.ndarray): A 3D array.
            tp (float): First axis sample coordinate, scaled to range [0,1].
            yp (float): Second axis sample coordinate, scaled to range [0, 1].
            xp (float): Third axis sample coordinate, scaled to range [0, 1].

        Returns:
            c (float): Trilinearly-interpolated sample value.

        """
        T, Y, X = arr.shape

        # Scale tp, yp, xp to the array dimensions
        tp = tp * (T - 1)
        yp = yp * (Y - 1)
        xp = xp * (X - 1)

        # Find the indices of the corners
        t0, y0, x0 = int(np.floor(tp)), int(np.floor(yp)), int(np.floor(xp))
        t1, y1, x1 = min(t0 + 1, T - 1), min(y0 + 1, Y - 1), min(x0 + 1, X - 1)

        # Compute the differences
        dt, dy, dx = tp - t0, yp - y0, xp - x0

        # Interpolate along x axis
        c00 = arr[t0, y0, x0] * (1 - dx) + arr[t0, y0, x1] * dx
        c01 = arr[t0, y1, x0] * (1 - dx) + arr[t0, y1, x1] * dx
        c10 = arr[t1, y0, x0] * (1 - dx) + arr[t1, y0, x1] * dx
        c11 = arr[t1, y1, x0] * (1 - dx) + arr[t1, y1, x1] * dx

        # Interpolate along y axis
        c0 = c00 * (1 - dy) + c01 * dy
        c1 = c10 * (1 - dy) + c11 * dy

        # Finally, interpolate along t axis
        c = c0 * (1 - dt) + c1 * dt

        return c