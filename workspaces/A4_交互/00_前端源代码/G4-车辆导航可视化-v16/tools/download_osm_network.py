"""Download the small OSM road extract used by the web demo."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BBOX = "30.496,114.396,30.516,114.416"
MAP_BBOX = "114.396,30.496,114.416,30.516"
HIGHWAY_PATTERN = (
    "motorway|motorway_link|trunk|trunk_link|primary|primary_link|"
    "secondary|secondary_link|tertiary|tertiary_link"
)
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OSM_MAP_ENDPOINT = "https://api.openstreetmap.org/api/0.6/map"


def query() -> str:
    return (
        '[out:json][timeout:45];'
        f'way["highway"~"^({HIGHWAY_PATTERN})$"]({BBOX});'
        "out body geom;"
    )


def parse_osm_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    allowed_nodes = set()
    ways = []
    for way in root.findall("way"):
        tags = {tag.get("k"): tag.get("v") for tag in way.findall("tag")}
        if tags.get("highway") not in HIGHWAY_PATTERN.split("|"):
            continue
        refs = [node.get("ref") for node in way.findall("nd") if node.get("ref")]
        if len(refs) < 2:
            continue
        allowed_nodes.update(refs)
        ways.append({
            "type": "way",
            "id": int(way.get("id")),
            "nodes": [int(ref) for ref in refs],
            "tags": tags,
        })
    elements = [
        {
            "type": "node",
            "id": int(node.get("id")),
            "lat": float(node.get("lat")),
            "lon": float(node.get("lon")),
        }
        for node in root.findall("node")
        if node.get("id") in allowed_nodes
    ]
    elements.extend(ways)
    if len(ways) < 20 or len(elements) < 40:
        raise RuntimeError("The OSM response contains too few main-road elements")
    return {"version": 0.6, "elements": elements}


def download_from_official_api() -> dict:
    request = Request(
        f"{OSM_MAP_ENDPOINT}?bbox={MAP_BBOX}",
        headers={
            "Accept": "application/xml",
            "User-Agent": "G4-vehicle-navigation/1.0",
        },
    )
    with urlopen(request, timeout=60) as response:
        return parse_osm_xml(response.read().decode("utf-8"))


def download_from_overpass() -> dict:
    body = urlencode({"data": query()}).encode("utf-8")
    last_error = None
    for endpoint in ENDPOINTS:
        try:
            request = Request(
                endpoint,
                data=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "G4-vehicle-navigation/1.0",
                },
                method="POST",
            )
            with urlopen(request, timeout=120) as response:
                payload = json.load(response)
            if len(payload.get("elements", [])) < 20:
                raise RuntimeError("The OSM response contains too few elements")
            return payload
        except Exception as error:  # Try the next public endpoint.
            last_error = error
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")


def download() -> dict:
    errors = []
    for source_name, source in (
        ("OpenStreetMap official map API", download_from_official_api),
        ("OpenStreetMap via Overpass API", download_from_overpass),
    ):
        try:
            return source(), source_name
        except Exception as error:  # Try the next public endpoint.
            errors.append(str(error))
    raise RuntimeError("All OSM download sources failed: " + " | ".join(errors))


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    payload, source = download()
    payload["g4_metadata"] = {
        "source": source,
        "bbox": BBOX,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "license": "ODbL 1.0",
        "attribution": "© OpenStreetMap contributors",
    }
    output = data_dir / "wuhan-main-roads.json"
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(payload['elements'])} OSM elements to {output}")


if __name__ == "__main__":
    main()
