"""Deterministic quantity decomposition shared by package design tools.

The smooth-number definition originated in Bag Selection.  Keeping it here
allows Bag and Container Design Mode to use exactly the same rounding and
factor-distribution rules without coupling the container engine to bag UI code.
"""

from typing import List, Tuple


def is_smooth(quantity: int) -> bool:
    """Return whether *quantity* has no prime factors other than 2, 3, and 5."""
    if quantity <= 0:
        return False
    remainder = int(quantity)
    for factor in (2, 3, 5):
        while remainder % factor == 0:
            remainder //= factor
    return remainder == 1


def get_prime_factors(quantity: int) -> List[int]:
    factors: List[int] = []
    divisor = 2
    remainder = int(quantity)
    while divisor * divisor <= remainder:
        while remainder % divisor == 0:
            factors.append(divisor)
            remainder //= divisor
        divisor += 1
    if remainder > 1:
        factors.append(remainder)
    return factors


def next_smooth_quantity(desired_quantity: int) -> int:
    """Apply Bag Selection's existing upward 2/3/5-smooth rounding rule."""
    desired = int(desired_quantity)
    if desired <= 0:
        raise ValueError("Desired quantity must be a positive integer.")
    design_quantity = desired
    while not is_smooth(design_quantity):
        design_quantity += 1
    return design_quantity


def generate_factor_arrangements(quantity: int, dimensions: int) -> List[Tuple[int, ...]]:
    """Distribute prime factors over 2D or 3D integer axes deterministically.

    This is the same recursive factor distribution formerly embedded in Bag
    Selection's ``get_final_packing_solution`` function.
    """
    if int(quantity) <= 0:
        raise ValueError("Quantity must be a positive integer.")
    if int(dimensions) not in (2, 3):
        raise ValueError("Only two- and three-dimensional arrangements are supported.")

    factors = get_prime_factors(int(quantity))
    arrangements = set()

    def distribute(index: int, axes: Tuple[int, ...]) -> None:
        if index == len(factors):
            arrangements.add(axes)
            return
        factor = factors[index]
        for axis_index in range(dimensions):
            updated = list(axes)
            updated[axis_index] *= factor
            distribute(index + 1, tuple(updated))

    distribute(0, tuple(1 for _ in range(dimensions)))
    return sorted(arrangements)
