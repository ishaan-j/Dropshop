import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#5E6B63]">404</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[#12372A]">That page is not in DropShop.</h1>
      <p className="mt-3 text-sm leading-6 text-[#5E6B63]">The link may be old. The dashboard and the live demo are still here.</p>
      <div className="mt-6 flex gap-4 text-sm font-semibold">
        <Link href="/" className="underline-offset-4 hover:underline">Home</Link>
        <Link href="/dashboard" className="underline-offset-4 hover:underline">Dashboard</Link>
      </div>
    </main>
  );
}
