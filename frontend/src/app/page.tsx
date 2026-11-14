// Placeholder dashboard (Layer 1 owner replaces this). See frontend/LAYER.md for the task list.
import { api, formatCents } from "@/lib/api";

export default async function Home() {
  const [savings, purchases] = await Promise.all([
    api.savings().catch(() => null),
    api.purchases().catch(() => []),
  ]);

  return (
    <main className="mx-auto w-full max-w-4xl p-10 font-sans">
      <h1 className="text-3xl font-semibold tracking-tight">Dropshot</h1>
      <p className="mt-1 text-zinc-500">Your purchases keep getting cheaper. Now so do you.</p>

      <section className="mt-8 rounded-xl border p-6">
        <h2 className="text-sm uppercase text-zinc-500">Recovered so far</h2>
        <p className="mt-1 text-4xl font-bold">
          {savings ? formatCents(savings.total_recovered_cents) : "API offline: start the backend"}
        </p>
      </section>

      <section className="mt-6 grid gap-3">
        {purchases.map((p) => (
          <div key={p.id} className="flex justify-between rounded-lg border p-4">
            <span>
              {p.product_name} <span className="text-zinc-500">· {p.retailer}</span>
            </span>
            <span className="font-mono text-sm">{p.status}</span>
          </div>
        ))}
      </section>
    </main>
  );
}
