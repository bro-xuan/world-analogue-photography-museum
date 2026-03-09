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
        <button className="mt-6 px-5 py-2 text-sm font-medium text-neutral-900 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer">
          Browse collection &darr;
        </button>
      </div>
    </div>
  );
}
