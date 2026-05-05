# ArgentiNat Native Species Map

Interactive biodiversity map and auto-updating database of native plant observations in Argentina using ArgentiNat / iNaturalist data.

## Live Map

View the interactive map here:

https://christianseymand-ai.github.io/argentinat-native-species-map/map/

## What this project does

This project creates a public map for exploring native plant observations in Argentina. It is designed for people interested in native species identification, cultivation, restoration, landscaping, environmental education, and biodiversity data.

The project includes:

- Public interactive web map
- GeoJSON data for mapping
- CSV observation database
- Python update script
- GitHub Actions workflow for automatic updates
- GitHub Pages deployment

## Practical uses

The map can help users:

- Locate native species across Argentina
- See which species grow nearby
- Find references for native seeds or plants responsibly
- Support restoration or environmental education projects
- Explore open biodiversity data

## Project structure

```text
argentinat-native-species-map/
  data/
    observations_argentina_live.csv
    observations_argentina_live.geojson
    species_master_all_native_plants.csv
    update_summary.json
  map/
    index.html
  scripts/
    update_all_native_plants_argentina.py
  .github/
    workflows/
      update-all-native-plants.yml
  index.html
  README.md
  requirements.txt
```

## Methodology note

"All native species" in this project means native or endemic plant taxa that currently have observations in Argentina returned by the iNaturalist / ArgentiNat API using the native=true filter. This is an observation-based public data map, not a formal botanical checklist.

For formal taxonomy and conservation work, species should be validated against specialized botanical sources such as Flora Argentina / Darwinion and other official biodiversity databases.

## Tools

Python, GeoJSON, iNaturalist API, GitHub Pages, GitHub Actions.
