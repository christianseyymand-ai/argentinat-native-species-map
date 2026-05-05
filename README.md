# Native Plants Argentina Map

Interactive web map of georeferenced observations of native and endemic plants in Argentina, based on research-grade iNaturalist / ArgentiNat records.

The project automatically downloads biodiversity observation data, processes it into CSV and GeoJSON files, and publishes an interactive Leaflet map through GitHub Pages.

## Live Map

Open the published GitHub Pages site for this repository to view the map.

## What the Map Shows

This map displays georeferenced observations of plant taxa marked as native or endemic in Argentina on iNaturalist / ArgentiNat.

The dataset includes native/endemic Plantae taxa observed in Argentina, research-grade observations, geographic coordinates, scientific names, common names when available, observation dates, iNaturalist observation links, and photos when available.

## Data Source

Data is retrieved from the public iNaturalist API.

Main API endpoints used:

- `observations/species_counts`
- `observations`

Current scope:

```text
Native/endemic Plantae taxa observed in Argentina on iNaturalist / ArgentiNat
```

Important note: this is an observation-based dataset. It is not a complete formal botanical checklist. Native/endemic status depends on iNaturalist establishment means. For formal vascular plant taxonomy, records should be validated against sources such as Flora Argentina / Darwinion.

## How It Works

The project uses a GitHub Actions workflow to update the dataset automatically.

The workflow fetches native/endemic plant taxa observed in Argentina, downloads georeferenced research-grade observations for each taxon, writes a master species CSV, writes a full observations CSV, generates a lightweight overview GeoJSON for fast initial map loading, splits the full GeoJSON dataset into spatial tiles, writes a tile manifest used by the frontend map, and commits the updated data back to the repository.

## Repository Structure

```text
.
├── index.html
├── requirements.txt
├── scripts/
│   └── update_all_native_plants_argentina.py
├── data/
│   ├── species_master_all_native_plants.csv
│   ├── observations_argentina_live.csv
│   ├── observations_argentina_live.geojson
│   ├── geojson_overview.geojson
│   ├── geojson_tile_manifest.json
│   ├── update_summary.json
│   ├── update_progress.json
│   └── geojson_tiles/
│       ├── tile_lat_..._lon_....geojson
│       └── ...
└── .github/
    └── workflows/
        └── update-all-native-plants.yml
```

## Main Files

### `index.html`

Frontend map built with Leaflet.

The map loads quickly by first displaying:

```text
data/geojson_overview.geojson
```

When the user zooms in, the map loads detailed spatial tiles from:

```text
data/geojson_tiles/
```

using:

```text
data/geojson_tile_manifest.json
```

This avoids loading the full dataset at once and keeps the map usable even with hundreds of thousands of observations.

### `scripts/update_all_native_plants_argentina.py`

Python script that downloads and processes the data from iNaturalist.

It creates:

```text
data/species_master_all_native_plants.csv
data/observations_argentina_live.csv
data/geojson_overview.geojson
data/geojson_tile_manifest.json
data/geojson_tiles/*.geojson
data/update_summary.json
data/update_progress.json
```

### `.github/workflows/update-all-native-plants.yml`

GitHub Actions workflow that runs the update script and commits the generated data files.

It can be triggered manually from the Actions tab or automatically by schedule.

## Data Files

### `species_master_all_native_plants.csv`

List of plant taxa discovered through the iNaturalist species counts endpoint.

Includes taxon ID, scientific name, common name when available, rank, iconic taxon, and observation count.

### `observations_argentina_live.csv`

Full observations table.

Includes observation ID, taxon ID, scientific name, common name, observation date, latitude, longitude, place guess, observer username, photo URL, and iNaturalist URL.

### `observations_argentina_live.geojson`

Small compatibility placeholder.

The full dataset is not stored in this single file because the complete GeoJSON can exceed GitHub file size limits. The frontend should use the overview and spatial tile files instead.

### `geojson_overview.geojson`

Lightweight sample used for fast initial map rendering.

This file allows the map to show an immediate national overview without loading the full dataset.

### `geojson_tile_manifest.json`

Index of all spatial GeoJSON tiles.

The frontend uses this file to know which tile files exist and which areas they cover.

### `geojson_tiles/*.geojson`

Detailed spatial tiles.

These files contain the full observation points divided by geographic grid cells so the browser only loads the data needed for the visible map area.

### `update_summary.json`

Summary of the latest update, including update timestamp, number of species written, number of observations written, number of taxa processed, number of spatial tiles, and methodology note.

### `update_progress.json`

Progress metadata from the latest workflow run.

## Updating the Dataset

To update the dataset manually:

1. Go to the repository on GitHub.
2. Open the **Actions** tab.
3. Select **Update All Native Plants Argentina**.
4. Click **Run workflow**.
5. Select branch `main`.
6. Wait for the workflow to finish.
7. Wait for GitHub Pages deployment to finish.
8. Open the map and hard refresh the browser.

On Windows/Linux:

```text
Ctrl + Shift + R
```

On Mac:

```text
Cmd + Shift + R
```

## Automatic Updates

The workflow is scheduled to run every Monday at 09:00 UTC:

```yaml
cron: "0 9 * * 1"
```

## Local Development

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the data update script:

```bash
python scripts/update_all_native_plants_argentina.py
```

Serve the site locally:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

## Requirements

The Python script requires:

```text
requests
```

## Performance Notes

The full dataset can contain hundreds of thousands of observations. Loading all points at once can be slow in a browser.

To improve performance, the map uses a lightweight overview GeoJSON for initial loading, spatial GeoJSON tiles for detailed loading, lazy loading based on the visible map area, and Leaflet canvas rendering.

Users can see the general distribution immediately, then zoom in to load complete observations for a specific area.

## Limitations

This project depends on the availability and structure of the iNaturalist API.

The dataset may not represent the full botanical diversity of Argentina because it only includes observations that are present on iNaturalist / ArgentiNat, marked as native/endemic through iNaturalist establishment means, research grade, and georeferenced.

Taxonomic and establishment status should be reviewed before using the dataset for formal scientific, legal, or conservation decisions.

## Credits

Data: iNaturalist / ArgentiNat  
Map: Leaflet and OpenStreetMap  
Project: Christian Seymand
