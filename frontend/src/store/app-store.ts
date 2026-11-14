"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Claim, LedgerState, User } from "../types";
import { applyDemoStage, resetDemoRun, type DemoStage } from "../lib/demo-reducer";
import { createSeed, defaultSettings, defaultUser, type UserSettings } from "../lib/mock-data";
import { verifyLedger } from "../lib/verify-ledger";

verifyLedger();

interface AppState extends LedgerState {
  user: User;
  settings: UserSettings;
  emailConnected: boolean;
  bankConnected: boolean;
  walletConnected: boolean;
  onboarded: boolean;
  readNotificationIds: string[];
  epoch: number;
  applyLedger: (ledger: LedgerState) => void;
  applyDemoStage: (stage: DemoStage) => void;
  resetDemoRun: () => void;
  resetDemo: () => void;
  upsertClaim: (claim: Claim) => void;
  updateProfile: (profile: { name: string; email: string }) => void;
  patchUser: (patch: Partial<User>) => void;
  updateSettings: (patch: Partial<UserSettings>) => void;
  setEmailConnected: (value: boolean) => void;
  setBankConnected: (value: boolean) => void;
  setWalletConnected: (value: boolean) => void;
  completeOnboarding: () => void;
  markNotificationsRead: () => void;
}

const seed = createSeed();

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      ...seed,
      user: defaultUser,
      settings: defaultSettings,
      emailConnected: false,
      bankConnected: false,
      walletConnected: false,
      onboarded: false,
      readNotificationIds: [],
      epoch: 0,
      applyLedger: (ledger) => set(ledger),
      applyDemoStage: (stage) => set((state) => applyDemoStage(state, stage)),
      resetDemoRun: () => set((state) => resetDemoRun(state)),
      resetDemo: () =>
        set((state) => ({
          ...state,
          ...createSeed(),
          user: defaultUser,
          settings: defaultSettings,
          emailConnected: true,
          bankConnected: true,
          walletConnected: true,
          onboarded: true,
          readNotificationIds: [],
          epoch: state.epoch + 1,
        })),
      upsertClaim: (claim) =>
        set((state) => ({
          claims: state.claims.some((item) => item.id === claim.id)
            ? state.claims.map((item) => (item.id === claim.id ? claim : item))
            : [claim, ...state.claims],
          purchases: state.purchases.map((purchase) => {
            if (purchase.id !== claim.purchase_id) return purchase;
            if (claim.status === "refund_received") return { ...purchase, status: "claimed" as const };
            if (claim.status === "rejected" || claim.status === "failed") return purchase;
            return { ...purchase, status: "claim_pending" as const };
          }),
        })),
      updateProfile: ({ name, email }) =>
        set((state) => ({ user: { ...state.user, name: name.trim(), email: email.trim() } })),
      patchUser: (patch) => set((state) => ({ user: { ...state.user, ...patch } })),
      updateSettings: (patch) => set((state) => ({ settings: { ...state.settings, ...patch } })),
      setEmailConnected: (value) => set({ emailConnected: value }),
      setBankConnected: (value) => set({ bankConnected: value }),
      setWalletConnected: (value) => set({ walletConnected: value }),
      completeOnboarding: () =>
        set({ emailConnected: true, bankConnected: true, walletConnected: true, onboarded: true }),
      markNotificationsRead: () =>
        set((state) => ({ readNotificationIds: state.activity.map((item) => item.id) })),
    }),
    {
      name: "dropshop-v1",
      skipHydration: true,
      version: 1,
      partialize: (state) => ({
        user: state.user,
        settings: state.settings,
        purchases: state.purchases,
        claims: state.claims,
        activity: state.activity,
        vaultTransactions: state.vaultTransactions,
        bankTransactions: state.bankTransactions,
        emailConnected: state.emailConnected,
        bankConnected: state.bankConnected,
        walletConnected: state.walletConnected,
        onboarded: state.onboarded,
        readNotificationIds: state.readNotificationIds,
      }),
      merge: (persisted, current) => {
        if (!persisted || typeof persisted !== "object") return current;
        const data = persisted as Partial<AppState>;
        if (
          !Array.isArray(data.purchases) ||
          !Array.isArray(data.claims) ||
          !Array.isArray(data.vaultTransactions) ||
          !Array.isArray(data.bankTransactions) ||
          !Array.isArray(data.activity)
        ) {
          return current;
        }
        return { ...current, ...data, epoch: 0 };
      },
    },
  ),
);
