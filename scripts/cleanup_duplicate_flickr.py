"""
Clean up wrong Flickr images from cameras.json.

Finds all images with source "flickr_scrape" where the same URL is used by
more than one camera. Removes those images from ALL cameras that share them,
deletes local files if they exist, and saves the updated cameras.json.
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

DATA_PATH = "data/merged/cameras.json"


def main():
    # Load cameras
    with open(DATA_PATH) as f:
        cameras = json.load(f)

    print(f"Loaded {len(cameras)} cameras")

    # Step 1: Build a map of flickr_scrape URL -> list of camera indices
    url_to_cameras: dict[str, list[int]] = defaultdict(list)
    for i, cam in enumerate(cameras):
        for img in cam.get("images", []):
            if img.get("source") == "flickr_scrape":
                url_to_cameras[img["url"]].append(i)

    total_flickr = len(url_to_cameras)
    print(f"Found {total_flickr} unique flickr_scrape URLs across all cameras")

    # Step 2: Find duplicate URLs (used by more than one camera)
    duplicate_urls = {url for url, indices in url_to_cameras.items() if len(indices) > 1}
    print(f"Found {len(duplicate_urls)} duplicate flickr_scrape URLs (shared by 2+ cameras)")

    if not duplicate_urls:
        print("Nothing to clean up!")
        return

    # Show some examples
    print("\nExamples of duplicate URLs:")
    for url in list(duplicate_urls)[:5]:
        camera_names = [cameras[i]["name"] for i in url_to_cameras[url]]
        print(f"  {url}")
        print(f"    shared by {len(camera_names)} cameras: {', '.join(camera_names[:5])}")
        if len(camera_names) > 5:
            print(f"    ... and {len(camera_names) - 5} more")

    # Step 3: Remove duplicate images and delete local files
    cameras_affected = 0
    images_removed = 0
    files_deleted = 0
    files_missing = 0

    for i, cam in enumerate(cameras):
        original_count = len(cam.get("images", []))
        new_images = []
        for img in cam.get("images", []):
            if img.get("source") == "flickr_scrape" and img["url"] in duplicate_urls:
                images_removed += 1
                # Try to delete local file
                local_path = img.get("local_path")
                if local_path and os.path.exists(local_path):
                    os.remove(local_path)
                    files_deleted += 1
                elif local_path:
                    files_missing += 1
            else:
                new_images.append(img)

        if len(new_images) < original_count:
            cameras_affected += 1
            cameras[i]["images"] = new_images

    # Step 4: Save updated cameras.json
    with open(DATA_PATH, "w") as f:
        json.dump(cameras, f, indent=2, ensure_ascii=False)
    print(f"\nSaved updated {DATA_PATH}")

    # Step 5: Print summary
    print("\n=== CLEANUP SUMMARY ===")
    print(f"Duplicate flickr_scrape URLs found: {len(duplicate_urls)}")
    print(f"Cameras affected (had images removed): {cameras_affected}")
    print(f"Total images removed: {images_removed}")
    print(f"Local files deleted: {files_deleted}")
    print(f"Local files not found (already missing): {files_missing}")


if __name__ == "__main__":
    main()
