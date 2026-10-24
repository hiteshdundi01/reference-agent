import { useSyncExternalStore } from "react";
import type { SignedIn, User } from "./types";

// Who is signed in in this browser tab, kept in sessionStorage so a reload
// keeps them signed in and closing the tab signs them out. Pages follow it with
// useSignedIn, so a sign-out or an expired sign-in shows at once.

const KEY = "signed-in";
const listeners = new Set<() => void>();

function saved(): string | null {
  return sessionStorage.getItem(KEY);
}

function changed() {
  for (const listener of listeners) listener();
}

export function signedIn(): SignedIn | null {
  const text = saved();
  return text ? (JSON.parse(text) as SignedIn) : null;
}

export function token(): string | undefined {
  return signedIn()?.token;
}

export function remember(signIn: SignedIn) {
  sessionStorage.setItem(KEY, JSON.stringify(signIn));
  changed();
}

export function forget() {
  sessionStorage.removeItem(KEY);
  changed();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// The signed-in person, or undefined, kept up to date as they sign in and out.
export function useSignedIn(): User | undefined {
  const text = useSyncExternalStore(subscribe, saved);
  return text ? (JSON.parse(text) as SignedIn).user : undefined;
}
