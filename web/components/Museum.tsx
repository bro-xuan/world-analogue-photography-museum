"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import FreeCanvas from "./FreeCanvas";
import FilterBar, {
  FilterState,
  EMPTY_FILTER,
  isFilterEmpty,
} from "./browse/FilterBar";
import BrowseGrid from "./browse/BrowseGrid";
import { CameraEntry, fetchLandingData } from "@/lib/cameras";
import { useMuseum } from "@/contexts/MuseumContext";

type Mode = "canvas" | "entering-browse" | "browse" | "leaving-browse";

const TRANSITION_MS = 600;

export default function Museum() {
  const [cameras, setCameras] = useState<CameraEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Fetch landing data client-side
  useEffect(() => {
    fetchLandingData()
      .then((data) => {
        setCameras(data.cameras);
        setTotal(data.meta.total);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load landing data:", err);
        setLoading(false);
      });
  }, []);

  const manufacturers = useMemo(
    () => new Set(cameras.map((c) => c.manufacturer)).size,
    [cameras]
  );

  const [mode, setMode] = useState<Mode>(() => {
    if (typeof window !== "undefined" && window.location.hash === "#browse") return "browse";
    return "canvas";
  });
  const [filters, setFilters] = useState<FilterState>({
    ...EMPTY_FILTER,
    formats: new Set(),
    decades: new Set(),
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

    const filtered = cameras.filter((cam) => {
      if (filters.country && cam.country !== filters.country) return false;
      if (filters.formats.size > 0 && (!cam.format || !filters.formats.has(cam.format)))
        return false;
      if (
        filters.manufacturer &&
        cam.manufacturer.toLowerCase() !== filters.manufacturer.toLowerCase()
      )
        return false;
      if (filters.decades.size > 0 && cam.year) {
        const decade = Math.floor(cam.year / 10) * 10;
        if (!filters.decades.has(decade)) return false;
      }
      if (filters.decades.size > 0 && !cam.year) return false;
      if (searchLower && !cam.name.toLowerCase().includes(searchLower))
        return false;
      return true;
    });

    // Sort by year when decade filters are active
    if (filters.decades.size > 0) {
      filtered.sort((a, b) => (a.year ?? 0) - (b.year ?? 0));
    }

    return filtered;
  }, [cameras, filters]);

  const enterBrowse = useCallback(() => {
    setMode("entering-browse");
    window.history.pushState(null, "", "#browse");
    setTimeout(() => setMode("browse"), TRANSITION_MS);
  }, []);

  const leaveBrowse = useCallback(() => {
    if (mode !== "browse") return;
    setMode("leaving-browse");
    setTimeout(() => {
      setMode("canvas");
      setFilters({ ...EMPTY_FILTER, formats: new Set(), decades: new Set() });
    }, TRANSITION_MS);
    // Remove the hash without adding a history entry
    window.history.replaceState(null, "", window.location.pathname);
  }, [mode]);

  // Handle browser back button: #browse -> no hash means leave browse
  useEffect(() => {
    const onPopState = () => {
      if (window.location.hash !== "#browse" && mode === "browse") {
        setMode("leaving-browse");
        setTimeout(() => {
          setMode("canvas");
          setFilters({ ...EMPTY_FILTER, formats: new Set(), decades: new Set() });
        }, TRANSITION_MS);
      }
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [mode]);

  // Register leaveBrowse so navbar logo can trigger it
  const { registerLeaveBrowse } = useMuseum();
  useEffect(() => {
    registerLeaveBrowse(leaveBrowse);
  }, [registerLeaveBrowse, leaveBrowse]);

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white">
        <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-900 rounded-full animate-spin" />
      </div>
    );
  }

  const showCanvas = mode === "canvas" || mode === "entering-browse" || mode === "leaving-browse";
  const showBrowse = mode === "browse" || mode === "entering-browse" || mode === "leaving-browse";

  const animDuration = `${TRANSITION_MS}ms`;

  const canvasStyle: React.CSSProperties =
    mode === "entering-browse"
      ? { animation: `slide-up-out ${animDuration} ease-in-out forwards`, pointerEvents: "none" }
      : mode === "leaving-browse"
        ? { animation: `slide-down-in ${animDuration} ease-in-out forwards`, pointerEvents: "none" }
        : {};

  const browseStyle: React.CSSProperties =
    mode === "entering-browse"
      ? { animation: `slide-up-in ${animDuration} ease-in-out forwards`, pointerEvents: "none" }
      : mode === "leaving-browse"
        ? { animation: `slide-down-out ${animDuration} ease-in-out forwards`, pointerEvents: "none" }
        : {};

  return (
    <>
      {/* Canvas mode */}
      {showCanvas && (
        <div
          className="fixed inset-0 z-30"
          style={canvasStyle}
        >
          <FreeCanvas
            cameras={cameras}
            total={total}
            manufacturers={manufacturers}
            onBrowse={enterBrowse}
          />
        </div>
      )}

      {/* Browse mode */}
      {showBrowse && (
        <div
          className="fixed left-0 right-0 bottom-0 bg-white z-40 overflow-y-auto"
          style={{ top: "max(60px, 6.5vh)", ...browseStyle }}
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
          <div style={{ paddingTop: "max(8px, 0.7vh)" }}>
            <BrowseGrid cameras={filteredCameras} />
          </div>
        </div>
      )}
    </>
  );
}
