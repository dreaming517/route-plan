# Local OSM data

The browser first tries to load `wuhan-main-roads.json` from this directory.
The checked-in file is a small real extract around central Wuhan. It contains
only major OSM roads, not POIs or a full-city dump.

To download a fresh small extract, run from the project directory:

```text
python tools/download_osm_network.py
```

The script first uses the official OSM map API for the small bounding box and
then falls back to Overpass. The extract uses the same Wuhan bounding box and
main-road filter as the web page. If the local file is absent, the page falls
back to the Overpass API.

The data comes from OpenStreetMap and is distributed under the Open Database
License (ODbL). Keep the source, date, bounding box, and attribution metadata
with any redistributed copy.
