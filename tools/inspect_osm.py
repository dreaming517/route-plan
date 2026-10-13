"""只读统计 Geofabrik OSM PBF，生成道路标签概况。依赖：osmium。"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import osmium


class RoadInspector(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.node_count = 0
        self.way_count = 0
        self.relation_count = 0
        self.highway_way_count = 0
        self.highway_types = Counter()
        self.oneway_tags = Counter()
        self.maxspeed_tags = Counter()
        self.access_tags = Counter()
        self.motor_vehicle_tags = Counter()
        self.restriction_count = 0
        self.restriction_types = Counter()

    def node(self, node):
        self.node_count += 1

    def way(self, way):
        self.way_count += 1
        highway = way.tags.get('highway')
        if highway is None:
            return
        self.highway_way_count += 1
        self.highway_types[highway] += 1
        self.oneway_tags[way.tags.get('oneway', '<missing>')] += 1
        self.maxspeed_tags['present' if 'maxspeed' in way.tags else 'missing'] += 1
        self.access_tags[way.tags.get('access', '<missing>')] += 1
        self.motor_vehicle_tags[way.tags.get('motor_vehicle', '<missing>')] += 1

    def relation(self, relation):
        self.relation_count += 1
        if relation.tags.get('type') == 'restriction':
            self.restriction_count += 1
            self.restriction_types[relation.tags.get('restriction', '<missing>')] += 1


def ranked(c: Counter) -> dict[str, int]:
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def main():
    parser = argparse.ArgumentParser(description='Inspect OSM PBF without modifying it')
    parser.add_argument('pbf', type=Path, help='Path to input .osm.pbf')
    parser.add_argument('--output', type=Path, default=Path('data/processed/osm_inspection.json'))
    args = parser.parse_args()

    if not args.pbf.is_file():
        parser.error(f'PBF file not found: {args.pbf}')

    print(f'Reading: {args.pbf} ({args.pbf.stat().st_size / 1024**2:.2f} MiB)')
    h = RoadInspector()
    h.apply_file(str(args.pbf), locations=False)

    result = {
        'source_file': args.pbf.name,
        'source_size_bytes': args.pbf.stat().st_size,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'counts': {
            'osm_nodes': h.node_count,
            'osm_ways': h.way_count,
            'osm_relations': h.relation_count,
            'highway_tagged_ways': h.highway_way_count,
            'restriction_relations': h.restriction_count,
        },
        'highway_types': ranked(h.highway_types),
        'oneway_tags_on_highway_ways': ranked(h.oneway_tags),
        'maxspeed_presence_on_highway_ways': ranked(h.maxspeed_tags),
        'access_tags_on_highway_ways': ranked(h.access_tags),
        'motor_vehicle_tags_on_highway_ways': ranked(h.motor_vehicle_tags),
        'restriction_types': ranked(h.restriction_types),
        'notes': [
            'OSM ways are not yet routing edges; intersections and topology have not been constructed.',
            'Missing oneway does not always mean bidirectional; roundabouts and road classes need special handling.',
            'The counts include non-drivable highway categories; motor-car access filtering is a later step.',
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    print('\nCounts:')
    for key, value in result['counts'].items():
        print(f'  {key}: {value:,}')
    print('\nTop highway types:')
    for key, value in list(result['highway_types'].items())[:20]:
        print(f'  {key:<24} {value:>10,}')
    print('\nOneway tags:')
    for key, value in result['oneway_tags_on_highway_ways'].items():
        print(f'  {key:<24} {value:>10,}')
    print('\nMaxspeed tag presence:')
    for key, value in result['maxspeed_presence_on_highway_ways'].items():
        print(f'  {key:<24} {value:>10,}')
    print(f'\nSaved JSON report: {args.output}')


if __name__ == '__main__':
    main()
