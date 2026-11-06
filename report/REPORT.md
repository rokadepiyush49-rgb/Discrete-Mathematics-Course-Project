# Route Resilience: discrete mathematics on Pune's road network

Discrete Mathematics course project, Vishwakarma Institute of Technology, Computer Engineering, AY 2026-27.

Based on Problem Statement 4 of the [Bharatiya Antariksh Hackathon 2026](https://hack2skill.com/event/bah2026/) (ISRO): *Route Resilience: Occlusion-Robust Road Extraction & Graph-Theoretic Criticality Analysis for Urban Mobility*. The hackathon has ended, so this is a course project and not a competition entry.

## 1. Summary

Satellite road extraction loses roads under tree canopy, shadow and cloud, which leaves a broken network that cannot be routed on. We take the real road network of central Pune, simulate that damage, repair it with graph algorithms, find the junctions the city depends on, and measure what happens when they fail.

Every core algorithm is written from scratch and tested against an independent implementation. The main results are:

1. **Kruskal's algorithm reconnects the network but restores no redundancy.** We prove every link it adds is a bridge. On real data it recovers 25.0% of true gaps and leaves travel times 49.1% wrong. Adding a loop-closure pass recovers 89.5% of gaps and cuts the error to 0.84%.
2. **The Resilience Index in the problem statement can improve when the network gets worse.** Under an attack on cut vertices it rises to 1.018 while efficiency falls to 0.953. We explain why and use efficiency instead.
3. **Busy is not the same as fragile.** Only 7 of the 50 highest-betweenness junctions are cut vertices. The most damaging cut vertex ranks 608th.
4. **Adaptive attacks are 1.9 times as damaging as a fixed ranking**, because traffic shifts after each closure.
5. **The generating-function prediction fails on roads.** It puts the collapse at 48.6% survival. Simulation finds 74.3%, because roads are not randomly wired.

## 2. Scope

The problem statement has four phases. This project covers the mathematical three.

| Phase in the statement | This project |
|---|---|
| I. Deep-learning road segmentation | **Not built.** It needs satellite imagery and GPUs, and it is not discrete mathematics. We simulate its output instead, which the statement allows ("mock or open-source vector baselines"). |
| II. Skeleton healing with MST and Disjoint Sets | Built, and extended with a second pass |
| III. Betweenness, node ablation, Resilience Index | Built, with a corrected index |
| IV. Interactive dashboard | Built |

Simulating occlusion has one real advantage: we know exactly which roads were hidden, so healing can be scored precisely.

## 3. The model

Let $G = (V, E, w)$ be a simple undirected weighted graph. Vertices are junctions and dead ends, edges are stretches of road between them, and $w(e)$ is free-flow travel time in seconds, from road length and an assumed speed per road class.

The data is OpenStreetMap, from a Geofabrik extract clipped to Deccan through Camp. We parse it directly: a point becomes a vertex if it ends a way or is shared by two or more ways, each way is split at its vertices, self-loops and parallel edges are removed, degree-2 vertices are contracted, and only the largest component is kept.

| Measure | Value |
|---|---:|
| Junctions $n$ | 3,973 |
| Roads $m$ | 5,424 |
| Total length | 405.7 km |
| Dead ends | 814 |
| Degree 3 / degree 4 junctions | 2,593 / 551 |
| Hospitals and fire stations | 156 |

## 4. The pipeline

1. **Occlusion.** 40 canopy patches of radius 260 m hide 55% of the roads inside them, and 2% of roads elsewhere are hit by clutter. Roads under 40 m are left alone. Each hidden road keeps two stubs and loses up to 90 m in the middle. Road choice comes from an affine permutation (Theorem 5).
2. **Healing.** Candidate links join dangling ends. A link must pass a gate on distance and alignment. Pass 1 runs Kruskal between components. Pass 2 closes aligned gaps within a component.
3. **Criticality.** Brandes' algorithm gives betweenness for every junction and road. Tarjan's algorithm gives cut vertices and bridges.
4. **Stress test.** Junctions are removed in a chosen order and the network is re-measured.
5. **Response.** Crews are matched to sites, repairs are coloured into days, and inspection routes are built from Euler tours.
6. **Audit.** 15 theorems are checked against the final graph, with the numbers shown.

The acceptance rules are propositional formulas over a candidate link $(a, b)$ with distance $d$ and alignment angle $\theta$:

$$\text{Pass 1: } (d \le D) \land (\theta \le \Theta) \land \lnot\,\mathrm{same}(a,b) \land \lnot\,\mathrm{used}(a) \land \lnot\,\mathrm{used}(b)$$

$$\text{Pass 2: } (d \le D) \land (\theta \le \Theta_2) \land \lnot\,\mathrm{used}(a) \land \lnot\,\mathrm{used}(b)$$

with $D = 120$ m, $\Theta = 50°$ and $\Theta_2 = 25°$. If Pass 1 leaves more than one component, a closure sweep repeats it with $D = 180$ m and no angle test. Connectivity is required, and on curved roads the alignment test can be wrong.

## 5. Proofs

**Lemma 1 (connectivity is an equivalence relation).** Define $u \sim v$ when a path joins $u$ and $v$.

*Proof.* Reflexive: the trivial path. Symmetric: reverse the path. Transitive: joining a $u$-$v$ path to a $v$-$w$ path gives a $u$-$w$ walk, and every walk contains a path. ∎

So the components partition $V$, and this partition is exactly what the Disjoint Set stores. Each `union` merges two classes, and `find` names a class.

**Theorem 2 (Kruskal's algorithm is optimal).** Suppose edge weights are distinct, or ties are broken by a fixed order.

*Cut property, by contradiction.* Let $e$ be the lightest edge crossing a cut $(S, V \setminus S)$, and suppose a minimum spanning tree $T$ omits $e$. Then $T + e$ contains a cycle through $e$. A cycle crosses a cut an even number of times, so the cycle contains another crossing edge $f$, with $w(f) > w(e)$. Now $T - f + e$ is a lighter spanning tree, which is a contradiction.

*Correctness, by induction on accepted edges.* The invariant is that the accepted set $F$ lies inside some minimum spanning forest. It holds for $F = \emptyset$. Let the next accepted edge be $e = ab$, and let $S$ be the class of $a$ under $F$. Any lighter edge crossing $S$ would have joined two classes when it was examined, and so would be in $F$. But no edge of $F$ crosses $S$. So $e$ is the lightest edge crossing $S$, and the cut property extends the invariant. ∎

*Caveat.* Our Pass 1 also uses each dangling end at most once, because a road continues in one direction. With that rule the result is a greedy forest, and Theorem 2 no longer guarantees minimum cost. Degree-constrained spanning trees are NP-hard in general. Lemma 3 does not depend on optimality.

**Lemma 3 (every Kruskal link is a bridge).** Let $L$ be links added to a graph $G$, each joining two different components at the moment it is added. Then every link in $L$ is a bridge of $G + L$.

*Proof.* Contract each component of $G$ to a point, giving a graph $H$ whose edges are exactly $L$. Suppose $H$ had a cycle, and consider its last-added link. Its ends were already connected by the earlier links of that cycle, so it did not join two components. This is a contradiction, so $H$ is a forest, and every edge of a forest is a bridge.

Now suppose some $\ell \in L$ lay on a cycle of $G + L$. Contraction would turn that cycle into a closed walk in $H$ using $\ell$ exactly once. Removing $\ell$ leaves a walk between its ends in $H - \ell$, so $\ell$ would lie on a cycle of $H$, which is a contradiction. ∎

**Corollary 4 (cycle rank).** The number of independent cycles is $\beta(G) = m - n + c$. A link between components sends $m \to m + 1$ and $c \to c - 1$, so $\beta$ does not change. A link inside a component raises $\beta$ by exactly 1. Subdividing an edge sends $m \to m+1$ and $n \to n+1$, so $\beta$ does not change.

Real data matches exactly: occlusion leaves $\beta = 905$, Kruskal's 204 links leave it at 905, and 509 loop links raise it to $905 + 509 = 1414$.

The last part matters. Stubs subdivide roads, which inflates the spanning tree count: a cycle of length $L$ has $L$ spanning trees. Our healed graph has about $10^{1053}$ spanning trees and the real map only about $10^{952}$, even though the healed graph has fewer cycles. We therefore compare stages by $\beta$, which subdivision cannot distort.

**Theorem 5 (affine bijection).** The map $x \mapsto ax + b$ on $\mathbb{Z}_m$ is a bijection if and only if $\gcd(a, m) = 1$.

*Proof.* If $\gcd(a, m) = 1$, Bézout gives $s, t$ with $as + mt = 1$, so $as \equiv 1$, and $y \mapsto s(y - b)$ is an inverse. If $d = \gcd(a, m) > 1$, then $a \cdot (m/d) \equiv 0$, so $0$ and $m/d$ collide. ∎

There are therefore $m\,\varphi(m)$ such shuffles. For $m = 5424 = 2^4 \cdot 3 \cdot 113$, inclusion-exclusion over the primes gives $\varphi(m) = 5424 \cdot \tfrac12 \cdot \tfrac23 \cdot \tfrac{112}{113} = 1792$, so 9,719,808 shuffles. We use $x \mapsto (3359x + 4711) \bmod 5424$.

The candidate search bins dangling ends into grid cells, and the Chinese Remainder Theorem packs a cell into one key. Consecutive integers are coprime, so $(r, c) \mapsto x$ with $x \equiv r \pmod{M}$ and $x \equiv c \pmod{M+1}$ is injective.

**Theorem 6 (pigeonhole on routes).** If $k$ edge-disjoint routes join $O$ and $D$, then any $k - 1$ road closures leave a route open.

*Proof.* Each closed road lies on at most one route, because the routes share no road. So $k - 1$ closures touch at most $k - 1$ of the $k$ routes. ∎

Menger's theorem says this is tight: the largest such $k$ equals the smallest number of roads that separate $O$ from $D$. We find the routes by unit-capacity maximum flow, and the tests confirm that the cut found always has exactly $k$ roads.

**Proposition 7 (double counting betweenness).** Fix a source $s$ and assume shortest paths are unique. Then $\sum_v \delta(s, v) = \sum_t (h(s, t) - 1)$, where $h$ counts edges on the path.

*Proof.* Count the pairs $(t, v)$ where $v$ is an interior vertex of the $s$-$t$ path. Grouping by $v$ gives the left side. Grouping by $t$ gives the right side, since a path of $h$ edges has $h - 1$ interior vertices. ∎

Betweenness and path lengths come from separate code, so this is a real check. Over 24 sources on the real graph both sides equal 7,605,476.

**Brandes' recurrences.** Let $\sigma(s, v)$ count shortest paths and $P(v)$ be the predecessors of $v$ on them. Each shortest path to $v$ ends with one edge from one predecessor, so

$$\sigma(s, v) = \sum_{u \in P(v)} \sigma(s, u).$$

A fraction $\sigma(s,v)/\sigma(s,w)$ of the paths to $w$ pass through $v$, and each carries the trip to $w$ plus all dependency beyond $w$, so

$$\delta(s, v) = \sum_{w:\, v \in P(w)} \frac{\sigma(s, v)}{\sigma(s, w)} \bigl(1 + \delta(s, w)\bigr).$$

Evaluating these forwards and backwards from each source costs $O(n(m + n \log n))$ in total, with no list of the 14,985,075 pairs.

**Proposition 8 (a linear recurrence for parallel streets).** Let $t_n$ count spanning trees of a ladder with $n$ rungs: two parallel roads joined by $n$ cross streets. Then $t_n = 4t_{n-1} - t_{n-2}$.

*Proof.* Let $f_n$ count spanning forests with exactly two components, separating the two end vertices. Add a new rung, with its two rail edges. A spanning tree of the larger ladder restricts either to a spanning tree (3 ways to attach, choosing two of the three new edges) or to such a forest (1 way, using all three). So $t_{n+1} = 3t_n + f_n$. Likewise $f_{n+1} = 2t_n + f_n$. Substituting $f_n = t_{n+1} - 3t_n$ into the second equation gives $t_{n+2} = 4t_{n+1} - t_n$. ∎

The characteristic equation $x^2 - 4x + 1 = 0$ has roots $2 \pm \sqrt 3$. With $t_1 = 1$ and $t_2 = 4$:

$$t_n = \frac{(2 + \sqrt 3)^n - (2 - \sqrt 3)^n}{2\sqrt 3}.$$

The tests confirm the recurrence and the closed form against Kirchhoff's Matrix-Tree Theorem.

**Proposition 9 (handshake).** $\sum_v \deg(v) = 2m$, since each edge has two ends. So the number of odd-degree vertices is even, and the Route Inspection problem can always pair them up. Duplicating shortest paths between pairs makes every degree even, so an Euler tour exists, and Hierholzer's algorithm finds it.

**Generating functions.** Let $G_0(x) = \sum_k p_k x^k$ be the degree generating function. Following a random road, the excess degree has $G_1(x) = G_0'(x) / G_0'(1)$. A giant component needs $G_1'(1) > 1$. If a fraction $q$ of junctions survive, it persists while $q\,G_1'(1) > 1$, so the predicted threshold is $q_c = 1 / G_1'(1)$.

For repair budgets, in $\prod_i (1 + x^{c_i})$ each factor chooses whether job $i$ is done, so the coefficient of $x^b$ counts the sets of jobs costing exactly $b$.

**Inclusion-exclusion.** Let $A_v$ be the trips whose fastest route passes through junction $v$. Then

$$\Bigl|\bigcup_v A_v\Bigr| = \sum_{\emptyset \ne T} (-1)^{|T|+1} \Bigl|\bigcap_{v \in T} A_v\Bigr|.$$

The same principle counts onto functions, which is the number of ways to split $m$ jobs among $k$ crews with none idle: $\sum_i (-1)^i \binom{k}{i} (k - i)^m$.

**Hall's theorem.** Crews can be matched to all sites if and only if every set $S$ of sites can reach at least $|S|$ crews. When a site goes unserved, the alternating-path search returns a set $S$ with $|N(S)| < |S|$. This is a checkable proof that no better plan exists.

## 6. Results

### Healing

| Stage | Components | Cycles $\beta$ | Trips possible | Travel-time error |
|---|---:|---:|---:|---:|
| Real map | 1 | 1,452 | 100% | 0% |
| Occluded | 205 | 905 | 69.9% | 40.0% |
| Kruskal only | 1 | 905 | 100% | 49.1% |
| Kruskal + loops | 1 | 1,414 | 100% | 0.84% |

The occluded error covers only trips that still exist, which is why it looks better than the Kruskal row.

| Method | Links | Correct | Gaps found | Precision | Links that are bridges |
|---|---:|---:|---:|---:|---:|
| Kruskal only | 204 | 188 | 25.0% | 92.2% | 204 of 204 |
| Kruskal + loops | 713 | 672 | 89.5% | 94.2% | 102 of 713 |

Kruskal adds exactly $205 - 1 = 204$ links, as a tree on 205 components must.

Over 20 seeds, recall with loops was 89.4% (SD 0.9, range 88.0% to 91.2%) and precision was 94.0% (SD 0.7, range 92.9% to 95.1%). Kruskal alone averaged 24.5%. The network ended connected every time, and Lemma 3 held every time.

### Criticality

The busiest junctions lie along Shivaji Road, led by the Laxmi Path junction with betweenness 0.220. Of the top 50 in the healed graph, 40 are also in the top 50 of the real map, so the healed network preserves most of the true ranking.

The healed network has 888 cut vertices and 1,230 bridges. Most guard short dead ends. Only 7 of the top 50 junctions are cut vertices. The most damaging one, on Jagannath Shankarsheth Marg, strands 52 junctions but ranks 608th by betweenness. Betweenness measures how much traffic is displaced. Cut vertices measure who gets cut off. A planner needs both.

### Stress test

Removing 30 junctions (0.75% of the total), measured from 200 sampled sources:

| Attack | Efficiency index | Path-ratio index | Trips still possible |
|---|---:|---:|---:|
| Adaptive betweenness | 0.881 | 0.833 | 99.3% |
| Fixed betweenness | 0.936 | 0.941 | 98.4% |
| Worst cut vertices | 0.953 | **1.018** | 93.3% |
| Random (mean of 5) | 0.983 | 0.987 | 99.4% |
| Highest degree | 0.989 | 0.992 | 99.7% |

**Why the problem statement's index misleads.** It is defined as $R = \bar{L}_{\text{before}} / \bar{L}_{\text{after}}$, the ratio of average shortest path lengths. An average over reachable pairs cannot see a stranded trip. In the cut-vertex row, 6.7% of trips become impossible. Those trips averaged 463 s before the attack, against 355 s for the rest, so losing them pulls the average down from 362.9 s to 356.3 s, and $R = 362.9 / 356.3 = 1.018$. The surviving trips actually got 1 s slower. The index reports an improvement while the network is breaking apart.

We use global efficiency instead: $E = \frac{1}{n(n-1)} \sum_{s \ne t} 1/d(s,t)$, with $1/\infty = 0$. A stranded pair then counts as a total loss, and $E$ stays defined however badly the graph breaks. The statement's text in fact mentions efficiency, while its formula uses path length.

**Exhaustive search is out of the question.** There are $\binom{5475}{3} = 27{,}337{,}771{,}825$ ways to fail just three vertices. That is why we need a ranking at all. The adaptive row shows that a fixed ranking is not enough, because recomputing after each closure does 1.9 times the damage.

### Percolation

The degree distribution gives mean degree 2.73 and $G_1'(1) = 2.06$, so the theory predicts collapse at $q_c = 48.6\%$. Simulation by the Newman-Ziff method (40 runs) puts the transition near 74.3%. The theory is too optimistic because it assumes random wiring, whereas a junction can only connect to its neighbours in space, so redundancy is local. The simulated figure is close to site percolation on a honeycomb lattice (about 69.7%), which fits a network dominated by degree-3 junctions.

### Theorem audit

All 15 checks hold on the healed network. They include the handshake lemma, $(A^2)_{ii} = \deg(i)$, $BB^T = D + A$, the double-counting identity, and the Matrix-Tree theorem by two independent methods (cofactor and eigenvalues, both $10^{1052.55}$).

The planarity test reports that both the real and healed graphs are **not planar**, which is correct: flyovers cross without a junction. The bound $|E| \le 3n - 6$ still holds (6,888 against 16,419), but it is only a necessary condition. Euler's formula is therefore not applied.

## 7. Syllabus coverage

"Core" means the project depends on the topic. "Supporting" means it is used in a real but replaceable role.

| Unit | Topics used | Where | Role |
|---|---|---|---|
| 1. Logic and proofs | Sets, relations, propositional logic, direct proof, contradiction, contrapositive, induction, correctness of programs | Healing gates, Lemma 1, Theorem 2, Lemma 3, loop invariants | Core |
| 2. Basic counting | Combinations, binomial coefficients, double counting | Failure scenarios, Proposition 7, handshake | Core |
| 3. Advanced combinatorics | Pigeonhole, inclusion-exclusion, onto functions, Euler's phi, Mantel's theorem | Theorem 6, trip overlap, crew splits, shuffle count | Core |
| 4. Recurrences and generating functions | Modelling with recurrences, linear homogeneous solution, generating functions in counting | Brandes, Proposition 8, percolation, repair budgets | Core |
| 5. Modular arithmetic | Euclid, extended Euclid, modular inverse, Fermat, prime factorisation, Euler's phi, CRT | Reproducible shuffle, grid keys | Supporting |
| 6. Graph theory | Matrices, components, degree, paths, cycles, Euler tours, trees, bipartite graphs, planarity, colouring, bipartite matching | Throughout | Core |

Not used, because they would have been forced: Ramsey theory, Turán's general theorem, the Erdős-Szekeres theorem, derangements, Catalan numbers, partitions, Tower of Hanoi, and Hamiltonian tours.

## 8. Testing

There are 65 automated tests, using Hypothesis to generate random inputs. The hand-written algorithms are compared with independent references:

| Algorithm | Checked against |
|---|---|
| Dijkstra, Brandes (node and edge, with and without ties) | NetworkX |
| Tarjan's cut vertices and bridges, 2-colouring | NetworkX |
| Edge-disjoint routes, minimum cut | NetworkX edge connectivity |
| Hopcroft-Karp | NetworkX, plus Hall certificates |
| Efficiency and average path | NetworkX, on the Petersen graph |
| Modular arithmetic, inclusion-exclusion, surjections, budget coefficients | Python's standard library and brute force |

Lemma 3 is tested on random forests and on the real map. Theorem 6 is tested by closing arbitrary sets of $k - 1$ roads. Tests also exercise the full HTTP API on the real network.

## 9. Limitations

- **No real imagery.** Occlusion is simulated, so healing accuracy here is not the accuracy of a real satellite pipeline. Real masks also have false roads and misaligned edges.
- **Simplified occlusion.** Gaps are at most 90 m and always leave two stubs. Whole roads vanishing under cloud would be harder.
- **One-way streets are ignored.** The graph is undirected, which will misjudge parts of central Pune.
- **Assumed speeds, no traffic.** Weights are free-flow estimates, and every pair of junctions counts equally. Real demand would change the ranking.
- **Edge effects.** Clipping to a box creates false dead ends near the border and underrates junctions there.
- **Sampling.** Stress curves use 200 sources, and the trip-overlap table uses 120. Betweenness and the audit's theorems use the full graph, except the double-counting check, which uses 24 sources.
- **One city, one study area.** The findings on percolation in particular may differ elsewhere.
- **Modular arithmetic is supporting only.** A library shuffle would work just as well for the project's results.

## 10. Reproducing the results

Everything is deterministic for a given seed:

```bash
uv sync
uv run route-resilience build
uv run pytest
```

The dashboard instructions are in the [README](../README.md).

## References

1. K. H. Rosen, *Discrete Mathematics and Its Applications*, 7th ed. McGraw-Hill, 2011.
2. D. B. West, *Introduction to Graph Theory*, 2nd ed. Prentice-Hall, 2001.
3. R. Diestel, *Graph Theory*, 5th ed. Springer, 2017.
4. U. Brandes, "A faster algorithm for betweenness centrality," *Journal of Mathematical Sociology*, 25(2), 2001.
5. R. E. Tarjan, "Depth-first search and linear graph algorithms," *SIAM Journal on Computing*, 1(2), 1972.
6. J. E. Hopcroft and R. M. Karp, "An n^(5/2) algorithm for maximum matchings in bipartite graphs," *SIAM Journal on Computing*, 2(4), 1973.
7. V. Latora and M. Marchiori, "Efficient behavior of small-world networks," *Physical Review Letters*, 87, 2001.
8. M. Molloy and B. Reed, "A critical point for random graphs with a given degree sequence," *Random Structures & Algorithms*, 6, 1995.
9. M. E. J. Newman and R. M. Ziff, "Efficient Monte Carlo algorithm and high-precision results for percolation," *Physical Review Letters*, 85, 2000.
10. OpenStreetMap contributors. Road data available under the Open Database License.
