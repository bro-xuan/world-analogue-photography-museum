import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center px-4">
      <div className="text-center">
        <p className="text-xs font-semibold tracking-widest text-neutral-400 uppercase mb-3">
          404
        </p>
        <h1 className="font-display text-3xl md:text-4xl font-bold text-neutral-900 mb-3">
          Page not found
        </h1>
        <p className="text-neutral-500 mb-8 max-w-sm mx-auto">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/"
          className="inline-block px-6 py-2.5 text-sm font-medium rounded-full bg-neutral-900 text-white hover:bg-neutral-800 transition-colors"
        >
          Back to the museum
        </Link>
      </div>
    </div>
  );
}
