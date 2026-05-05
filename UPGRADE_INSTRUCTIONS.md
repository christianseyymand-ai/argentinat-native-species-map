# Upgrade: All Native Plants Argentina

This upgrade changes the map from a curated KML-derived species list to a broader, auto-updating biodiversity map.

## Files to add/replace

1. Add:

```text
scripts/update_all_native_plants_argentina.py
.github/workflows/update-all-native-plants.yml
```

2. Replace:

```text
map/index.html
```

## What it does

The new script discovers native/endemic plant taxa observed in Argentina through the iNaturalist / ArgentiNat API using:

```text
place_id=7190
native=true
iconic_taxa=Plantae
quality_grade=research
has[]=geo
```

Then it downloads representative observations for each taxon and writes:

```text
data/species_master_all_native_plants.csv
data/observations_argentina_live.csv
data/observations_argentina_live.geojson
data/update_summary.json
```

## GitHub Actions

After committing the workflow, go to:

```text
Actions → Update All Native Plants Argentina → Run workflow
```

If it finishes green, your map will update automatically every Monday.

## Performance controls

The workflow currently uses:

```text
MAX_OBS_PER_TAXON=5
QUALITY_GRADE=research
```

This keeps the map useful without making the GeoJSON too heavy.

## Methodology note

This does not mean every native plant ever recorded in Flora Argentina. It means all native/endemic plant taxa that currently have iNaturalist / ArgentiNat observations in Argentina and are returned by the native=true filter.

For formal botanical completeness, validate the species master list against Flora Argentina / Darwinion.
