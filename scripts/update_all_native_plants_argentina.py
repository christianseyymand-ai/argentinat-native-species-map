#!/usr/bin/env python3
"""
Rate-limit-safe updater for the ArgentiNat Native Species Map.

Purpose:
- Discover native/endemic plant taxa observed in Argentina via iNaturalist / ArgentiNat.
- Keep a cumulative master species list.
- Download a small number of representative observations per taxon.
- Avoid API 429 errors by processing taxa in small batches and preserving progress across runs.

Outputs:
- data/species_master_all_native_plants.csv
- data/observations_argentina_live.csv
- data/observations_argentina_live.geojson
- data/update_summary.json

Methodology note:
"All native species" here means native/endemic plant taxa that currently have iNaturalist
observations in Argentina and are returned by the iNaturalist native=true filter. This is an
observation-based public-data map, not a formal botanical checklist.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

ARGENTINA_PLACE_ID = os.getenv("ARGENTINA_PLACE_ID", "7190")
API_BASE = "https://api.inaturalist.org/v1"
USER_AGENT = os.getenv(
    "USER_AGENT",
    "argentinat-native-species-map/1.1 rate-limit-safe (open biodiversity data project; contact via GitHub)",
)

# Scope configuration
ICONIC_TAXA = os.getenv("ICONIC_TAXA", "Plantae")
NATIVE_FILTER = os.getenv("NATIVE_FILTER", "true")
QUALITY_GRADE = os.getenv("QUALITY_GRADE", "research")
HAS_GEO = os.getenv("HAS_GEO", "true")

# API-friendly defaults.
# The script is cumulative: it processes a batch each run and keeps previous observations.
PER_PAGE = int(os.getenv("PER_PAGE", "100"))
MAX_SPECIES = int(os.getenv("MAX_SPECIES", "0"))  # 0 = no cap on species discovery
MAX_OBS_PER_TAXON = int(os.getenv("MAX_OBS_PER_TAXON", "1"))
MAX_TAXA_PER_RUN = int(os.getenv("MAX_TAXA_PER_RUN", "250"))
SLEEP_SECONDS = float(os.getenv("SLEEP_SECONDS", "2.5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "45"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "6"))

ORIGINAL_SPECIES_MASTER = DATA / "species_master.csv"
SPECIES_OUT = DATA / "species_master_all_native_plants.csv"
OBS_OUT = DATA / "observations_argentina_live.csv"
GEOJSON_OUT = DATA / "observations_argentina_live.geojson"
SUMMARY_OUT = DATA / "update_summary.json"


@dataclass
class ApiResult:
    data: Dict[str, Any]
    url: str


def request_json(endpoint: str, params: Dict[str, Any], retries: int = MAX_RETRIES) -> ApiResult:
    """GET JSON from iNaturalist with respectful retry/backoff, especially for 429 rate limits."""
    url = f"{API_BASE}/{endpoint.lstrip('/')}"
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = int(retry_after)
                else:
                    wait = min(60 * attempt, 300)
                print(f"Rate limit response 429. Waiting {wait}s before retry {attempt}/{retries}...", file=sys.stderr)
                time.sleep(wait)
                continue

            if response.status_code in {500, 502, 503, 504}:
                wait = min(30 * attempt, 180)
                print(f"Temporary API response {response.status_code}. Waiting {wait}s before retry {attempt}/{retries}...", file=sys.stderr)
                time.sleep(wait)
                continue

            response.raise_for_status()
            return ApiResult(response.json(), response.url)

        except Exception as exc:
            if attempt >= retries:
                raise
            wait = min(30 * attempt, 180)
            print(f"Request failed ({exc}). Waiting {wait}s before retry {attempt}/{retries}...", file=sys.stderr)
            time.sleep(wait)

    raise RuntimeError("Unexpected request retry state")


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_original_taxon_ids() -> set[str]:
    rows = read_csv_rows(ORIGINAL_SPECIES_MASTER)
    return {str(row.get("taxon_id", "")).strip() for row in rows if row.get("taxon_id")}


def read_existing_observations() -> List[Dict[str, Any]]:
    rows = read_csv_rows(OBS_OUT)
    # Deduplicate by observation_id if present.
    seen = set()
    unique = []
    for row in rows:
        oid = str(row.get("observation_id", "")).strip()
        key = oid or json.dumps(row, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def fetch_native_plant_species_counts() -> Tuple[List[Dict[str, Any]], int, str]:
    """Discover native/endemic plant taxa observed in Argentina."""
    all_results: List[Dict[str, Any]] = []
    page = 1
    total_results = 0
    first_url = ""

    while True:
        params: Dict[str, Any] = {
            "place_id": ARGENTINA_PLACE_ID,
            "native": NATIVE_FILTER,
            "iconic_taxa": ICONIC_TAXA,
            "quality_grade": QUALITY_GRADE,
            "per_page": PER_PAGE,
            "page": page,
        }
        if HAS_GEO == "true":
            params["has[]"] = "geo"

        result = request_json("observations/species_counts", params)
        if not first_url:
            first_url = result.url
        data = result.data
        total_results = int(data.get("total_results") or 0)
        batch = data.get("results") or []

        if not batch:
            break

        all_results.extend(batch)
        print(f"Fetched species page {page}: {len(batch)} records; cumulative={len(all_results)} / total={total_results}")

        if MAX_SPECIES and len(all_results) >= MAX_SPECIES:
            all_results = all_results[:MAX_SPECIES]
            break

        if len(batch) < PER_PAGE or len(all_results) >= total_results:
            break

        page += 1
        time.sleep(SLEEP_SECONDS)

    return all_results, total_results, first_url


def flatten_species_count(item: Dict[str, Any], original_taxon_ids: set[str], updated_at: str) -> Dict[str, Any]:
    taxon = item.get("taxon") or {}
    conservation_status = taxon.get("conservation_status") or {}
    ancestry = taxon.get("ancestry") or ""
    taxon_id = str(taxon.get("id") or item.get("taxon_id") or "")
    return {
        "taxon_id": taxon_id,
        "scientific_name": taxon.get("name") or "",
        "preferred_common_name": taxon.get("preferred_common_name") or "",
        "rank": taxon.get("rank") or "",
        "iconic_taxon_name": taxon.get("iconic_taxon_name") or "",
        "observations_argentina_count": item.get("count") or item.get("observation_count") or "",
        "representative_observations_downloaded": "0",
        "inat_taxon_url": f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else "",
        "inat_observations_argentina_url": f"https://www.inaturalist.org/observations?place_id={ARGENTINA_PLACE_ID}&taxon_id={taxon_id}&native=true" if taxon_id else "",
        "conservation_status": conservation_status.get("status") or "",
        "conservation_authority": conservation_status.get("authority") or "",
        "ancestor_taxon_ids": ancestry,
        "in_original_kml_map": "yes" if taxon_id in original_taxon_ids else "no",
        "source": "iNaturalist / ArgentiNat API: observations/species_counts native=true",
        "argentina_place_id": ARGENTINA_PLACE_ID,
        "native_filter": NATIVE_FILTER,
        "quality_grade_filter": QUALITY_GRADE,
        "last_api_update_utc": updated_at,
        "notes": "Observation-based native/endemic status from iNaturalist establishment means. Validate formal taxonomy against Flora Argentina/Darwinion when needed.",
    }


def flatten_observation(obs: Dict[str, Any]) -> Dict[str, Any]:
    taxon = obs.get("taxon") or {}
    photos = obs.get("photos") or []
    photo_url = ""
    if photos:
        photo_url = (photos[0].get("url") or "").replace("square", "medium")

    geo = obs.get("geojson") or {}
    coords = geo.get("coordinates") or [None, None]
    if isinstance(coords, list) and len(coords) >= 2:
        lon, lat = coords[0], coords[1]
    else:
        lon, lat = None, None

    return {
        "observation_id": obs.get("id"),
        "observed_on": obs.get("observed_on"),
        "created_at": obs.get("created_at"),
        "quality_grade": obs.get("quality_grade"),
        "place_guess": obs.get("place_guess"),
        "latitude": lat,
        "longitude": lon,
        "taxon_id": taxon.get("id"),
        "scientific_name": taxon.get("name"),
        "preferred_common_name": taxon.get("preferred_common_name"),
        "rank": taxon.get("rank"),
        "iconic_taxon_name": taxon.get("iconic_taxon_name"),
        "observer_login": (obs.get("user") or {}).get("login"),
        "uri": obs.get("uri"),
        "photo_url": photo_url,
        "source": "iNaturalist / ArgentiNat API: observations",
    }


def fetch_representative_observations(taxon_id: str) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch a very small number of recent georeferenced observations per taxon for map display."""
    if not taxon_id:
        return [], ""
    params: Dict[str, Any] = {
        "place_id": ARGENTINA_PLACE_ID,
        "taxon_id": taxon_id,
        "native": NATIVE_FILTER,
        "quality_grade": QUALITY_GRADE,
        "per_page": min(PER_PAGE, MAX_OBS_PER_TAXON),
        "page": 1,
        "order_by": "observed_on",
        "order": "desc",
    }
    if HAS_GEO == "true":
        params["has[]"] = "geo"

    result = request_json("observations", params)
    observations = [flatten_observation(o) for o in (result.data.get("results") or [])]
    return observations[:MAX_OBS_PER_TAXON], result.url


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def write_geojson(path: Path, rows: Iterable[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    features = []
    for row in rows:
        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat in (None, "") or lon in (None, ""):
            continue
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        props = {k: v for k, v in row.items() if k not in {"latitude", "longitude"}}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon_f, lat_f]},
            "properties": props,
        })
    geojson = {
        "type": "FeatureCollection",
        "metadata": summary,
        "features": features,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    original_taxon_ids = read_original_taxon_ids()

    print("Discovering native/endemic plant taxa observed in Argentina from iNaturalist / ArgentiNat...")
    species_counts, total_available, species_counts_url = fetch_native_plant_species_counts()
    species_rows = [flatten_species_count(item, original_taxon_ids, updated_at) for item in species_counts]

    existing_observations = read_existing_observations()
    existing_taxon_ids = {str(row.get("taxon_id", "")).strip() for row in existing_observations if row.get("taxon_id")}

    for species in species_rows:
        taxon_id = str(species.get("taxon_id", "")).strip()
        if taxon_id in existing_taxon_ids:
            species["representative_observations_downloaded"] = "already_downloaded"

    taxa_to_process = [s for s in species_rows if str(s.get("taxon_id", "")).strip() and str(s.get("taxon_id", "")).strip() not in existing_taxon_ids]
    taxa_this_run = taxa_to_process[:MAX_TAXA_PER_RUN]

    all_observations: List[Dict[str, Any]] = list(existing_observations)
    observation_example_url = ""

    print(f"Existing taxa with observations: {len(existing_taxon_ids)}")
    print(f"Taxa remaining without representative observations: {len(taxa_to_process)}")
    print(f"Taxa selected for this run: {len(taxa_this_run)}")

    for idx, species in enumerate(taxa_this_run, 1):
        taxon_id = str(species.get("taxon_id", "")).strip()
        sci = species.get("scientific_name")
        print(f"[{idx}/{len(taxa_this_run)}] Fetching representative observations for {sci} / taxon_id={taxon_id}")
        try:
            obs, obs_url = fetch_representative_observations(taxon_id)
            if obs_url and not observation_example_url:
                observation_example_url = obs_url
            all_observations.extend(obs)
            species["representative_observations_downloaded"] = str(len(obs))
        except Exception as exc:
            print(f"Observation fetch failed for {sci} ({taxon_id}): {exc}", file=sys.stderr)
            species["representative_observations_downloaded"] = "0"
            species["notes"] = f"{species.get('notes','')} Observation fetch failed: {exc}".strip()
        time.sleep(SLEEP_SECONDS)

    # Deduplicate observations after this run.
    deduped_observations = []
    seen_obs = set()
    for row in all_observations:
        oid = str(row.get("observation_id", "")).strip()
        key = oid or json.dumps(row, sort_keys=True)
        if key in seen_obs:
            continue
        seen_obs.add(key)
        deduped_observations.append(row)

    species_fields = [
        "taxon_id", "scientific_name", "preferred_common_name", "rank", "iconic_taxon_name",
        "observations_argentina_count", "representative_observations_downloaded", "inat_taxon_url",
        "inat_observations_argentina_url", "conservation_status", "conservation_authority",
        "ancestor_taxon_ids", "in_original_kml_map", "source", "argentina_place_id", "native_filter",
        "quality_grade_filter", "last_api_update_utc", "notes",
    ]
    obs_fields = [
        "observation_id", "observed_on", "created_at", "quality_grade", "place_guess",
        "latitude", "longitude", "taxon_id", "scientific_name", "preferred_common_name",
        "rank", "iconic_taxon_name", "observer_login", "uri", "photo_url", "source",
    ]

    processed_taxa_after_run = {str(row.get("taxon_id", "")).strip() for row in deduped_observations if row.get("taxon_id")}
    remaining_after_run = max(0, len(species_rows) - len(processed_taxa_after_run))

    summary = {
        "updated_at_utc": updated_at,
        "place_id": ARGENTINA_PLACE_ID,
        "place_name": "Argentina",
        "scope": "Native/endemic Plantae taxa observed in Argentina on iNaturalist / ArgentiNat",
        "method": "observations/species_counts native=true + cumulative representative observations per taxon",
        "quality_grade": QUALITY_GRADE,
        "species_available_from_api": total_available,
        "species_written": len(species_rows),
        "observations_written": len(deduped_observations),
        "taxa_with_representative_observations": len(processed_taxa_after_run),
        "taxa_remaining_without_representative_observations": remaining_after_run,
        "max_species": MAX_SPECIES,
        "max_taxa_per_run": MAX_TAXA_PER_RUN,
        "max_observations_per_taxon": MAX_OBS_PER_TAXON,
        "sleep_seconds": SLEEP_SECONDS,
        "species_counts_api_url_example": species_counts_url,
        "observations_api_url_example": observation_example_url,
        "methodology_note": "This is observation-based, not a complete formal botanical checklist. Native/endemic status depends on iNaturalist establishment means. For formal vascular plant taxonomy, validate against Flora Argentina / Darwinion.",
    }

    write_csv(SPECIES_OUT, species_rows, species_fields)
    write_csv(OBS_OUT, deduped_observations, obs_fields)
    write_geojson(GEOJSON_OUT, deduped_observations, summary)
    SUMMARY_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
