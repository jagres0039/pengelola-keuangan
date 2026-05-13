"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken, setToken, type UserMe } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "anon" }
  | { kind: "user"; user: UserMe };

export function useAuth(): { state: State; logout: () => void; refresh: () => Promise<void> } {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "loading" });

  async function refresh(): Promise<void> {
    if (!getToken()) {
      setState({ kind: "anon" });
      return;
    }
    try {
      const me = await api.get<UserMe>("/auth/me");
      setState({ kind: "user", user: me });
    } catch {
      setToken(null);
      setState({ kind: "anon" });
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function logout() {
    setToken(null);
    router.push("/login");
  }

  return { state, logout, refresh };
}

export function AuthGuard({ children }: { children: (user: UserMe) => React.ReactNode }) {
  const router = useRouter();
  const { state } = useAuth();

  useEffect(() => {
    if (state.kind === "anon") {
      router.replace("/login");
    }
  }, [state, router]);

  if (state.kind === "loading") {
    return (
      <div className="flex min-h-dvh items-center justify-center text-slate-400">
        memuat…
      </div>
    );
  }
  if (state.kind === "anon") {
    return null;
  }
  return <>{children(state.user)}</>;
}
