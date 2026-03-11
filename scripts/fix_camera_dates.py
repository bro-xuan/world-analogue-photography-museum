"""Fix incorrect camera launch dates from regex parsing errors and bad source data.

Usage:
    uv run python scripts/fix_camera_dates.py          # Dry-run (report only)
    uv run python scripts/fix_camera_dates.py --fix     # Apply fixes + save
"""

import argparse
import json
import sys

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR

CAMERAS_FILE = MERGED_DIR / "cameras.json"

# Rule 1: Explicit typo fixes
TYPO_FIXES = {
    ("AGFA", "Solina"): {"year_discontinued": 1962},
    ("AGFA", "Studio Camera"): {"year_discontinued": 1910},
}

# Rule 2: Pre-1880 whitelist (legitimate early cameras)
PRE_1880_WHITELIST = {
    ("Voigtlander", "Daguerreotype (Metallcamera)"),
    ("Voigtländer", "Daguerreotype (Metallcamera)"),
    ("Houghton (Ensign)", "Daguerreotype Tropical Sliding Box"),
}


def _cam_key(cam: dict) -> tuple[str, str]:
    return (cam.get("manufacturer", ""), cam.get("name", ""))


def fix_camera_dates(cameras: list[dict]) -> dict[str, list[dict]]:
    """Analyze and fix camera dates. Returns fixes grouped by category."""
    fixes = {
        "typo": [],
        "pre_1880": [],
        "swapped": [],
        "small_diff": [],
    }

    for cam in cameras:
        key = _cam_key(cam)
        yi = cam.get("year_introduced")
        yd = cam.get("year_discontinued")
        ld = cam.get("launch_date")

        # Rule 1: Explicit typo fixes
        if key in TYPO_FIXES:
            correction = TYPO_FIXES[key]
            fix = {"cam": cam, "changes": {}}
            for field, new_val in correction.items():
                old_val = cam.get(field)
                if old_val != new_val:
                    fix["changes"][field] = (old_val, new_val)
            if fix["changes"]:
                fixes["typo"].append(fix)
            continue

        # Rule 2 & 3: Pre-1880 dates
        if yi is not None and yi < 1880:
            if key in PRE_1880_WHITELIST:
                continue
            fix = {
                "cam": cam,
                "changes": {
                    "year_introduced": (yi, None),
                    "launch_date": (ld, None),
                },
            }
            fixes["pre_1880"].append(fix)
            continue

        # Rule 4 & 5: Discontinued before introduced
        if yi is not None and yd is not None and yd < yi:
            diff = yi - yd
            if diff >= 4:
                # Swapped dates
                fix = {
                    "cam": cam,
                    "changes": {
                        "year_introduced": (yi, yd),
                        "year_discontinued": (yd, yi),
                        "launch_date": (ld, str(yd)),
                    },
                }
                fixes["swapped"].append(fix)
            else:
                # Small diff — null out year_discontinued
                fix = {
                    "cam": cam,
                    "changes": {
                        "year_discontinued": (yd, None),
                    },
                }
                fixes["small_diff"].append(fix)

    return fixes


def apply_fixes(fixes: dict[str, list[dict]]) -> int:
    """Apply fixes to camera objects in-place. Returns total fix count."""
    total = 0
    for category, fix_list in fixes.items():
        for fix in fix_list:
            cam = fix["cam"]
            for field, (_, new_val) in fix["changes"].items():
                cam[field] = new_val
            total += 1
    return total


def print_report(fixes: dict[str, list[dict]]) -> None:
    """Print structured report grouped by fix category."""
    labels = {
        "typo": "Explicit typo fixes",
        "pre_1880": "Impossible pre-1880 dates (nulled out)",
        "swapped": "Swapped dates (diff >= 4 years)",
        "small_diff": "Small-diff dates (nulled year_discontinued)",
    }

    total = 0
    for category, fix_list in fixes.items():
        if not fix_list:
            continue
        print(f"\n=== {labels[category]} ({len(fix_list)}) ===")
        for fix in fix_list:
            cam = fix["cam"]
            mfr = cam.get("manufacturer", "?")
            name = cam.get("name", "?")
            print(f"  {mfr} / {name}")
            for field, (old, new) in fix["changes"].items():
                print(f"    {field}: {old} → {new}")
        total += len(fix_list)

    print(f"\n--- Total cameras to fix: {total} ---")


def main():
    parser = argparse.ArgumentParser(description="Fix incorrect camera dates")
    parser.add_argument("--fix", action="store_true", help="Apply fixes and save")
    args = parser.parse_args()

    cameras = json.loads(CAMERAS_FILE.read_text())
    print(f"Loaded {len(cameras)} cameras from {CAMERAS_FILE}")

    fixes = fix_camera_dates(cameras)
    print_report(fixes)

    if args.fix:
        count = apply_fixes(fixes)
        if count > 0:
            CAMERAS_FILE.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
            print(f"\nSaved {count} fixes to {CAMERAS_FILE}")
            print("Reminder: run `uv run python scripts/prepare_camera_pages.py` to regenerate web data")
        else:
            print("\nNo fixes to apply.")
    else:
        print("\nDry run — no changes made. Use --fix to apply.")


if __name__ == "__main__":
    main()
