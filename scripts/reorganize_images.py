"""Reorganize camera images into brand/format/model hierarchy.

Moves files into `Brand/Format/Model/main.jpg` structure,
updates cameras.json with new paths, and handles orphan files.

Usage:
    uv run python scripts/reorganize_images.py --dry-run
    uv run python scripts/reorganize_images.py --execute
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR

# Use relative paths consistently (matching cameras.json format)
CAMERAS_IMAGES_REL = "data/images/cameras"
CAMERAS_JSON = MERGED_DIR / "cameras.json"
REPORTS_DIR = Path("data/reports")
ORPHANS_REL = f"{CAMERAS_IMAGES_REL}/_orphans"
LOG_PATH = Path(f"{CAMERAS_IMAGES_REL}/_reorganize_log.json")


def _sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    s = re.sub(r'[<>:"/\\|?*]', "_", name)
    s = re.sub(r"[\s_]+", "_", s).strip("_.")
    return s[:200] if s else "unknown"


def _rel_parts(path_str: str) -> tuple[str, ...]:
    """Get path parts relative to CAMERAS_IMAGES_REL."""
    rel = path_str[len(CAMERAS_IMAGES_REL) + 1 :]  # strip "data/images/cameras/"
    return Path(rel).parts


def _is_flat_file(path_str: str) -> bool:
    """Check if a path is a flat file (directly in cameras/ root)."""
    parts = _rel_parts(path_str)
    return len(parts) == 1


def load_cameras() -> list[dict]:
    return json.loads(CAMERAS_JSON.read_text())


def save_cameras(cameras: list[dict]) -> None:
    CAMERAS_JSON.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"  Saved {len(cameras)} cameras to {CAMERAS_JSON}")


def scan_disk() -> set[str]:
    """Return all file paths under cameras images dir as relative paths."""
    base = Path(CAMERAS_IMAGES_REL)
    files = set()
    for f in base.rglob("*"):
        if f.is_file() and f.name != ".DS_Store":
            files.add(str(f))
    return files


def collect_json_paths(cameras: list[dict]) -> set[str]:
    """Return all local_path values from cameras.json."""
    paths = set()
    for cam in cameras:
        for img in cam.get("images", []):
            lp = img.get("local_path")
            if lp:
                paths.add(lp)
    return paths


def build_move_plan(cameras: list[dict], disk_files: set[str]):
    """Build the complete move plan without touching disk.

    Returns:
        moves: dict mapping source_path -> target_path
        cam_path_updates: list of (camera_index, image_index, new_local_path)
        orphan_moves: dict mapping source_path -> target_path
        stats: dict with statistics
    """
    moves = {}  # source -> target
    cam_path_updates = []  # (cam_idx, img_idx, new_path)
    json_paths = collect_json_paths(cameras)
    orphan_files = disk_files - json_paths
    missing_files = json_paths - disk_files

    # Build lookup: for flat files, map base_stem -> list of orphan paths
    # This lets us quickly find _2, _3, .jpeg variants
    orphan_by_stem = {}  # base_stem -> list of (path, suffix_num_or_None)
    for p in orphan_files:
        if not _is_flat_file(p):
            continue
        path = Path(p)
        stem = path.stem
        m = re.match(r"^(.+?)_(\d+)$", stem)
        if m:
            base_stem = m.group(1)
            num = int(m.group(2))
        else:
            base_stem = stem
            num = None
        orphan_by_stem.setdefault(base_stem, []).append((p, num))

    # Track all targets to detect collisions
    used_targets = set()
    # Track which orphans get claimed
    claimed_orphans = set()

    # Phase 1: Process each camera with local_path entries
    for cam_idx, cam in enumerate(cameras):
        mfr = cam.get("manufacturer_normalized", cam.get("manufacturer", "Unknown"))
        name = cam["name"]
        brand_dir = _sanitize_filename(mfr)
        model_dir = _sanitize_filename(name)
        target_base = f"{CAMERAS_IMAGES_REL}/{brand_dir}/{model_dir}"

        # Collect all unique source files for this camera (preserving order)
        source_files = []
        seen_sources = set()

        has_local = False
        for img in cam.get("images", []):
            lp = img.get("local_path")
            if lp:
                has_local = True
                if lp not in seen_sources:
                    seen_sources.add(lp)
                    source_files.append(lp)

        if not has_local:
            continue

        # Find orphan secondary images matching this camera's primary files
        for src in list(source_files):
            if not _is_flat_file(src):
                continue
            src_stem = Path(src).stem
            # Look for _N siblings
            for orphan_path, num in orphan_by_stem.get(src_stem, []):
                if orphan_path not in seen_sources:
                    seen_sources.add(orphan_path)
                    source_files.append(orphan_path)
                    claimed_orphans.add(orphan_path)
            # Look for alt extension match (e.g., file.jpeg when file.jpg is referenced)
            src_path = Path(src)
            for orphan_path, num in orphan_by_stem.get(src_stem, []):
                pass  # already handled above
            # Also check orphans with same stem but different ext (no _N suffix)
            for orphan_path, num in orphan_by_stem.get(src_stem, []):
                if num is None and orphan_path not in seen_sources:
                    seen_sources.add(orphan_path)
                    source_files.append(orphan_path)
                    claimed_orphans.add(orphan_path)

        # Sort secondary files by their numeric suffix
        primary = [s for s in source_files if s not in orphan_files or s in json_paths]
        secondary = sorted(
            [s for s in source_files if s in orphan_files and s not in json_paths],
            key=lambda p: _extract_num(p),
        )
        source_files = primary + secondary

        # Assign target filenames
        file_num = 0
        src_to_target = {}
        for src in source_files:
            if src in missing_files:
                continue

            ext = Path(src).suffix
            if file_num == 0:
                target = f"{target_base}/main{ext}"
            else:
                target = f"{target_base}/{file_num + 1}{ext}"
            file_num += 1

            # Handle collision with another camera's target
            while target in used_targets:
                file_num += 1
                target = f"{target_base}/{file_num + 1}{ext}"

            used_targets.add(target)
            src_to_target[src] = target

            if src != target:
                moves[src] = target

        # Record path updates for this camera's image entries
        for img_idx, img in enumerate(cam.get("images", [])):
            lp = img.get("local_path")
            if lp and lp in src_to_target:
                new_path = src_to_target[lp]
                if new_path != lp:
                    cam_path_updates.append((cam_idx, img_idx, new_path))

    # Phase 2: Handle remaining orphans -> _orphans/
    remaining_orphans = orphan_files - claimed_orphans - set(moves.keys())
    orphan_moves = {}
    orphan_targets_used = set()

    for p in sorted(remaining_orphans):
        if not _is_flat_file(p):
            continue  # already in brand/model structure, leave it
        filename = Path(p).name
        target = f"{ORPHANS_REL}/{filename}"
        # Handle filename collision
        if target in orphan_targets_used:
            stem = Path(p).stem
            suffix = Path(p).suffix
            counter = 2
            while True:
                target = f"{ORPHANS_REL}/{stem}_dup{counter}{suffix}"
                if target not in orphan_targets_used:
                    break
                counter += 1
        orphan_targets_used.add(target)
        orphan_moves[p] = target

    stats = {
        "total_cameras": len(cameras),
        "cameras_with_images": sum(
            1 for c in cameras if any(i.get("local_path") for i in c.get("images", []))
        ),
        "total_disk_files": len(disk_files),
        "total_json_paths": len(json_paths),
        "missing_files": len(missing_files),
        "orphan_files": len(orphan_files),
        "moves_planned": len(moves),
        "already_correct": len(used_targets) - len(moves),
        "path_updates": len(cam_path_updates),
        "orphan_moves": len(orphan_moves),
        "orphans_claimed_as_secondary": len(claimed_orphans),
        "missing_file_list": sorted(missing_files),
    }

    return moves, cam_path_updates, orphan_moves, stats


def _extract_num(path_str: str) -> int:
    """Extract numeric suffix from filename for sorting (_2 -> 2, _10 -> 10)."""
    stem = Path(path_str).stem
    m = re.match(r"^.+?_(\d+)$", stem)
    return int(m.group(1)) if m else 0


def remove_missing_paths(cameras: list[dict], missing_files: set[str]) -> int:
    """Remove local_path entries for files that don't exist on disk."""
    removed = 0
    for cam in cameras:
        for img in cam.get("images", []):
            lp = img.get("local_path")
            if lp and lp in missing_files:
                img["local_path"] = None
                removed += 1
                print(f"    Removed missing: {lp} ({cam['name']})")
    return removed


def execute_moves(
    moves: dict[str, str],
    orphan_moves: dict[str, str],
    cam_path_updates: list[tuple[int, int, str]],
    cameras: list[dict],
    missing_files: set[str],
) -> None:
    """Execute all file moves and update cameras.json."""
    all_moves = {**moves, **orphan_moves}

    # Create all target directories
    target_dirs = {str(Path(t).parent) for t in all_moves.values()}
    for d in sorted(target_dirs):
        Path(d).mkdir(parents=True, exist_ok=True)

    # Write move log for crash recovery
    log_data = {"moves": all_moves, "status": "in_progress"}
    LOG_PATH.write_text(json.dumps(log_data, indent=2, ensure_ascii=False))

    # Execute file moves
    moved = 0
    errors = 0
    for src, dst in sorted(all_moves.items()):
        try:
            shutil.move(src, dst)
            moved += 1
        except Exception as e:
            print(f"    ERROR: {src} -> {dst}: {e}")
            errors += 1

    print(f"  Moved {moved} files ({errors} errors)")

    if errors:
        print("  WARNING: Some moves failed. Move log preserved at", LOG_PATH)
        return

    # Remove missing file references
    removed = remove_missing_paths(cameras, missing_files)
    if removed:
        print(f"  Removed {removed} missing file references")

    # Update cameras.json with new paths
    for cam_idx, img_idx, new_path in cam_path_updates:
        cameras[cam_idx]["images"][img_idx]["local_path"] = new_path

    save_cameras(cameras)

    # Delete move log on success
    LOG_PATH.unlink(missing_ok=True)


def verify(cameras: list[dict]) -> bool:
    """Verify all local_path entries point to existing files."""
    missing = 0
    total = 0
    for cam in cameras:
        for img in cam.get("images", []):
            lp = img.get("local_path")
            if lp:
                total += 1
                if not Path(lp).exists():
                    if missing < 10:
                        print(f"    MISSING: {lp} ({cam['name']})")
                    missing += 1
    if missing:
        print(f"  {missing}/{total} local_path entries point to missing files")
        return False
    print(f"  All {total} local_path entries verified OK")
    return True


def cleanup_empty_dirs() -> int:
    """Remove empty directories and .DS_Store files."""
    base = Path(CAMERAS_IMAGES_REL)
    for ds in base.rglob(".DS_Store"):
        ds.unlink()
    removed = 0
    for d in sorted(base.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            removed += 1
    return removed


def main():
    parser = argparse.ArgumentParser(description="Reorganize camera images into brand/model hierarchy")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without modifying anything")
    group.add_argument("--execute", action="store_true", help="Execute the reorganization")
    args = parser.parse_args()

    print("Phase 0: Loading data...")
    cameras = load_cameras()
    disk_files = scan_disk()
    json_paths = collect_json_paths(cameras)

    print(f"  Cameras: {len(cameras)}")
    print(f"  Files on disk: {len(disk_files)}")
    print(f"  Unique local_paths in JSON: {len(json_paths)}")
    print(f"  Orphans (on disk, not in JSON): {len(disk_files - json_paths)}")
    print(f"  Missing (in JSON, not on disk): {len(json_paths - disk_files)}")

    print("\nPhase 1-2: Building move plan...")
    moves, cam_path_updates, orphan_moves, stats = build_move_plan(cameras, disk_files)

    print(f"  Files to move (camera images): {stats['moves_planned']}")
    print(f"  Orphans claimed as secondary: {stats['orphans_claimed_as_secondary']}")
    print(f"  Path updates in cameras.json: {stats['path_updates']}")
    print(f"  Orphans to _orphans/: {stats['orphan_moves']}")
    if stats["missing_file_list"]:
        print(f"  Missing files to clean: {stats['missing_file_list']}")

    if args.dry_run:
        print("\n[DRY RUN] No changes made.")

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        preview = {
            "stats": stats,
            "moves_count": len(moves),
            "orphan_moves_count": len(orphan_moves),
            "sample_moves": dict(list(sorted(moves.items()))[:50]),
            "sample_orphan_moves": dict(list(sorted(orphan_moves.items()))[:20]),
        }
        preview_path = REPORTS_DIR / "reorganize_preview.json"
        preview_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False))
        print(f"  Preview written to {preview_path}")

        print("\nSample moves (first 20):")
        for i, (src, dst) in enumerate(sorted(moves.items())):
            if i >= 20:
                print(f"  ... and {len(moves) - 20} more")
                break
            print(f"  {src}")
            print(f"    -> {dst}")

        if orphan_moves:
            print(f"\nSample orphan moves (first 10):")
            for i, (src, dst) in enumerate(sorted(orphan_moves.items())):
                if i >= 10:
                    print(f"  ... and {len(orphan_moves) - 10} more")
                    break
                print(f"  {src}")
                print(f"    -> {dst}")

        # Collision check
        all_targets = list(moves.values()) + list(orphan_moves.values())
        if len(all_targets) != len(set(all_targets)):
            from collections import Counter
            dupes = {t: c for t, c in Counter(all_targets).items() if c > 1}
            print(f"\nWARNING: {len(dupes)} target collisions detected!")
            for t, c in list(dupes.items())[:5]:
                print(f"  {t} ({c}x)")
        else:
            print(f"\nNo target collisions detected.")

        # Check for source/target overlap (would be a problem during execution)
        sources = set(moves.keys()) | set(orphan_moves.keys())
        targets = set(moves.values()) | set(orphan_moves.values())
        overlap = sources & targets
        if overlap:
            print(f"WARNING: {len(overlap)} files are both source and target!")
            for p in list(overlap)[:5]:
                print(f"  {p}")
        return

    # Execute
    print("\nPhase 3: Executing moves...")
    missing_files = json_paths - disk_files
    execute_moves(moves, orphan_moves, cam_path_updates, cameras, missing_files)

    print("\nPhase 4: Verifying...")
    cameras = load_cameras()
    verify(cameras)
    disk_after = scan_disk()
    print(f"  Files before: {len(disk_files)}, after: {len(disk_after)}")

    print("\nPhase 5: Cleanup...")
    removed = cleanup_empty_dirs()
    print(f"  Removed {removed} empty directories")

    disk_final = scan_disk()
    print(f"\nDone! Final file count: {len(disk_final)}")


if __name__ == "__main__":
    main()
