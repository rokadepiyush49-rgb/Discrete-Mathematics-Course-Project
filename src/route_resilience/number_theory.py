"""Modular arithmetic (syllabus Unit 5), used for reproducible sampling and spatial indexing.

These tools play a supporting role. The project needs a repeatable way to pick which roads to
hide, and a compact key for grid cells, and both have clean number-theoretic constructions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def gcd(a: int, b: int) -> int:
    """Euclid's algorithm."""
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    """Return (g, x, y) with a*x + b*y = g = gcd(a, b): Bézout's identity."""
    old_r, r = a, b
    old_x, x = 1, 0
    old_y, y = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_x, x = x, old_x - q * x
        old_y, y = y, old_y - q * y
    return old_r, old_x, old_y


def mod_inverse(a: int, m: int) -> int:
    """The x with a*x ≡ 1 (mod m). It exists exactly when gcd(a, m) = 1."""
    g, x, _ = extended_gcd(a % m, m)
    if g != 1:
        raise ValueError(f"{a} has no inverse modulo {m}")
    return x % m


def fermat_inverse(a: int, p: int) -> int:
    """For prime p, a^(p-1) ≡ 1, so a^(p-2) is the inverse of a."""
    return pow(a, p - 2, p)


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    return all(n % d for d in range(2, math.isqrt(n) + 1))


def prime_factors(n: int) -> dict[int, int]:
    """Fundamental Theorem of Arithmetic: the unique factorisation of n."""
    factors: dict[int, int] = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors[d] = factors.get(d, 0) + 1
            n //= d
        d += 1
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


def euler_phi(n: int) -> int:
    """Count of 1 <= k <= n with gcd(k, n) = 1.

    Inclusion-exclusion over the prime divisors gives n * Π(1 - 1/p).
    """
    result = n
    for p in prime_factors(n):
        result -= result // p
    return result


def crt(r1: int, m1: int, r2: int, m2: int) -> int:
    """Chinese Remainder Theorem: the unique x mod m1*m2 with x ≡ r1 (m1) and x ≡ r2 (m2)."""
    if gcd(m1, m2) != 1:
        raise ValueError("moduli must be coprime")
    return (r1 + m1 * (((r2 - r1) * mod_inverse(m1, m2)) % m2)) % (m1 * m2)


@dataclass(frozen=True, slots=True)
class AffinePermutation:
    """x -> (a*x + b) mod m. A bijection on Z_m exactly when gcd(a, m) = 1.

    This gives a seeded shuffle that repeats nothing, needs no random-number library, and can be
    run backwards with a modular inverse. There are m * φ(m) such shuffles.
    """

    m: int
    a: int
    b: int

    def __post_init__(self) -> None:
        if gcd(self.a, self.m) != 1:
            raise ValueError("a must be coprime to m")

    @classmethod
    def from_seed(cls, m: int, seed: int) -> AffinePermutation:
        # Start near m/φ (the golden ratio) so that consecutive outputs spread out well.
        a = max(1, int(m * 0.6180339887) + seed)
        while gcd(a, m) != 1:
            a += 1
        return cls(m, a % m if m > 1 else 0, (seed * 2654435761) % m)

    def __call__(self, x: int) -> int:
        return (self.a * x + self.b) % self.m

    def inverse(self, y: int) -> int:
        return (mod_inverse(self.a, self.m) * (y - self.b)) % self.m

    @property
    def family_size(self) -> int:
        return self.m * euler_phi(self.m)


class CRTGrid:
    """Packs a grid cell (row, col) into one integer through the CRT.

    Consecutive integers are coprime, so moduli m and m + 1 give each cell a distinct key
    for grids up to m rows by m + 1 columns.
    """

    def __init__(self, cells_per_side: int) -> None:
        self.m1 = cells_per_side + 1
        self.m2 = cells_per_side + 2

    def key(self, row: int, col: int) -> int:
        return crt(row % self.m1, self.m1, col % self.m2, self.m2)
