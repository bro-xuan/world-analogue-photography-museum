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
  const mfrRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setMfrQuery(filters.manufacturer);
  }, [filters.manufacturer]);

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

  const fs = {
    sm: "max(13px, 1.25vh)",
    pill: "max(13px, 1.2vh)",
    inputPad: "max(6px, 0.55vh) max(12px, 1vh)",
    pillPad: "max(4px, 0.4vh) max(10px, 0.95vh)",
  };

  return (
    <div className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-neutral-200 shadow-sm">
      {/* Row 1: close, search, country, manufacturer, count, clear */}
      <div
        className="flex items-center w-full"
        style={{ gap: "max(10px, 0.9vh)", padding: "max(8px, 0.7vh) max(16px, 1.4vh)" }}
      >
        <button
          onClick={onClose}
          className="shrink-0 flex items-center justify-center rounded-full hover:bg-neutral-100 transition-colors text-neutral-500 hover:text-neutral-900"
          style={{ width: "max(28px, 2.6vh)", height: "max(28px, 2.6vh)" }}
          aria-label="Close browse mode"
        >
          <svg
            viewBox="0 0 16 16"
            fill="none"
            style={{ width: "max(14px, 1.3vh)", height: "max(14px, 1.3vh)" }}
          >
            <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>

        <div className="flex-1 relative" style={{ maxWidth: "max(320px, 25vw)" }}>
          <input
            type="text"
            placeholder="Search cameras..."
            defaultValue={filters.search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full border border-neutral-200 rounded-lg focus:outline-none focus:border-neutral-400 bg-white"
            style={{ padding: fs.inputPad, fontSize: fs.sm }}
          />
        </div>

        <select
          value={filters.country}
          onChange={(e) => update({ country: e.target.value })}
          className="shrink-0 border border-neutral-200 rounded-lg bg-white focus:outline-none focus:border-neutral-400"
          style={{ padding: fs.inputPad, fontSize: fs.sm }}
        >
          <option value="">All countries</option>
          {countries.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <div ref={mfrRef} className="relative shrink-0">
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
            className="border border-neutral-200 rounded-lg bg-white focus:outline-none focus:border-neutral-400"
            style={{ padding: fs.inputPad, fontSize: fs.sm, width: "max(140px, 12vw)" }}
          />
          {mfrOpen && filteredMfrs.length > 0 && (
            <div
              className="absolute top-full left-0 mt-1 overflow-y-auto bg-white border border-neutral-200 rounded-lg shadow-lg z-50"
              style={{ maxHeight: "min(300px, 20vh)", width: "max(200px, 18vh)" }}
            >
              {filteredMfrs.map((m) => (
                <button
                  key={m}
                  onClick={() => {
                    update({ manufacturer: m });
                    setMfrQuery(m);
                    setMfrOpen(false);
                  }}
                  className={`block w-full text-left hover:bg-neutral-50 ${
                    filters.manufacturer === m ? "bg-neutral-100 font-medium" : ""
                  }`}
                  style={{ padding: "max(6px, 0.55vh) max(12px, 1vh)", fontSize: fs.sm }}
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="shrink-0 flex items-center ml-auto" style={{ gap: "max(12px, 1.1vh)" }}>
          <span className="text-neutral-400 tabular-nums whitespace-nowrap" style={{ fontSize: fs.sm }}>
            {resultCount.toLocaleString()} cameras
          </span>
          {hasFilters && (
            <button
              onClick={clearAll}
              className="text-neutral-400 hover:text-neutral-700 transition-colors whitespace-nowrap"
              style={{ fontSize: fs.sm }}
            >
              Clear all
            </button>
          )}
        </div>
      </div>

      {/* Row 2: format pills + decade pills */}
      <div
        className="flex items-center border-t border-neutral-100 w-full"
        style={{ gap: "max(10px, 0.9vh)", padding: "max(6px, 0.55vh) max(16px, 1.4vh)" }}
      >
        {/* Format pills */}
        <div className="flex items-center flex-wrap" style={{ gap: "max(5px, 0.45vh)" }}>
          {formats.map((fmt) => (
            <button
              key={fmt}
              onClick={() => toggleFormat(fmt)}
              className={`shrink-0 rounded-full border transition-colors ${
                filters.formats.has(fmt)
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              }`}
              style={{ padding: fs.pillPad, fontSize: fs.pill }}
            >
              {fmt}
            </button>
          ))}
        </div>

        <div className="w-px bg-neutral-200 shrink-0" style={{ height: "max(18px, 1.7vh)" }} />

        {/* Decade pills */}
        <div className="flex items-center flex-wrap" style={{ gap: "max(5px, 0.45vh)" }}>
          {decades.map((d) => (
            <button
              key={d}
              onClick={() => toggleDecade(d)}
              className={`shrink-0 rounded-full border transition-colors ${
                filters.decades.has(d)
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              }`}
              style={{ padding: fs.pillPad, fontSize: fs.pill }}
            >
              {d}s
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
