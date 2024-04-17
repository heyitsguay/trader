"""Hold references to noise objects used in random feature generation.

"""
import os
import random

import numpy as np

from typing import Any, Dict, List, Tuple

from perlin_numpy import generate_perlin_noise_3d

from .good import Good

LOCATION_GRID_SIZE = 256
MIN_FARMER_PROD_PROBABILITY = 0.15


class NoiseController:
    def __init__(
            self,
            seed: int,
            goods: List[Good],
            year_length: int,
            prod_params: Dict[str, int],
            location_params: Dict[str, Any],
            farmer_params: Dict[str, float]):
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
            location_params (Dict[str, Any]): Location generation params:
                n_locations (int): Number of locations.
                n_clusters (int): Number of location clusters. Each cluster
                    contributes a Gaussian function to an empirical probability
                    density function.
                amp_min (float): Minimum cluster amplitude.
                amp_max (float): Maximum cluster amplitude.
                std_min (float): Minimum cluster standard deviation.
                std_max (float): Maximum cluster standard deviation.
            farmer_params (Dict[str, float]): Farmer generation params:
                mean_n_goods (float): Mean number of goods a farmer produces.
                min_n_goods (float): Minimum number of goods a farmer produces.
        """
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        self.rng = np.random.default_rng(seed)

        self.year_length = year_length
        self.prod_params = prod_params
        self.location_params = location_params
        self.farmer_params = farmer_params

        self.location_cdf = self.init_location_density()

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
            selections = self.rng.random(len(goods)) < scaled_pop_probs
            found_n_goods = selections.sum()
        prod_rates = np.maximum(
            self.rng.random(len(goods)), MIN_FARMER_PROD_PROBABILITY)
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

    def init_location_density(self) -> np.ndarray:
        """Initialize the location density distribution.

        Distribution is a sum of Gaussians with random means, amplitudes, and
        widths.

        Returns:
            location_cdf (np.ndarray): CDF of the constructed location density
                function.

        """
        n_clusters = self.location_params['n_clusters']
        amp_min = self.location_params['amp_min']
        amp_max = self.location_params['amp_max']
        std_min = self.location_params['std_min']
        std_max = self.location_params['std_max']

        grid_y, grid_x = np.meshgrid(
            np.linspace(0, 1, LOCATION_GRID_SIZE),
            np.linspace(0, 1, LOCATION_GRID_SIZE))
        density = np.zeros((LOCATION_GRID_SIZE, LOCATION_GRID_SIZE))

        amps = amp_min + (amp_max - amp_min) * self.rng.random(n_clusters)
        means = self.rng.random((n_clusters, 2))
        stds = std_min + (std_max - std_min) * self.rng.random(n_clusters)

        for amp, mean, std in zip(amps, means, stds):
            gaussian = amp * np.exp(
                -((grid_y - mean[0])**2 + (grid_x - mean[1])**2) / (2 * std**2))
            density += gaussian
        density /= np.sum(density)

        location_cdf = np.cumsum(density.flatten())
        return location_cdf

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

    def sample_good_delta(
            self, prod_rate: float, amount: int, max_amount: int) -> int:
        """Calculate a good's per-turn quantity change based on its
        production rate.

        Increments are stochastic, and probability of applying an increment
        drops to 0 as the current amount approaches some maximum.

        Decrements are stochastic, and probability of appplying a decrement
        drops to 0 as the current amount approaches 0.

        Args:
            prod_rate (float): Per-turn production rate.
            amount (int): Current amount of the good.
            max_amount (int):

        Returns:
            increment (int): Good quantity increment.

        """
        increment = 0
        # Calculate an increment with some probability
        p_increment = min(1.0, max(0.0, (max_amount - amount) / (amount + 0.0001)))
        if random.random() < p_increment:
            if prod_rate == 0:
                increment = 0
            elif prod_rate <= 1:
                increment = round(self.rng.exponential(prod_rate))
            else:
                increment = np.maximum(0, round(self.rng.exponential(prod_rate + 1) - 1))

        decrement = 0
        # Calculate a decrement with some probability
        p_decrement = min(1.0, max(0.0, 0.25 + 0.5 * (amount / max_amount) / (1 + abs(1 - amount / max_amount))))
        if random.random() < p_decrement:
            decrement = (0.05 + 0.2 * random.random() * random.random()) * amount
        return increment - decrement

    def sample_location(self) -> Tuple[float, float]:
        """Sample a 2D "location" in the range [0,1]x[0,1] based on the
        constructed location CDF.

        Returns:
            location_x: X location.
            location_y: Y location.

        """
        r = self.rng.random()
        idx = np.searchsorted(self.location_cdf, r)
        y_idx, x_idx = np.unravel_index(idx, (LOCATION_GRID_SIZE, LOCATION_GRID_SIZE))
        location_x = x_idx / LOCATION_GRID_SIZE
        location_y = y_idx / LOCATION_GRID_SIZE
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
