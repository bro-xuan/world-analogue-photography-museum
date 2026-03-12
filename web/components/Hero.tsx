interface HeroProps {
  total: number;
  manufacturers: number;
}

export default function Hero({ total, manufacturers }: HeroProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
      <div className="bg-white px-16 py-14 text-center pointer-events-auto">
        <h1 className="font-display text-4xl md:text-6xl font-bold text-neutral-900 leading-tight tracking-tight">
          World Analogue
          <br />
          Photography Museum
        </h1>
        <p className="mt-4 text-sm md:text-base text-neutral-500">
          {manufacturers.toLocaleString()} brands &middot;{" "}
          {total.toLocaleString()} cameras
        </p>
        <div className="mt-6 flex flex-col items-center gap-4">
          <button className="px-5 py-2 text-sm font-medium text-neutral-900 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer">
            Browse collection &darr;
          </button>
          <a
            href="https://x.com/Erc721_stefan"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-neutral-400 hover:text-neutral-600 transition-colors flex items-center gap-1"
          >
            <svg viewBox="0 0 24 24" className="w-3 h-3 fill-current" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
            by @Erc721_stefan
          </a>
        </div>
      </div>
    </div>
  );
}
