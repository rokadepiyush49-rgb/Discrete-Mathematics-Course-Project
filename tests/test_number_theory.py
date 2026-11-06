import math

from hypothesis import given
from hypothesis import strategies as st

from route_resilience.number_theory import (
    AffinePermutation,
    CRTGrid,
    crt,
    euler_phi,
    extended_gcd,
    fermat_inverse,
    gcd,
    is_prime,
    mod_inverse,
    prime_factors,
)

positive = st.integers(1, 10**6)


@given(positive, positive)
def test_gcd_matches_stdlib(a, b):
    assert gcd(a, b) == math.gcd(a, b)


@given(positive, positive)
def test_bezout_identity(a, b):
    g, x, y = extended_gcd(a, b)
    assert a * x + b * y == g == math.gcd(a, b)


@given(st.integers(2, 10**5), st.integers(1, 10**5))
def test_modular_inverse_exists_iff_coprime(m, a):
    if math.gcd(a, m) == 1:
        assert (a * mod_inverse(a, m)) % m == 1 % m
    else:
        try:
            mod_inverse(a, m)
        except ValueError:
            return
        raise AssertionError("expected no inverse")


def test_fermat_agrees_with_euclid():
    for p in (101, 7919, 104729):
        assert is_prime(p)
        for a in (2, 3, 5, 99):
            assert fermat_inverse(a, p) == mod_inverse(a, p)


@given(st.integers(2, 10**6))
def test_fundamental_theorem_of_arithmetic(n):
    factors = prime_factors(n)
    assert all(is_prime(p) for p in factors)
    assert math.prod(p**e for p, e in factors.items()) == n


@given(st.integers(1, 3000))
def test_phi_matches_direct_count(n):
    assert euler_phi(n) == sum(math.gcd(k, n) == 1 for k in range(1, n + 1))


@given(st.integers(2, 500), st.integers(0, 10**4), st.integers(0, 10**4))
def test_crt_solution_is_unique_and_correct(m, r1, r2):
    m2 = m + 1  # Consecutive integers are coprime.
    x = crt(r1 % m, m, r2 % m2, m2)
    assert x % m == r1 % m and x % m2 == r2 % m2 and 0 <= x < m * m2


@given(st.integers(2, 2000), st.integers(0, 50))
def test_affine_map_is_a_bijection_with_an_inverse(m, seed):
    p = AffinePermutation.from_seed(m, seed)
    assert sorted(p(x) for x in range(m)) == list(range(m))
    assert all(p.inverse(p(x)) == x for x in range(m))


def test_crt_grid_keys_are_injective():
    grid = CRTGrid(40)
    keys = {grid.key(r, c) for r in range(41) for c in range(42)}
    assert len(keys) == 41 * 42
