"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import FreeCanvas from "./FreeCanvas";
import FilterBar, {
  FilterState,
  EMPTY_FILTER,
  isFilterEmpty,
} from "./browse/FilterBar";
import BrowseGrid from "./browse/BrowseGrid";
import { CameraEntry } from "@/lib/cameras";

interface MuseumProps {
  cameras: CameraEntry[];
  total: number;
  manufacturers: number;
  detailIdList: string[];
}

type Mode = "canvas" | "entering-browse" | "browse" | "leaving-browse";

export default function Museum({
  cameras,
  total,
  manufacturers,
  detailIdList,
}: MuseumProps) {
  const detailIds = useMemo(() => new Set(detailIdList), [detailIdList]);

  const [mode, setMode] = useState<Mode>("canvas");
  const [filters, setFilters] = useState<FilterState>({
    ...EMPTY_FILTER,
    formats: new Set(),
  });

  // Pre-compute filter options
  const filterOptions = useMemo(() => {
    const countrySet = new Set<string>();
    const formatSet = new Set<string>();
    const mfrSet = new Set<string>();
    const decadeSet = new Set<number>();

    for (const cam of cameras) {
      if (cam.country) countrySet.add(cam.country);
      if (cam.format) formatSet.add(cam.format);
      if (cam.manufacturer) mfrSet.add(cam.manufacturer);
      if (cam.year) {
        const decade = Math.floor(cam.year / 10) * 10;
        decadeSet.add(decade);
      }
    }

    return {
      countries: Array.from(countrySet).sort(),
      formats: Array.from(formatSet).sort(),
      manufacturers: Array.from(mfrSet).sort(),
      decades: Array.from(decadeSet).sort(),
    };
  }, [cameras]);

  // Filter cameras
  const filteredCameras = useMemo(() => {
    if (isFilterEmpty(filters)) return cameras;

    const searchLower = filters.search.toLowerCase();

    return cameras.filter((cam) => {
      if (filters.country && cam.country !== filters.country) return false;
      if (filters.formats.size > 0 && (!cam.format || !filters.formats.has(cam.format)))
        return false;
      if (
        filters.manufacturer &&
        cam.manufacturer.toLowerCase() !== filters.manufacturer.toLowerCase()
      )
        return false;
      if (filters.decadeStart !== null && cam.year) {
        const decade = Math.floor(cam.year / 10) * 10;
        const end = filters.decadeEnd ?? filters.decadeStart;
        if (decade < filters.decadeStart || decade > end) return false;
      }
      if (filters.decadeStart !== null && !cam.year) return false;
      if (searchLower && !cam.name.toLowerCase().includes(searchLower))
        return false;
      return true;
    });
  }, [cameras, filters]);

  const enterBrowse = useCallback(() => {
    setMode("entering-browse");
    // After CSS transition, switch to full browse
    setTimeout(() => setMode("browse"), 300);
  }, []);

  const leaveBrowse = useCallback(() => {
    setMode("leaving-browse");
    setTimeout(() => {
      setMode("canvas");
      setFilters({ ...EMPTY_FILTER, formats: new Set() });
    }, 300);
  }, []);

  // Scroll to top when entering browse mode
  useEffect(() => {
    if (mode === "browse") {
      window.scrollTo(0, 0);
    }
  }, [mode]);

  const showCanvas = mode === "canvas" || mode === "entering-browse" || mode === "leaving-browse";
  const showBrowse = mode === "browse" || mode === "entering-browse" || mode === "leaving-browse";

  // Canvas fades out via opacity on its own fixed container — no transform
  // wrapper needed (transform on a parent breaks position:fixed children).
  const canvasOpacity =
    mode === "entering-browse" ? 0 : mode === "leaving-browse" ? 1 : 1;

  return (
    <>
      {/* Canvas mode — rendered without a wrapper so fixed positioning works */}
      {showCanvas && (
        <div
          className="fixed inset-0 z-30 transition-opacity duration-300 ease-in-out pointer-events-auto"
          style={{ opacity: canvasOpacity }}
        >
          <FreeCanvas
            cameras={cameras}
            total={total}
            manufacturers={manufacturers}
            detailIds={detailIds}
            onBrowse={enterBrowse}
          />
        </div>
      )}

      {/* Browse mode */}
      {showBrowse && (
        <div
          className="fixed inset-0 bg-white z-40 overflow-y-auto transition-opacity duration-300 ease-in-out"
          style={{
            opacity: mode === "browse" ? 1 : 0,
          }}
        >
          <FilterBar
            filters={filters}
            onChange={setFilters}
            onClose={leaveBrowse}
            resultCount={filteredCameras.length}
            countries={filterOptions.countries}
            formats={filterOptions.formats}
            manufacturers={filterOptions.manufacturers}
            decades={filterOptions.decades}
          />
          {/* Grid with top padding for filter bar */}
          <div className="pt-28 md:pt-24">
            <BrowseGrid cameras={filteredCameras} detailIds={detailIds} />
          </div>
        </div>
      )}
    </>
  );
}
