# Native Plants Argentina Map

Interactive web map of georeferenced observations of native and endemic plants in Argentina, based on research-grade iNaturalist / ArgentiNat records.

The project automatically downloads biodiversity observation data, processes it into CSV and GeoJSON files, and publishes an interactive Leaflet map through GitHub Pages.

## Live Map

Open the published GitHub Pages site for this repository to view the map.

## What the Map Shows

This map displays georeferenced observations of plant taxa marked as native or endemic in Argentina on iNaturalist / ArgentiNat.

The dataset includes:

- Native/endemic Plantae taxa observed in Argentina
- Research-grade observations
- Observations with geographic coordinates
- Scientific names
- Common names when available
- Observation dates
- iNaturalist observation links
- Photos when available

## Data Source

Data is retrieved from the public iNaturalist API.

Main API endpoints used:

- `observations/species_counts`
- `observations`

The current scope is:

```text
Native/endemic Plantae taxa observed in Argentina on iNaturalist / ArgentiNat
