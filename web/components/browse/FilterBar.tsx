"use client";

import { useRef, useState, useEffect, useCallback } from "react";

export interface FilterState {
  country: string;
  formats: Set<string>;
  manufacturer: string;
  decades: Set<number>;
  search: string;
}

export const EMPTY_FILTER: FilterState = {
  country: "",
  formats: new Set(),
  manufacturer: "",
  decades: new Set(),
  search: "",
};

export function isFilterEmpty(f: FilterState): boolean {
  return (
    !f.country &&
    f.formats.size === 0 &&
    !f.manufacturer &&
    f.decades.size === 0 &&
    !f.search
  );
}

interface FilterBarProps {
  filters: FilterState;
  onChange: (f: FilterState) => void;
  onClose: () => void;
  resultCount: number;
  countries: string[];
  formats: string[];
  manufacturers: string[];
  decades: number[];
}

export default function FilterBar({
  filters,
  onChange,
  onClose,
  resultCount,
  countries,
  formats,
  manufacturers,
  decades,
}: FilterBarProps) {
  const [mfrQuery, setMfrQuery] = useState(filters.manufacturer);
  const [mfrOpen, setMfrOpen] = useState(false);
  const [filtersExpanded, setFiltersExpanded] = useState(false);
  const mfrRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync mfrQuery when filters.manufacturer changes externally (e.g. clear all)
  useEffect(() => {
    setMfrQuery(filters.manufacturer);
  }, [filters.manufacturer]);

  // Close manufacturer dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (mfrRef.current && !mfrRef.current.contains(e.target as Node)) {
        setMfrOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const update = useCallback(
    (partial: Partial<FilterState>) => {
      onChange({ ...filters, ...partial });
    },
    [filters, onChange]
  );

  const onSearchChange = useCallback(
    (value: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        update({ search: value });
      }, 150);
    },
    [update]
  );

  const toggleFormat = (fmt: string) => {
    const next = new Set(filters.formats);
    if (next.has(fmt)) next.delete(fmt);
    else next.add(fmt);
    update({ formats: next });
  };

  const toggleDecade = (decade: number) => {
    const next = new Set(filters.decades);
    if (next.has(decade)) next.delete(decade);
    else next.add(decade);
    update({ decades: next });
  };

  const isDecadeActive = (decade: number) => {
    return filters.decades.has(decade);
  };

  const clearAll = () => {
    onChange({ ...EMPTY_FILTER, formats: new Set(), decades: new Set() });
    setMfrQuery("");
  };

  const filteredMfrs = mfrQuery
    ? manufacturers.filter((m) =>
        m.toLowerCase().includes(mfrQuery.toLowerCase())
      )
    : manufacturers;

  const hasFilters = !isFilterEmpty(filters);

  return (
    <div className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-neutral-200 shadow-sm">
      {/* Top row: close, search, count, clear */}
      <div className="flex items-center gap-3 px-4 py-3 max-w-screen-2xl mx-auto">
        <button
          onClick={onClose}
          className="shrink-0 w-8 h-8 flex items-center justify-center rounded-full hover:bg-neutral-100 transition-colors text-neutral-500 hover:text-neutral-900"
          aria-label="Close browse mode"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>

        <div className="flex-1 relative">
          <input
            type="text"
            placeholder="Search cameras..."
            defaultValue={filters.search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full px-3 py-1.5 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:border-neutral-400 bg-white"
          />
        </div>

        <span className="shrink-0 text-xs text-neutral-400 tabular-nums">
          {resultCount.toLocaleString()} camera{resultCount !== 1 ? "s" : ""}
        </span>

        {/* Mobile filter toggle */}
        <button
          onClick={() => setFiltersExpanded(!filtersExpanded)}
          className="shrink-0 md:hidden px-3 py-1.5 text-xs font-medium border border-neutral-200 rounded-lg hover:bg-neutral-50 transition-colors"
        >
          Filters{hasFilters ? " *" : ""}
        </button>

        {hasFilters && (
          <button
            onClick={clearAll}
            className="shrink-0 text-xs text-neutral-400 hover:text-neutral-700 transition-colors"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Filter controls row — always visible on md+, toggled on mobile */}
      <div
        className={`border-t border-neutral-100 px-4 py-2 max-w-screen-2xl mx-auto ${
          filtersExpanded ? "block" : "hidden md:block"
        }`}
      >
        <div className="flex flex-wrap items-center gap-3">
          {/* Country dropdown */}
          <select
            value={filters.country}
            onChange={(e) => update({ country: e.target.value })}
            className="text-xs border border-neutral-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-neutral-400"
          >
            <option value="">All countries</option>
            {countries.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          {/* Manufacturer autocomplete */}
          <div ref={mfrRef} className="relative">
            <input
              type="text"
              placeholder="Manufacturer..."
              value={mfrQuery}
              onChange={(e) => {
                setMfrQuery(e.target.value);
                setMfrOpen(true);
                if (!e.target.value) update({ manufacturer: "" });
              }}
              onFocus={() => setMfrOpen(true)}
              className="text-xs border border-neutral-200 rounded-lg px-2 py-1.5 w-36 bg-white focus:outline-none focus:border-neutral-400"
            />
            {mfrOpen && filteredMfrs.length > 0 && (
              <div className="absolute top-full left-0 mt-1 w-48 max-h-60 overflow-y-auto bg-white border border-neutral-200 rounded-lg shadow-lg z-50">
                {filteredMfrs.map((m) => (
                  <button
                    key={m}
                    onClick={() => {
                      update({ manufacturer: m });
                      setMfrQuery(m);
                      setMfrOpen(false);
                    }}
                    className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-neutral-50 ${
                      filters.manufacturer === m
                        ? "bg-neutral-100 font-medium"
                        : ""
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Separator */}
          <div className="hidden md:block w-px h-5 bg-neutral-200" />

          {/* Format pills */}
          <div className="flex flex-wrap gap-1.5">
            {formats.map((fmt) => (
              <button
                key={fmt}
                onClick={() => toggleFormat(fmt)}
                className={`px-2.5 py-1 text-[11px] rounded-full border transition-colors ${
                  filters.formats.has(fmt)
                    ? "bg-neutral-900 text-white border-neutral-900"
                    : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
                }`}
              >
                {fmt}
              </button>
            ))}
          </div>

          {/* Separator */}
          <div className="hidden md:block w-px h-5 bg-neutral-200" />

          {/* Decade pills */}
          <div className="flex flex-wrap gap-1.5">
            {decades.map((d) => (
              <button
                key={d}
                onClick={() => toggleDecade(d)}
                className={`px-2.5 py-1 text-[11px] rounded-full border transition-colors ${
                  isDecadeActive(d)
                    ? "bg-neutral-900 text-white border-neutral-900"
                    : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
                }`}
              >
                {d}s
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
