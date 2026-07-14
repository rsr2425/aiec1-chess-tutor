"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";

export default function Home() {
  const [username, setUsername] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) return;
    localStorage.setItem("username", trimmed);
    router.push("/coach");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-amber-400">{APP_NAME}</h1>
        <p className="mt-2 text-stone-400">{APP_TAGLINE}</p>
      </div>

      <form onSubmit={handleSubmit} className="flex w-full max-w-sm flex-col gap-3">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Enter your username"
          className="rounded-lg border border-stone-700 bg-stone-900 px-4 py-3 text-stone-100 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-amber-400"
          autoFocus
        />
        <button
          type="submit"
          disabled={!username.trim()}
          className="rounded-lg bg-amber-400 px-4 py-3 font-semibold text-stone-950 hover:bg-amber-300 disabled:opacity-40"
        >
          Start coaching session
        </button>
      </form>

      <p className="text-xs text-stone-600">No password needed — your username is your key.</p>
    </main>
  );
}
