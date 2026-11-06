export type Coord = [number, number];

export type Gatekeeper = {
  vertex: number;
  name: string;
  betweenness: number;
  rank: number;
  is_cut_vertex: boolean;
  stranded: number;
  lon: number;
  lat: number;
};

export type StressPoint = {
  removed: number;
  average_path_s: number;
  efficiency: number;
  reachable_pairs: number;
  largest_component: number;
  r_average_path: number;
  r_efficiency: number;
};

export type HealRow = {
  true_gaps: number;
  links: number;
  correct: number;
  precision: number;
  recall: number;
  kruskal_links: number;
  loop_links: number;
  links_that_are_bridges: number;
};

export type StageRow = {
  name: string;
  vertices: number;
  roads: number;
  components: number;
  largest_component: number;
  independent_cycles: number;
  pairs_connected: number;
  mean_relative_error: number;
};

export type Theorem = {
  unit: number;
  name: string;
  statement: string;
  evidence: string;
  holds: boolean;
};

export type Summary = {
  area: {
    label: string;
    bbox: [number, number, number, number];
    source: string;
    license: string;
    junctions: number;
    roads: number;
    km: number;
    bridges: number;
    dead_ends: number;
    degree_counts: Record<string, number>;
  };
  occlusion: {
    gaps: number;
    patches: number;
    fragments: number;
    largest_fragment: number;
    permutation: { m: number; a: number; b: number; phi: number; family_size: number };
  };
  stages: StageRow[];
  healing: {
    mst: HealRow;
    mst_loops: HealRow;
    candidates: number;
    sweep: {
      seeds: number;
      mst_recall: { mean: number };
      full_recall: { mean: number; min: number; max: number };
      full_precision: { mean: number; min: number; max: number };
      always_connected: boolean;
      lemma_held_every_time: boolean;
    };
  };
  criticality: {
    cut_vertices: number;
    bridges: number;
    top: Gatekeeper[];
    worst_cuts: Gatekeeper[];
    top50_cut_vertices: number;
    top50_shared_with_truth: number;
  };
  stress: Record<"betweenness" | "adaptive" | "degree" | "cut_vertices" | "random", StressPoint[]>;
  percolation: {
    mean_degree: number;
    branching_factor: number;
    predicted_critical_survival: number;
    critical_survival: number;
    survival: number[];
    largest_component: number[];
  };
  counting: { pairs: number; triples: number; phi_m: number };
  theorems: Theorem[];
};

type Collection = GeoJSON.FeatureCollection;

export type Layers = {
  truth: Collection;
  roads: Collection;
  gaps: Collection;
  patches: Collection;
  junctions: Collection;
  pois: Collection;
};

export type Simulation = {
  state: StressPoint;
  base: StressPoint;
  index: { average_path: number; efficiency: number };
  components: number;
  stranded: number;
  scenarios: string;
};

export type RouteSummary = { seconds: number; metres: number; geometry: Coord[] };

export type RouteResult = {
  baseline: RouteSummary | null;
  detour: RouteSummary | null;
  disjoint: { k: number; routes: Coord[][]; cut: Coord[][] };
};

export type Overlap = {
  closures: number[];
  terms: { subset: number[]; size: number; sign: number }[];
  union: number;
  direct: number;
  sum_of_singles: number;
  trips_sampled: number;
};

export type ResponsePlan = {
  assignments: {
    site: number;
    seconds: number;
    name: string;
    kind: string;
    from: Coord;
    to: Coord;
  }[];
  unserved: number[];
  hall: { sites: number; depots: number };
  schedule: {
    days: { road: string; metres: number }[][];
    lower_bound: number;
    upper_bound: number;
  };
  budget: {
    jobs: number;
    total_hours: number;
    hours: number;
    subsets: string;
    affordable: string;
  };
  crews: { count: number; onto_assignments: string };
};

export type Inspection = {
  start: number;
  vertices: number;
  roads: number;
  sector_roads: number;
  odd_vertices: number;
  road_length_m: number;
  deadhead_m: number;
  geometry: Coord[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const get = <T,>(path: string) => request<T>(path);

export const post = <T,>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
