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
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center px-4 py-20">
      <div className="bg-white rounded-2xl shadow-sm border border-neutral-100 w-full max-w-sm p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="mb-3 flex justify-center">
            <img src="https://cdn.buymeacoffee.com/buttons/bmc-new-btn-logo.svg" alt="" width="40" height="40" />
          </div>
          <h1 className="text-lg font-semibold text-neutral-900">
            Support this project
          </h1>
          <p className="text-sm text-neutral-500 mt-1.5 leading-relaxed">
            Running a museum of {(10599).toLocaleString()} cameras takes
            coffee. Yours helps keep it going.
          </p>
        </div>

        {/* Amount picker */}
        <div className="flex items-center justify-center gap-2 mb-4">
          {PRESETS.map((val) => (
            <button
              key={val}
              onClick={() => {
                setAmount(val);
                setShowCustom(false);
              }}
              className={`w-16 h-10 text-sm font-medium rounded-full border transition-all cursor-pointer ${
                !showCustom && amount === val
                  ? "bg-neutral-900 text-white border-neutral-900"
                  : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              }`}
            >
              ${val}
            </button>
          ))}
          <button
            onClick={() => setShowCustom(true)}
            className={`h-10 px-4 text-sm font-medium rounded-full border transition-all cursor-pointer ${
              showCustom
                ? "bg-neutral-900 text-white border-neutral-900"
                : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
            }`}
          >
            Other
          </button>
        </div>

        {/* Custom amount input */}
        {showCustom && (
          <div className="mb-4">
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-neutral-400">
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
                className="w-full pl-7 pr-3 py-2.5 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:border-neutral-400 transition-colors"
              />
            </div>
          </div>
        )}

        {/* Summary */}
        {activeAmount > 0 && (
          <div className="bg-neutral-50 rounded-lg px-4 py-3 mb-6 text-center">
            <span className="text-sm text-neutral-500">
              You&apos;re sending{" "}
              <span className="font-semibold text-neutral-900">
                ${activeAmount}
              </span>
            </span>
          </div>
        )}

        {/* Pay button */}
        <a
          href={`https://buymeacoffee.com/erc721stefan`}
          target="_blank"
          rel="noopener noreferrer"
          className={`w-full flex items-center justify-center gap-2 py-3 text-sm font-medium rounded-full transition-all ${
            activeAmount > 0
              ? "bg-neutral-900 text-white hover:bg-neutral-800 cursor-pointer"
              : "bg-neutral-200 text-neutral-400 pointer-events-none"
          }`}
        >
          <img src="https://cdn.buymeacoffee.com/buttons/bmc-new-btn-logo.svg" alt="" width="18" height="18" />
          Support ${activeAmount || "..."}
        </a>

        {/* Back link */}
        <div className="mt-6 text-center">
          <Link
            href="/"
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors"
          >
            &larr; Back to the museum
          </Link>
        </div>
      </div>
    </div>
  );
}
