"""Build a field profile from the command line — no GCP, no keys.

    python3 backend/run_local.py                      # the Narwana demo field
    python3 backend/run_local.py --lat 29.61 --lng 76.11
    python3 backend/run_local.py --out data/seed/demo_field_profile.json

Used to generate the seeded fallback profile that keeps S1/S2 alive offline.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from m0_field import build_field_profile  # noqa: E402
from m0_field.seed import seeded_soil_for  # noqa: E402
from m0_field.sources.earth_engine import RABI_PEAK_WINDOW  # noqa: E402

# Build Brief product defaults: Haryana wheat belt, near Narwana (Kaithal-Jind).
DEMO_LAT = 29.61
DEMO_LNG = 76.11


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an M0 field profile")
    parser.add_argument("--lat", type=float, default=DEMO_LAT)
    parser.add_argument("--lng", type=float, default=DEMO_LNG)
    parser.add_argument("--field-id", default="field-demo-narwana")
    parser.add_argument("--plot-ha", type=float, default=1.5)
    parser.add_argument("--fallback-ndvi", type=float, default=None)
    parser.add_argument(
        "--season",
        choices=["live", "rabi"],
        default="live",
        help="'live' = last 30 days; 'rabi' = peak wheat canopy window",
    )
    parser.add_argument(
        "--no-seed-npk",
        action="store_true",
        help="leave phosphorus and potassium null instead of seeding district values",
    )
    parser.add_argument("--ndvi-start", help="YYYY-MM-DD, overrides --season")
    parser.add_argument("--ndvi-end", help="YYYY-MM-DD, overrides --season")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.ndvi_start and args.ndvi_end:
        window = (args.ndvi_start, args.ndvi_end)
    elif args.season == "rabi":
        window = RABI_PEAK_WINDOW
    else:
        window = None

    profile = build_field_profile(
        pin={"lat": args.lat, "lng": args.lng},
        field_id=args.field_id,
        plot_ha=args.plot_ha,
        fallback_ndvi=args.fallback_ndvi,
        ndvi_window=window,
        seeded_soil=None if args.no_seed_npk else seeded_soil_for(args.lat, args.lng),
    )

    payload = profile.to_dict()
    rendered = json.dumps(payload, indent=2)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n")
        print(f"wrote {args.out}")
    else:
        print(rendered)

    _print_provenance(payload)
    return 0


def _print_provenance(payload: dict) -> None:
    print("\n--- signal provenance ---", file=sys.stderr)
    for signal, meta in payload.get("sources", {}).items():
        note = f"  ({meta['note']})" if meta.get("note") else ""
        print(f"{signal:<12} {meta['status']:<12} {meta['source']}{note}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
