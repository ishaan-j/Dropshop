"use client";

import { useState } from "react";
import { ErrorBox, Loading, Pill } from "@/components/ui";
import { useResource } from "@/components/use-resource";
import { api, money, when } from "@/lib/api";
import type { VaultView } from "@/types";

type Phantom = {
  isPhantom?: boolean;
  publicKey?: { toString(): string };
  connect: () => Promise<{ publicKey: { toString(): string } }>;
  signTransaction: (tx: unknown) => Promise<{ serialize: () => Uint8Array }>;
};

export default function VaultPage() {
  const { data, error, loading, reload } = useResource<VaultView>("/vault");
  const [sol, setSol] = useState("0.01");
  const [usd, setUsd] = useState("0");
  const [note, setNote] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function wallet(): Phantom | null {
    if (typeof window === "undefined") return null;
    return (window as unknown as { solana?: Phantom }).solana ?? null;
  }

  async function connect() {
    setActionError(null);
    const provider = wallet();
    if (!provider) {
      setActionError("No injected wallet was found. Install Phantom and switch it to Devnet.");
      return;
    }
    const response = await provider.connect();
    await api("/vault/wallet", {
      method: "POST",
      body: JSON.stringify({ address: response.publicKey.toString() }),
    });
    setNote("Public address saved. The private key stayed in the wallet.");
    await reload();
  }

  async function deposit() {
    setBusy(true);
    setActionError(null);
    setNote(null);
    const provider = wallet();
    if (!provider?.publicKey) {
      setActionError("Connect the wallet first.");
      setBusy(false);
      return;
    }
    if (!data?.vault_address || !data.rpc_url) {
      setActionError(data?.detail ?? "Vault address is not configured.");
      setBusy(false);
      return;
    }
    if (!data.rpc_url.includes("devnet")) {
      setActionError("Refusing a non-Devnet RPC.");
      setBusy(false);
      return;
    }
    let signature = "";
    try {
      const solana = await import("@solana/web3.js");
      const connection = new solana.Connection(data.rpc_url, "confirmed");
      const from = new solana.PublicKey(provider.publicKey.toString());
      const lamports = Math.round(Number(sol) * solana.LAMPORTS_PER_SOL);
      if (!Number.isFinite(lamports) || lamports <= 0) throw new Error("Enter a Devnet SOL amount greater than zero.");
      const tx = new solana.Transaction().add(
        solana.SystemProgram.transfer({
          fromPubkey: from,
          toPubkey: new solana.PublicKey(data.vault_address),
          lamports,
        }),
      );
      tx.feePayer = from;
      const latest = await connection.getLatestBlockhash("confirmed");
      tx.recentBlockhash = latest.blockhash;
      const signed = await provider.signTransaction(tx);
      signature = await connection.sendRawTransaction(signed.serialize());
      await connection.confirmTransaction(
        { signature, blockhash: latest.blockhash, lastValidBlockHeight: latest.lastValidBlockHeight },
        "confirmed",
      );
      const saved = await api<{ note: string; signature: string | null }>("/vault/confirm", {
        method: "POST",
        body: JSON.stringify({ signature, intended_cents: Math.round(Number(usd || "0") * 100) }),
      });
      setNote(saved.note);
      await reload();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Transfer failed";
      setActionError(
        signature
          ? `${message} A signature was created (${signature}) but DropShop did not verify it, so it is not listed as confirmed.`
          : message,
      );
    } finally {
      setBusy(false);
    }
  }

  async function demoEarmark() {
    setBusy(true);
    setActionError(null);
    try {
      const saved = await api<{ note: string }>("/vault/demo-allocation", {
        method: "POST",
        body: JSON.stringify({ amount_cents: Math.round(Number(usd) * 100) }),
      });
      setNote(saved.note);
      await reload();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Could not record the demo earmark");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Loading label="Loading vault" />;
  if (error && !data) return <ErrorBox message={error} />;
  if (!data) return null;

  return (
    <>
      <p className="muted">Savings vault</p>
      <h1 className="page-title">Devnet, separate from the refund</h1>
      <div className="banner">
        A retailer refund returns on the original payment method. It does not move itself onto Solana.
        A deposit here is Devnet SOL you sign. It has no real-money value. No Anchor program is deployed.
      </div>
      {note && <div className="banner">{note}</div>}
      {actionError && <ErrorBox message={actionError} />}
      <div className="metrics">
        <article className="metric"><span>Network</span><strong style={{ fontSize: 22 }}>{data.network}</strong></article>
        <article className="metric"><span>Status</span><strong style={{ fontSize: 18 }}><Pill value={data.mode} /></strong></article>
        <article className="metric">
          <span>Vault balance</span>
          <strong style={{ fontSize: 18 }}>{data.balance_verified ? `${data.balance_lamports} lamports` : "Not verified"}</strong>
        </article>
        <article className="metric"><span>Program</span><strong style={{ fontSize: 18 }}>{data.program_deployed ? "Deployed" : "None"}</strong></article>
      </div>
      <section className="panel">
        <p>{data.detail}</p>
        <p className="mono" style={{ wordBreak: "break-all" }}>Wallet: {data.wallet_address ?? "not connected"}</p>
        <p className="mono" style={{ wordBreak: "break-all" }}>Vault: {data.vault_address ?? "not configured"}</p>
        <div className="row-actions">
          <button className="btn" onClick={() => void connect()}>Connect wallet</button>
        </div>
        <div className="filters" style={{ marginTop: 12 }}>
          <input value={sol} onChange={(event) => setSol(event.target.value)} aria-label="Devnet SOL" />
          <input value={usd} onChange={(event) => setUsd(event.target.value)} aria-label="USD earmark" />
          <button className="btn primary" disabled={busy} onClick={() => void deposit()}>Authorize Devnet deposit</button>
          <button className="btn" disabled={busy} onClick={() => void demoEarmark()}>Record demo earmark</button>
        </div>
        <p className="muted">The first number is Devnet SOL. The second is a USD earmark of recovered savings, and it cannot exceed matched refunds.</p>
      </section>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Allocations</h2>
        {data.allocations.length === 0 ? (
          <p className="muted">No allocations recorded.</p>
        ) : (
          <div className="stack">
            {data.allocations.map((item) => (
              <article key={item.id}>
                <div>{money(item.amount_cents)} · {item.kind} · <Pill value={item.data_origin} /> · {item.confirmed ? "verified" : "not on-chain"}</div>
                <div className="muted">{when(item.created_at)} {item.lamports != null ? `· ${item.lamports} lamports` : ""}</div>
                <div>{item.note}</div>
                {item.signature && item.confirmed && (
                  <a href={`https://explorer.solana.com/tx/${item.signature}?cluster=devnet`} target="_blank" rel="noreferrer">
                    {item.signature}
                  </a>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
