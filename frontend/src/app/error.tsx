"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6">
      <h1 className="text-3xl font-semibold tracking-tight text-[#12372A]">Something went wrong.</h1>
      <p className="mt-3 text-sm leading-6 text-[#5E6B63]">The demo data is still in this browser. Try the page again.</p>
      <button type="button" onClick={reset} className="mt-6 h-10 w-fit rounded-lg bg-[#12372A] px-4 text-sm font-semibold text-white">
        Try again
      </button>
    </main>
  );
}
