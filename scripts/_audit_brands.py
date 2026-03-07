#!/usr/bin/env python3
"""Audit camera brand/model image folders against cameras.json.

Reports:
1. Brand folders in images/ that don't match any manufacturer_normalized in cameras.json
2. Model folders that don't match any camera entry for that brand
3. Potential misplacements (model name contains a different brand name)
4. Brand folders with 0 main.jpg files (empty brands)
5. Summary statistics
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename (mirrors download.py)."""
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    s = re.sub(r'[\s_]+', '_', s).strip('_.')
    return s[:200] if s else 'unknown'


def main():
    project_root = Path(__file__).resolve().parent.parent
    cameras_json = project_root / "data" / "merged" / "cameras.json"
    images_dir = project_root / "data" / "images" / "cameras"

    if not cameras_json.exists():
        print(f"ERROR: {cameras_json} not found")
        sys.exit(1)
    if not images_dir.exists():
        print(f"ERROR: {images_dir} not found")
        sys.exit(1)

    # Load cameras
    with open(cameras_json) as f:
        cameras = json.load(f)
    print(f"Loaded {len(cameras)} cameras from cameras.json\n")

    # ---- Build lookup structures from cameras.json ----

    # brand_normalized -> set of sanitized model names
    # Also keep brand_normalized -> sanitized brand folder name mapping
    brand_to_sanitized = {}  # manufacturer_normalized -> sanitized folder name
    sanitized_to_brand = {}  # sanitized folder name -> manufacturer_normalized
    brand_models = {}        # sanitized brand folder -> set of sanitized model names
    brand_models_raw = {}    # sanitized brand folder -> dict of sanitized model -> list of raw camera names

    all_brands_normalized = set()

    for cam in cameras:
        mfr = cam.get("manufacturer_normalized", "")
        name = cam.get("name", "unknown")
        if not mfr:
            continue

        all_brands_normalized.add(mfr)
        safe_mfr = _sanitize_filename(mfr)
        safe_name = _sanitize_filename(name)

        brand_to_sanitized[mfr] = safe_mfr
        sanitized_to_brand[safe_mfr] = mfr

        if safe_mfr not in brand_models:
            brand_models[safe_mfr] = set()
            brand_models_raw[safe_mfr] = {}

        brand_models[safe_mfr].add(safe_name)
        if safe_name not in brand_models_raw[safe_mfr]:
            brand_models_raw[safe_mfr][safe_name] = []
        brand_models_raw[safe_mfr][safe_name].append(name)

    # All known sanitized brand folder names from cameras.json
    known_brand_folders = set(brand_to_sanitized.values())

    print(f"Unique manufacturer_normalized values: {len(all_brands_normalized)}")
    print(f"Unique sanitized brand folders (from JSON): {len(known_brand_folders)}")

    # ---- Scan image directories ----
    image_brand_folders = sorted([
        d.name for d in images_dir.iterdir()
        if d.is_dir()
    ])
    print(f"Brand folders on disk: {len(image_brand_folders)}\n")

    # ============================================================
    # TASK 1: Brand folders that DON'T exist in cameras.json
    # ============================================================
    print("=" * 80)
    print("TASK 1: Brand folders in images/ with NO matching manufacturer_normalized")
    print("=" * 80)

    orphan_brands = []
    for folder in image_brand_folders:
        if folder == "_orphans":
            continue  # Skip special folder
        if folder not in known_brand_folders:
            # Count model dirs and main.jpg files
            folder_path = images_dir / folder
            model_dirs = [d for d in folder_path.iterdir() if d.is_dir()]
            main_jpgs = [d for d in model_dirs if (d / "main.jpg").exists()]
            orphan_brands.append((folder, len(model_dirs), len(main_jpgs)))

    if orphan_brands:
        print(f"\nFound {len(orphan_brands)} orphan brand folders:\n")
        for folder, n_models, n_images in sorted(orphan_brands):
            print(f"  {folder:40s}  {n_models:3d} model dirs, {n_images:3d} main.jpg files")
    else:
        print("\nNo orphan brand folders found.")

    # ============================================================
    # TASK 2: Model folders that don't match any camera for that brand
    # ============================================================
    print("\n" + "=" * 80)
    print("TASK 2: Model folders with NO matching camera entry in cameras.json")
    print("=" * 80)

    orphan_models_by_brand = {}
    total_orphan_models = 0
    total_models_checked = 0

    for folder in image_brand_folders:
        if folder == "_orphans":
            continue
        folder_path = images_dir / folder
        model_dirs = sorted([d.name for d in folder_path.iterdir() if d.is_dir()])

        if not model_dirs:
            continue

        known_models = brand_models.get(folder, set())
        orphans_in_brand = []

        for model_dir in model_dirs:
            total_models_checked += 1
            if model_dir not in known_models:
                has_main = (folder_path / model_dir / "main.jpg").exists()
                orphans_in_brand.append((model_dir, has_main))
                total_orphan_models += 1

        if orphans_in_brand:
            orphan_models_by_brand[folder] = orphans_in_brand

    print(f"\nTotal model folders checked: {total_models_checked}")
    print(f"Total orphan model folders: {total_orphan_models}")
    print(f"Brands with orphan models: {len(orphan_models_by_brand)}\n")

    if orphan_models_by_brand:
        for brand in sorted(orphan_models_by_brand.keys()):
            orphans = orphan_models_by_brand[brand]
            brand_label = sanitized_to_brand.get(brand, brand)
            total_in_brand = len([d for d in (images_dir / brand).iterdir() if d.is_dir()])
            print(f"  [{brand}] (brand: {brand_label}, {total_in_brand} total model dirs, {len(orphans)} orphans):")
            for model_dir, has_main in orphans:
                status = "has main.jpg" if has_main else "NO main.jpg"
                print(f"    - {model_dir}  ({status})")
            print()

    # ============================================================
    # TASK 3: Potential misplacements (model name contains different brand)
    # ============================================================
    print("=" * 80)
    print("TASK 3: Potential misplacements (model folder name contains a DIFFERENT brand name)")
    print("=" * 80)

    # Build list of well-known brand names to check against.
    # Only use distinctive camera brand names (5+ chars) to avoid false positives
    # from generic English words that happen to be brand names (e.g., "mini",
    # "red", "sport", "happy", "arrow", "nova", "five", "venus", "bell", etc.)
    #
    # Excluded short/ambiguous brand names that cause false positives:
    #   3D, 3M, 4D, Le, FED, ICA, ERA, Red, Mini, Five, Coca, Nova, Omes,
    #   Sport, Arrow, Happy, Venus, Pearl, Diana, Rocks, Wales, Vista, Helm,
    #   Alpa, Boots, Bell, Cabbage, Empire, Target, Purple, Jazz, Indo, Yi, etc.

    # Curated list of distinctive major camera brand names (unlikely to appear
    # as common words in model names of other brands)
    well_known_brands = {
        "minolta", "nikon", "canon", "pentax", "olympus", "leica",
        "hasselblad", "mamiya", "rollei", "contax", "yashica", "ricoh",
        "fujifilm", "kodak", "polaroid", "zeiss", "voigtlander",
        "praktica", "zenit", "kiev", "zorki", "agfa", "konica",
        "nikkormat", "nikomat", "nikkor", "asahi", "topcon", "miranda",
        "petri", "chinon", "cosina", "vivitar", "sigma", "tamron",
        "holga", "lomography", "seagull", "phenix", "ansco", "argus",
        "graflex", "hanimex", "halina", "coronet", "ernemann",
        "balda", "wirgin", "braun", "ducati", "exakta", "samsung",
        "hasselblad", "soligor", "keystone", "kalimar",
    }
    # Also add normalized brands that are 6+ chars (distinctive enough)
    for brand in all_brands_normalized:
        if len(brand) >= 6:
            well_known_brands.add(brand.lower())

    # Known legitimate cross-brand relationships (parent/child, collaborations, OEM)
    # These are NOT misplacements even though model contains another brand name.
    _LEGIT_CROSS_BRAND = {
        # Asahi made Pentax cameras
        ("asahi optical co", "pentax"), ("asahi optical co", "asahi pentax"),
        ("asahi optical co.", "pentax"),
        # Konica Minolta is Konica + Minolta merger
        ("konica", "minolta"), ("minolta", "konica"),
        ("konica minolta", "konica"), ("konica minolta", "minolta"),
        # Bell & Howell sold Canon/Nikon rebadges
        ("canon", "bell & howell"), ("bell & howell", "canon"),
        ("nikon", "bell & howell"),
        # Argus/Cosina collaboration
        ("argus", "cosina"),
        # Exakta/Praktica/Contax all from Dresden/Pentacon group
        ("exakta", "contax"), ("exakta", "praktica"),
        # Zeiss Ikon is part of Zeiss; Contax is Zeiss Ikon sub-brand
        ("zeiss", "zeiss ikon"), ("zeiss ikon", "zeiss"),
        ("zeiss ikon", "contax"), ("zeiss", "contax"),
        # Halina/Ansco collaboration; Haking made Halina cameras
        ("halina", "ansco"), ("ansco", "halina"),
        ("halina/ansco", "halina"), ("halina/ansco", "ansco"),
        ("haking", "halina"), ("haking", "hanimex"),
        # Revue was a rebrand house
        ("revue", "chinon"), ("revue", "cosina"), ("revue", "ricoh"),
        ("revue", "praktica"), ("revue", "zenit"),
        # Kodak/Chinon
        ("kodak", "chinon"),
        # Samsung/Rollei
        ("samsung", "rollei"), ("samsung electronics", "rollei"),
        # Fujifilm/Instax sub-brand
        ("fujifilm", "instax"),
        # Yashica/Contax (Yashica-Kyocera group made Contax)
        ("yashica", "contax"),
        # Riken is Ricoh's old name
        ("riken", "ricoh"),
        # Zenit factory also made Zorki, Horizon, FED
        ("zenit", "zorki"), ("zenit", "horizon"),
        # FED/Zorki both from Soviet rangefinder lineage
        ("fed", "zorki"),
        # Leica/Minolta CL collaboration
        ("leica", "minolta"),
        # Nikon and Nikkor/Nikkormat/Nikomat are the same brand
        ("nikon", "nikkor"), ("nikon", "nikkormat"), ("nikon", "nikomat"),
        # Nikon Nikonos was based on Calypso design
        ("nikon", "calypso"),
        # Kiev is based on Contax/Zeiss designs
        ("kiev", "contax"), ("kiev", "zeiss"), ("kiev", "zenit"),
        # Miranda/Soligor rebadging
        ("miranda", "soligor"),
        # Minox made Leica miniatures
        ("minox", "leica"),
        # Cosina made Edixa cameras
        ("cosina", "edixa"),
        # Kodak Target and Empire are model names, not brands
        ("kodak", "target"), ("kodak", "empire"),
        # Agfa Traveller is a model name
        ("agfa", "traveller"),
        # Various is a catch-all
        ("various", "holga"),
        # Rollei/Zeiss collaboration
        ("rollei", "zeiss"),
        # Balda Coronet is a model
        ("balda", "coronet"),
        # Leica/Polaroid
        ("leica", "polaroid"),
        # FED Red Flag
        ("fed", "red flag"),
    }

    misplacements_high = []  # Model STARTS with a different brand name
    misplacements_low = []   # Model CONTAINS a different brand name

    for folder in image_brand_folders:
        if folder == "_orphans":
            continue
        folder_path = images_dir / folder
        brand_name_lower = sanitized_to_brand.get(folder, folder).lower()
        model_dirs = sorted([d.name for d in folder_path.iterdir() if d.is_dir()])

        for model_dir in model_dirs:
            model_lower = model_dir.lower().replace("_", " ")
            for other_brand in well_known_brands:
                # Skip if this IS the current brand
                if other_brand == brand_name_lower:
                    continue
                # Skip if the other brand is a substring of the current brand or vice versa
                if other_brand in brand_name_lower or brand_name_lower in other_brand:
                    continue
                # Skip known legitimate cross-brand pairings
                if (brand_name_lower, other_brand) in _LEGIT_CROSS_BRAND:
                    continue

                # Check if other brand name appears as a word in model name
                pattern = r'\b' + re.escape(other_brand) + r'\b'
                if re.search(pattern, model_lower):
                    has_main = (folder_path / model_dir / "main.jpg").exists()
                    # HIGH confidence: model name starts with the other brand
                    if model_lower.startswith(other_brand + " ") or model_lower == other_brand:
                        misplacements_high.append((folder, model_dir, other_brand, has_main))
                    else:
                        misplacements_low.append((folder, model_dir, other_brand, has_main))

    print(f"\n--- HIGH CONFIDENCE (model name STARTS with a different brand) ---")
    if misplacements_high:
        print(f"Found {len(misplacements_high)} high-confidence misplacements:\n")
        for brand_folder, model_dir, detected_brand, has_main in sorted(misplacements_high):
            status = "has main.jpg" if has_main else "NO main.jpg"
            print(f"  [{brand_folder}] {model_dir}")
            print(f"    -> Starts with brand '{detected_brand}' ({status})")
    else:
        print("None found.\n")

    print(f"\n--- LOW CONFIDENCE (model name CONTAINS a different brand) ---")
    if misplacements_low:
        print(f"Found {len(misplacements_low)} low-confidence matches (likely legitimate cross-brand refs):\n")
        for brand_folder, model_dir, detected_brand, has_main in sorted(misplacements_low):
            status = "has main.jpg" if has_main else "NO main.jpg"
            print(f"  [{brand_folder}] {model_dir}")
            print(f"    -> Contains brand '{detected_brand}' ({status})")
    else:
        print("None found.\n")

    misplacements = misplacements_high + misplacements_low

    # ============================================================
    # TASK 4: Brand folders with 0 main.jpg files
    # ============================================================
    print("\n" + "=" * 80)
    print("TASK 4: Brand folders with 0 main.jpg files (empty brands)")
    print("=" * 80)

    empty_brands = []
    for folder in image_brand_folders:
        if folder == "_orphans":
            continue
        folder_path = images_dir / folder
        model_dirs = [d for d in folder_path.iterdir() if d.is_dir()]
        main_jpg_count = sum(1 for d in model_dirs if (d / "main.jpg").exists())
        if main_jpg_count == 0:
            empty_brands.append((folder, len(model_dirs)))

    if empty_brands:
        print(f"\nFound {len(empty_brands)} brand folders with 0 main.jpg files:\n")
        for folder, n_model_dirs in sorted(empty_brands):
            brand_label = sanitized_to_brand.get(folder, folder)
            in_json = folder in known_brand_folders
            json_status = "in JSON" if in_json else "NOT in JSON"
            print(f"  {folder:40s}  {n_model_dirs:3d} model dirs  ({json_status}, brand: {brand_label})")
    else:
        print("\nNo empty brand folders found.")

    # ============================================================
    # TASK 5: Brands with very few images (1-5 model dirs)
    # ============================================================
    print("\n" + "=" * 80)
    print("TASK 5: Small brands (1-5 model dirs on disk) - higher misplacement risk")
    print("=" * 80)

    small_brands = []
    for folder in image_brand_folders:
        if folder == "_orphans":
            continue
        folder_path = images_dir / folder
        model_dirs = sorted([d.name for d in folder_path.iterdir() if d.is_dir()])
        if 1 <= len(model_dirs) <= 5:
            main_jpg_count = sum(
                1 for d in model_dirs
                if (folder_path / d / "main.jpg").exists()
            )
            in_json = folder in known_brand_folders
            small_brands.append((folder, model_dirs, main_jpg_count, in_json))

    if small_brands:
        print(f"\nFound {len(small_brands)} small brands:\n")
        for folder, models, n_imgs, in_json in sorted(small_brands):
            brand_label = sanitized_to_brand.get(folder, folder)
            json_status = "in JSON" if in_json else "NOT in JSON"
            print(f"  [{folder}] ({json_status}, brand: {brand_label}, {n_imgs} main.jpg)")
            for m in models:
                has_main = (images_dir / folder / m / "main.jpg").exists()
                is_orphan = m not in brand_models.get(folder, set())
                flags = []
                if not has_main:
                    flags.append("NO main.jpg")
                if is_orphan:
                    flags.append("ORPHAN")
                flag_str = f"  [{', '.join(flags)}]" if flags else ""
                print(f"    - {m}{flag_str}")
        print()

    # ============================================================
    # SUMMARY
    # ============================================================
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Cameras in JSON:              {len(cameras)}")
    print(f"  Unique brands in JSON:        {len(all_brands_normalized)}")
    print(f"  Brand folders on disk:        {len(image_brand_folders)}")
    print(f"  Orphan brand folders:         {len(orphan_brands)}")
    print(f"  Total model folders checked:  {total_models_checked}")
    print(f"  Orphan model folders:         {total_orphan_models}")
    print(f"  Potential misplacements:      {len(misplacements)}")
    print(f"  Empty brand folders (0 imgs): {len(empty_brands)}")
    print(f"  Small brands (1-5 models):    {len(small_brands)}")


if __name__ == "__main__":
    main()
