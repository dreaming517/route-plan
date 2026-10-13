"""Validate a converted OSM GraphML using the existing path_planning engine.

Run from the repository root:
  python tools/validate_dc_network.py
No existing project files or routing data are modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from path_planning.osm_loader import load_graphml
from path_planning.costs import CostModel, Preference
from path_planning.router import NoRouteError, plan_route
from path_planning.geo import haversine_m


def components(vertices, forward, backward=None):
    """Iterative weak components (backward=None) or Kosaraju SCCs."""
    if backward is None:
        seen = set()
        groups = []
        for origin in vertices:
            if origin in seen:
                continue
            seen.add(origin)
            stack = [origin]
            group = []
            while stack:
                u = stack.pop()
                group.append(u)
                for v in forward[u]:
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            groups.append(group)
        groups.sort(key=len, reverse=True)
        return groups

    seen = set()
    finish = []
    for root in vertices:
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, 0)]
        while stack:
            u, i = stack[-1]
            neighbors = forward[u]
            if i == len(neighbors):
                finish.append(u)
                stack.pop()
                continue
            stack[-1] = (u, i + 1)
            v = neighbors[i]
            if v not in seen:
                seen.add(v)
                stack.append((v, 0))
    seen.clear()
    groups = []
    for root in reversed(finish):
        if root in seen:
            continue
        seen.add(root)
        stack = [root]
        group = []
        while stack:
            u = stack.pop()
            group.append(u)
            for v in backward[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        groups.append(group)
    groups.sort(key=len, reverse=True)
    return groups


def choose_pair(graph, group):
    """Deterministic, spatially separated points within the same SCC."""
    a = min(group, key=lambda n: (graph.nodes[n].lon, n))
    p = graph.nodes[a]
    b = max(group, key=lambda n: haversine_m((p.lon, p.lat), (graph.nodes[n].lon, graph.nodes[n].lat)))
    return a, b


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/processed/dc_driving.graphml')
    parser.add_argument('--output', default='data/processed/dc_validation.json')
    parser.add_argument('--max-checks', type=int, default=2, help='Number of test pairs in largest SCC; default 2')
    args = parser.parse_args()
    path = ROOT / args.input
    if not path.is_file():
        parser.error(f'GraphML not found: {path}')
    print('Loading:', path, flush=True)
    t0 = perf_counter()
    graph = load_graphml(path)
    load_s = perf_counter() - t0
    print(f'Loaded {len(graph.nodes):,} nodes, {len(graph.edges):,} directed edges in {load_s:.2f}s', flush=True)

    adjacency = {n: [] for n in graph.nodes}
    reverse = {n: [] for n in graph.nodes}
    undirected = {n: [] for n in graph.nodes}
    invalid_coords = []
    for node in graph.nodes.values():
        if not (-180 <= node.lon <= 180 and -90 <= node.lat <= 90 and math.isfinite(node.lon) and math.isfinite(node.lat)):
            invalid_coords.append(node.node_id)
    invalid_coords_set = set(invalid_coords)
    length_invalid = []
    speed_invalid = []
    shorter_than_straight = []
    speeds = []
    types = Counter()
    for edge in graph.edges.values():
        u, v = edge.from_node, edge.to_node
        adjacency[u].append(v)
        reverse[v].append(u)
        undirected[u].append(v)
        undirected[v].append(u)
        types[edge.road_type] += 1
        if not math.isfinite(edge.length_m) or edge.length_m <= 0:
            length_invalid.append(edge.edge_id)
        if not math.isfinite(edge.speed_kmh) or edge.speed_kmh <= 0:
            speed_invalid.append(edge.edge_id)
        speeds.append(edge.speed_kmh)
        if u not in invalid_coords_set and v not in invalid_coords_set:
            a, b = graph.nodes[u], graph.nodes[v]
            straight = haversine_m((a.lon, a.lat), (b.lon, b.lat))
            if edge.length_m + max(0.1, straight * 0.0001) < straight:
                shorter_than_straight.append(edge.edge_id)
    print('Computing weak/strong components...', flush=True)
    weak = components(graph.nodes, undirected)
    strong = components(graph.nodes, adjacency, reverse)
    isolated = sum(1 for n in graph.nodes if not undirected[n])
    print(f'Weak components: {len(weak):,}; largest: {len(weak[0]):,}', flush=True)
    print(f'Strong components: {len(strong):,}; largest: {len(strong[0]):,}', flush=True)
    print(f'Isolated nodes: {isolated:,}; suspicious short edges: {len(shorter_than_straight):,}', flush=True)
    max_speed = max(speeds) if speeds else 0
    # At least maximum observed speed for a valid time lower bound.
    chosen_speed = max(130.0, max_speed)
    print(f'Speed max: {max_speed:.1f} km/h, time heuristic bound: {chosen_speed:.1f} km/h', flush=True)
    report = {
        'input': str(path), 'generated_utc': datetime.now(timezone.utc).isoformat(),
        'load_seconds': round(load_s, 3), 'node_count': len(graph.nodes), 'edge_count': len(graph.edges),
        'connected': {
            'isolated_nodes': isolated,
            'weak_component_count': len(weak), 'weak_largest_nodes': len(weak[0]),
            'weak_largest_fraction': len(weak[0]) / max(1, len(graph.nodes)),
            'strong_component_count': len(strong), 'strong_largest_nodes': len(strong[0]),
            'strong_largest_fraction': len(strong[0]) / max(1, len(graph.nodes)),
        },
        'edge_checks': {
            'invalid_node_coordinates_count': len(invalid_coords),
            'non_positive_or_nonfinite_length_count': len(length_invalid),
            'non_positive_or_nonfinite_speed_count': len(speed_invalid),
            'shorter_than_straight_count_with_tolerance': len(shorter_than_straight),
            'speed_kmh_max': max_speed,
            'speed_kmh_median': median(speeds) if speeds else None,
            'road_types_directed_edges': dict(types.most_common()),
            'example_short_edges': shorter_than_straight[:10]
        },
        'route_tests': [],
        'limitations': [
            'Turn restrictions from OSM relations are not yet loaded.',
            'Conditional access and detailed traffic rules are simplified.',
            'All paths are on the converted graph, not a traffic-legal proof.'
        ]
    }
    if len(strong[0]) > 1 and args.max_checks > 0:
        largest = strong[0]
        a, b = choose_pair(graph, largest)
        pairs = [(a, b)]
        if args.max_checks >= 2:
            pairs.append((b, a))
        for i, (src, dst) in enumerate(pairs, 1):
            for pref in (Preference.SHORTEST, Preference.FASTEST):
                model = CostModel(preference=pref, max_speed_kmh=chosen_speed)
                results = {}
                for algorithm in ('dijkstra', 'astar'):
                    print(f'Routing pair {i}/{len(pairs)} {src}->{dst} {pref.value} {algorithm}...', flush=True)
                    try:
                        r = plan_route(graph, src, dst, algorithm=algorithm, cost_model=model)
                        results[algorithm] = {
                            'status': 'ok', 'cost': r.cost, 'distance_m': r.distance_m,
                            'duration_s': r.duration_s, 'expanded_states': r.expanded_states,
                            'queue_pushes': r.queue_pushes, 'planning_ms': r.planning_ms,
                            'path_node_count': len(r.node_ids), 'path_edge_count': len(r.edge_ids)
                        }
                    except (NoRouteError, ValueError) as e:
                        results[algorithm] = {'status': 'error', 'message': str(e)}
                x, y = results['dijkstra'], results['astar']
                agree = (x['status'] == y['status'] == 'ok' and math.isclose(x['cost'], y['cost'], rel_tol=1e-8, abs_tol=1e-5))
                print('  Equal optimal cost:', agree, flush=True)
                report['route_tests'].append({'source': src, 'target': dst, 'preference': pref.value,
                                              'dijkstra': x, 'astar': y, 'costs_agree': agree})
    else:
        print('Skipping routing: no suitable strongly connected component or max-checks=0', flush=True)
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Report saved:', out, flush=True)
    print('RESULT:', 'CHECK WARNINGS/FAILURES' if (
        invalid_coords or length_invalid or speed_invalid or shorter_than_straight or
        any(not r['costs_agree'] for r in report['route_tests'])
    ) else 'BASIC CHECKS PASSED', flush=True)


if __name__ == '__main__':
    main()
