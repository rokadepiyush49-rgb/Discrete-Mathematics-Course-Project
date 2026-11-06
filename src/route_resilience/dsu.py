"""Disjoint Set Union (union-find): a live partition of the vertices.

"Is connected to" is an equivalence relation, and a partition is what an equivalence relation
looks like when written down: each set here is one equivalence class.
"""

from __future__ import annotations


class DisjointSet:
    """Union by rank with path halving: near-constant amortised time per operation."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n
        self.size = [1] * n
        self.count = n

    def find(self, x: int) -> int:
        parent = self.parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        """Merge the classes of a and b. Returns False if they were already one class."""
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        self.size[a] += self.size[b]
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1
        self.count -= 1
        return True

    def same(self, a: int, b: int) -> bool:
        return self.find(a) == self.find(b)

    def classes(self) -> list[list[int]]:
        groups: dict[int, list[int]] = {}
        for x in range(len(self.parent)):
            groups.setdefault(self.find(x), []).append(x)
        return list(groups.values())
