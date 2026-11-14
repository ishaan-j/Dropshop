import Link from "next/link";

const STEPS = [
  ["Purchase", "An order confirmation is the start."],
  ["Monitor", "Prices are checked from a named source."],
  ["Detect", "A lower price becomes a drop event."],
  ["Verify", "Policy, window, and exclusions decide eligibility."],
  ["Claim", "A claim is prepared. You approve it."],
  ["Recover", "A refund is recorded only when a source confirms it."],
  ["Save", "You can earmark savings, then sign a Devnet transfer yourself."],
];

export default function Home() {
  return (
    <div className="landing">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="brand">DropShop</span>
        <Link className="btn primary" href="/app">
          Open the dashboard
        </Link>
      </header>
      <section className="hero">
        <div>
          <p className="muted">Price recovery, with the receipt trail left visible</p>
          <h1>Find the drop. See why it qualifies. Keep the refund yours to approve.</h1>
        </div>
        <p className="lede">
          DropShop watches purchases, compares them with an authorized price, and checks the
          retailer&apos;s adjustment window. A lower price is not a refund. You approve every claim,
          and a Solana transfer is a separate step you sign.
        </p>
      </section>
      <section className="steps">
        {STEPS.map(([title, copy]) => (
          <article className="step" key={title}>
            <b>{title}</b>
            {copy}
          </article>
        ))}
      </section>
      <section className="agents">
        <article className="panel">
          <h2 className="serif" style={{ marginTop: 0 }}>Four agents, one trail</h2>
          <p>Receipt, price, eligibility, and claim. Each run is stored with a time and a result. The Agent Center reads those records. It does not play a canned animation.</p>
        </article>
        <article className="panel">
          <h2 className="serif" style={{ marginTop: 0 }}>What &quot;demo&quot; means</h2>
          <p>Without Gmail, Gemini, Nessie, or a database, you can run a labeled scenario: sample emails and the Harbor &amp; Co catalog, a store that exists only in this app. Those rows stay marked Demo. They are not your inbox and not a live retailer.</p>
          <p><Link href="/app">Run it from the dashboard →</Link></p>
        </article>
      </section>
    </div>
  );
}
