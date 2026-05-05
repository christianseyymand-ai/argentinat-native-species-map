import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


# ============================================================
# CONFIG
# ============================================================

PLACE_ID = "7190"  # Argentina
PLACE_NAME = "Argentina"

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SPECIES_MASTER_CSV = DATA_DIR / "species_master_all_native_plants.csv"
OBSERVATIONS_CSV = DATA_DIR / "observations_argentina_live.csv"

# Este archivo queda chico, solo como compatibilidad.
OBSERVATIONS_GEOJSON = DATA_DIR / "observations_argentina_live.geojson"

# Dataset grande dividido en partes para no superar el límite de GitHub.
GEOJSON_CHUNKS_DIR = DATA_DIR / "geojson_chunks"
GEOJSON_MANIFEST = DATA_DIR / "geojson_manifest.json"

UPDATE_SUMMARY_JSON = DATA_DIR / "update_summary.json"
UPDATE_PROGRESS_JSON = DATA_DIR / "update_progress.json"

INAT_BASE_URL = "https://api.inaturalist.org/v1"

# 0 = sin límite
MAX_SPECIES = 0

# 0 = procesar todas las especies/taxones encontrados
MAX_TAXA_PER_RUN = 0

# 0 = traer todas las observaciones disponibles por taxón
MAX_OBSERVATIONS_PER_TAXON = 0

SPECIES_PER_PAGE = 100
OBSERVATIONS_PER_PAGE = 200

# Cantidad de observaciones por archivo .geojson.
# 25000 mantiene cada archivo por debajo del límite de 100 MB de GitHub.
GEOJSON_CHUNK_SIZE = 25000

# Pausa entre requests. 1.0 es razonable.
SLEEP_SECONDS = 1.0

QUALITY_GRADE = "research"


# ============================================================
# HELPERS
# ============================================================

def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_json(url, params=None, retries=5):
    params = params or {}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=60)

            if response.status_code == 429:
                wait = 20 * attempt
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except Exception as exc:
            wait = 10 * attempt
            print(f"Request failed attempt {attempt}/{retries}: {exc}")

            if attempt == retries:
                raise

            time.sleep(wait)

    raise RuntimeError("Failed request after retries")


def safe_get(dct, path, default=""):
    cur = dct

    for key in path:
        if not isinstance(cur, dict):
            return default

        cur = cur.get(key)

        if cur is None:
            return default

    return cur


# ============================================================
# SPECIES DISCOVERY
# ============================================================

def fetch_native_plant_taxa():
    print("Discovering native/endemic plant taxa observed in Argentina from iNaturalist / ArgentiNat...")

    taxa = []
    page = 1
    total_results = None

    while True:
        params = {
            "place_id": PLACE_ID,
            "native": "true",
            "iconic_taxa": "Plantae",
            "quality_grade": QUALITY_GRADE,
            "per_page": SPECIES_PER_PAGE,
            "page": page,
            "has[]": "geo",
        }

        data = get_json(f"{INAT_BASE_URL}/observations/species_counts", params=params)

        results = data.get("results", [])
        total_results = data.get("total_results", total_results)

        if not results:
            break

        for item in results:
            taxon = item.get("taxon", {}) or {}
            taxon_id = taxon.get("id")

            if not taxon_id:
                continue

            taxa.append({
                "taxon_id": taxon_id,
                "name": taxon.get("name", ""),
                "preferred_common_name": taxon.get("preferred_common_name", ""),
                "rank": taxon.get("rank", ""),
                "iconic_taxon_name": taxon.get("iconic_taxon_name", ""),
                "observations_count": item.get("count", 0),
            })

            if MAX_SPECIES and len(taxa) >= MAX_SPECIES:
                break

        print(
            f"Fetched species page {page}: {len(results)} records; "
            f"cumulative={len(taxa)} / total={total_results}"
        )

        if MAX_SPECIES and len(taxa) >= MAX_SPECIES:
            break

        if total_results is not None and len(taxa) >= total_results:
            break

        page += 1
        time.sleep(SLEEP_SECONDS)

    return taxa


# ============================================================
# OBSERVATIONS
# ============================================================

def fetch_observations_for_taxon(taxon):
    taxon_id = taxon["taxon_id"]
    taxon_name = taxon.get("name", "")

    observations = []
    page = 1

    while True:
        params = {
            "place_id": PLACE_ID,
            "taxon_id": taxon_id,
            "native": "true",
            "quality_grade": QUALITY_GRADE,
            "per_page": OBSERVATIONS_PER_PAGE,
            "page": page,
            "order_by": "observed_on",
            "order": "desc",
            "has[]": "geo",
        }

        data = get_json(f"{INAT_BASE_URL}/observations", params=params)
        results = data.get("results", [])

        if not results:
            break

        for obs in results:
            geojson = obs.get("geojson") or {}
            coordinates = geojson.get("coordinates") or []

            if not coordinates or len(coordinates) < 2:
                continue

            longitude, latitude = coordinates[0], coordinates[1]

            if latitude is None or longitude is None:
                continue

            observation_id = obs.get("id")

            if not observation_id:
                continue

            observed_taxon = obs.get("taxon", {}) or {}
            user = obs.get("user", {}) or {}

            photos = obs.get("photos") or []
            photo_url = ""

            if photos:
                photo_url = safe_get(photos[0], ["url"], "")

                if photo_url:
                    photo_url = photo_url.replace("square", "medium")

            observation = {
                "observation_id": str(observation_id),
                "taxon_id": str(taxon_id),
                "scientific_name": observed_taxon.get("name", taxon_name),
                "common_name": observed_taxon.get(
                    "preferred_common_name",
                    taxon.get("preferred_common_name", "")
                ),
                "rank": observed_taxon.get("rank", taxon.get("rank", "")),
                "observed_on": obs.get("observed_on", ""),
                "created_at": obs.get("created_at", ""),
                "quality_grade": obs.get("quality_grade", ""),
                "latitude": latitude,
                "longitude": longitude,
                "place_guess": obs.get("place_guess", ""),
                "uri": obs.get("uri", ""),
                "user_login": user.get("login", ""),
                "photo_url": photo_url,
            }

            observations.append(observation)

            if MAX_OBSERVATIONS_PER_TAXON and len(observations) >= MAX_OBSERVATIONS_PER_TAXON:
                return observations

        print(
            f"  taxon_id={taxon_id} {taxon_name}: "
            f"page={page}, fetched={len(results)}, kept_total={len(observations)}"
        )

        if len(results) < OBSERVATIONS_PER_PAGE:
            break

        page += 1
        time.sleep(SLEEP_SECONDS)

    return observations


# ============================================================
# WRITERS
# ============================================================

def write_species_master(taxa):
    fieldnames = [
        "taxon_id",
        "name",
        "preferred_common_name",
        "rank",
        "iconic_taxon_name",
        "observations_count",
    ]

    with SPECIES_MASTER_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in taxa:
            writer.writerow(row)


def write_observations_csv(observations):
    fieldnames = [
        "observation_id",
        "taxon_id",
        "scientific_name",
        "common_name",
        "rank",
        "observed_on",
        "created_at",
        "quality_grade",
        "latitude",
        "longitude",
        "place_guess",
        "uri",
        "user_login",
        "photo_url",
    ]

    with OBSERVATIONS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in observations:
            writer.writerow(row)


def observation_to_feature(obs):
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                float(obs["longitude"]),
                float(obs["latitude"]),
            ],
        },
        "properties": {
            "observation_id": obs["observation_id"],
            "taxon_id": obs["taxon_id"],
            "scientific_name": obs["scientific_name"],
            "common_name": obs["common_name"],
            "rank": obs["rank"],
            "observed_on": obs["observed_on"],
            "created_at": obs["created_at"],
            "quality_grade": obs["quality_grade"],
            "place_guess": obs["place_guess"],
            "uri": obs["uri"],
            "user_login": obs["user_login"],
            "photo_url": obs["photo_url"],
        },
    }


def write_geojson_chunks(observations):
    GEOJSON_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    # Borrar chunks viejos
    for old_file in GEOJSON_CHUNKS_DIR.glob("*.geojson"):
        old_file.unlink()

    chunk_files = []

    for chunk_index, start in enumerate(range(0, len(observations), GEOJSON_CHUNK_SIZE), start=1):
        chunk = observations[start:start + GEOJSON_CHUNK_SIZE]

        features = [observation_to_feature(obs) for obs in chunk]

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }

        chunk_name = f"observations_{chunk_index:03d}.geojson"
        chunk_path = GEOJSON_CHUNKS_DIR / chunk_name

        with chunk_path.open("w", encoding="utf-8") as f:
            json.dump(
                geojson,
                f,
                ensure_ascii=False,
                separators=(",", ":")
            )

        chunk_files.append(f"geojson_chunks/{chunk_name}")

        print(
            f"Wrote {chunk_path} with {len(features)} observations "
            f"({start + len(features)} / {len(observations)})"
        )

    manifest = {
        "updated_at_utc": now_utc_iso(),
        "total_observations": len(observations),
        "chunk_size": GEOJSON_CHUNK_SIZE,
        "chunks_count": len(chunk_files),
        "chunks": chunk_files,
    }

    with GEOJSON_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # Archivo chico para evitar el límite de 100 MB de GitHub.
    # El mapa debería cargar geojson_manifest.json y luego los chunks.
    small_placeholder = {
        "type": "FeatureCollection",
        "features": [],
        "note": "Full dataset is split into data/geojson_chunks/*.geojson. Load data/geojson_manifest.json.",
        "total_observations": len(observations),
        "chunks_count": len(chunk_files),
        "manifest": "data/geojson_manifest.json",
    }

    with OBSERVATIONS_GEOJSON.open("w", encoding="utf-8") as f:
        json.dump(small_placeholder, f, ensure_ascii=False, indent=2)


def write_summary(taxa, observations, processed_taxa_count):
    taxa_with_observations = len({obs["taxon_id"] for obs in observations})
    taxa_remaining = max(len(taxa) - taxa_with_observations, 0)

    chunks_count = 0
    if GEOJSON_MANIFEST.exists():
        try:
            with GEOJSON_MANIFEST.open("r", encoding="utf-8") as f:
                manifest = json.load(f)
                chunks_count = manifest.get("chunks_count", 0)
        except Exception:
            chunks_count = 0

    summary = {
        "updated_at_utc": now_utc_iso(),
        "place_id": PLACE_ID,
        "place_name": PLACE_NAME,
        "scope": "Native/endemic Plantae taxa observed in Argentina on iNaturalist / ArgentiNat",
        "method": "observations/species_counts native=true + all available georeferenced research-grade observations per taxon",
        "quality_grade": QUALITY_GRADE,
        "species_available_from_api": len(taxa),
        "species_written": len(taxa),
        "observations_written": len(observations),
        "taxa_processed_this_run": processed_taxa_count,
        "taxa_with_observations": taxa_with_observations,
        "taxa_remaining_without_observations": taxa_remaining,
        "max_species": MAX_SPECIES,
        "max_taxa_per_run": MAX_TAXA_PER_RUN,
        "max_observations_per_taxon": MAX_OBSERVATIONS_PER_TAXON,
        "observations_per_page": OBSERVATIONS_PER_PAGE,
        "geojson_chunk_size": GEOJSON_CHUNK_SIZE,
        "geojson_chunks_count": chunks_count,
        "geojson_manifest": "data/geojson_manifest.json",
        "sleep_seconds": SLEEP_SECONDS,
        "species_counts_api_url_example": (
            "https://api.inaturalist.org/v1/observations/species_counts"
            "?place_id=7190&native=true&iconic_taxa=Plantae"
            "&quality_grade=research&per_page=100&page=1&has%5B%5D=geo"
        ),
        "observations_api_url_example": (
            "https://api.inaturalist.org/v1/observations"
            "?place_id=7190&taxon_id=51454&native=true"
            "&quality_grade=research&per_page=200&page=1"
            "&order_by=observed_on&order=desc&has%5B%5D=geo"
        ),
        "methodology_note": (
            "This is observation-based, not a complete formal botanical checklist. "
            "Native/endemic status depends on iNaturalist establishment means. "
            "For formal vascular plant taxonomy, validate against Flora Argentina / Darwinion."
        ),
    }

    with UPDATE_SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with UPDATE_PROGRESS_JSON.open("w", encoding="utf-8") as f:
        json.dump({
            "updated_at_utc": now_utc_iso(),
            "processed_taxa_count": processed_taxa_count,
            "total_taxa": len(taxa),
            "observations_written": len(observations),
            "taxa_with_observations": taxa_with_observations,
            "geojson_chunks_count": chunks_count,
        }, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


# ============================================================
# MAIN
# ============================================================

def main():
    taxa = fetch_native_plant_taxa()

    if not taxa:
        raise RuntimeError("No native plant taxa found from API.")

    write_species_master(taxa)

    taxa_to_process = taxa

    if MAX_TAXA_PER_RUN and MAX_TAXA_PER_RUN > 0:
        taxa_to_process = taxa[:MAX_TAXA_PER_RUN]

    print(f"Species/taxa available: {len(taxa)}")
    print(f"Taxa selected for this run: {len(taxa_to_process)}")
    print(
        "Max observations per taxon: "
        f"{MAX_OBSERVATIONS_PER_TAXON if MAX_OBSERVATIONS_PER_TAXON else 'unlimited'}"
    )

    existing_ids = set()
    all_observations = []
    processed_taxa_count = 0

    for idx, taxon in enumerate(taxa_to_process, start=1):
        print(
            f"[{idx}/{len(taxa_to_process)}] Fetching observations for "
            f"{taxon.get('name')} / taxon_id={taxon.get('taxon_id')}"
        )

        try:
            observations = fetch_observations_for_taxon(taxon)
        except Exception as exc:
            print(f"Failed taxon_id={taxon.get('taxon_id')}: {exc}")
            continue

        for obs in observations:
            obs_id = obs["observation_id"]

            if obs_id in existing_ids:
                continue

            existing_ids.add(obs_id)
            all_observations.append(obs)

        processed_taxa_count += 1

        print(f"Current total observations: {len(all_observations)}")
        time.sleep(SLEEP_SECONDS)

    write_observations_csv(all_observations)
    write_geojson_chunks(all_observations)
    write_summary(taxa, all_observations, processed_taxa_count)


if __name__ == "__main__":
    main()
