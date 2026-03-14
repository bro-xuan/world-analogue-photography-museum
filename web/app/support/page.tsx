"use client";

import { useState } from "react";
import Link from "next/link";

const PRESETS = [3, 5, 10] as const;

export default function SupportPage() {
  const [amount, setAmount] = useState(5);
  const [custom, setCustom] = useState("");
  const [showCustom, setShowCustom] = useState(false);

  const activeAmount = showCustom ? Number(custom) || 0 : amount;

  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center px-4 py-20" style={{ fontSize: "clamp(14px, 1.6vw, 22px)" }}>
      <div className="bg-white rounded-3xl shadow-sm border border-neutral-100" style={{ width: "min(90vw, 36em)", padding: "clamp(32px, 3vw, 56px)" }}>
        {/* Header */}
        <div className="text-center" style={{ marginBottom: "2em" }}>
          <div className="flex justify-center" style={{ marginBottom: "0.8em" }}>
            <img src="https://storage.ko-fi.com/cdn/cup-border.png" alt="" style={{ width: "3.5em", height: "3.5em" }} />
          </div>
          <h1 className="font-semibold text-neutral-900" style={{ fontSize: "1.5em" }}>
            Support this project
          </h1>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "1em", marginTop: "0.5em" }}>
            If you enjoyed roaming around the analog camera museum...
          </p>
        </div>

        {/* Amount picker */}
        <div className="flex items-center justify-center" style={{ gap: "0.6em", marginBottom: "1.2em" }}>
          {PRESETS.map((val) => (
            <button
              key={val}
              onClick={() => {
                setAmount(val);
                setShowCustom(false);
              }}
              className={`font-medium rounded-full border transition-all cursor-pointer ${
                !showCustom && amount === val
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              }`}
              style={{ width: "4em", height: "2.6em", fontSize: "1em" }}
            >
              ${val}
            </button>
          ))}
          <button
            onClick={() => setShowCustom(true)}
            className={`font-medium rounded-full border transition-all cursor-pointer ${
              showCustom
                ? "bg-neutral-900 text-white border-neutral-900"
                : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
            }`}
            style={{ height: "2.6em", padding: "0 1.2em", fontSize: "1em" }}
          >
            Other
          </button>
        </div>

        {/* Custom amount input */}
        {showCustom && (
          <div style={{ marginBottom: "1.2em" }}>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-neutral-400" style={{ fontSize: "1em" }}>
                $
              </span>
              <input
                type="number"
                min="1"
                step="1"
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                placeholder="Enter amount"
                autoFocus
                className="w-full border border-neutral-200 rounded-xl focus:outline-none focus:border-neutral-400 transition-colors"
                style={{ fontSize: "1em", padding: "0.7em 1em 0.7em 2em" }}
              />
            </div>
          </div>
        )}

        {/* Summary */}
        {activeAmount > 0 && (
          <div className="bg-neutral-50 rounded-xl text-center" style={{ padding: "0.8em 1.2em", marginBottom: "1.5em" }}>
            <span className="text-neutral-500" style={{ fontSize: "1em" }}>
              You&apos;re sending{" "}
              <span className="font-semibold text-neutral-900">
                ${activeAmount}
              </span>
            </span>
          </div>
        )}

        {/* Pay button */}
        <a
          href={`https://ko-fi.com/afrodance`}
          target="_blank"
          rel="noopener noreferrer"
          className={`w-full flex items-center justify-center font-medium rounded-full transition-all ${
            activeAmount > 0
              ? "bg-neutral-900 text-white hover:bg-neutral-800 cursor-pointer"
              : "bg-neutral-200 text-neutral-400 pointer-events-none"
          }`}
          style={{ gap: "0.5em", padding: "0.8em 0", fontSize: "1em" }}
        >
          <img src="https://storage.ko-fi.com/cdn/cup-border.png" alt="" style={{ width: "1.3em", height: "1.3em" }} />
          Support ${activeAmount || "..."}
        </a>

        {/* Back link */}
        <div className="text-center" style={{ marginTop: "1.8em" }}>
          <Link
            href="/"
            className="text-neutral-400 hover:text-neutral-600 transition-colors"
            style={{ fontSize: "0.8em" }}
          >
            &larr; Back to the museum
          </Link>
        </div>
      </div>
    </div>
  );
}
