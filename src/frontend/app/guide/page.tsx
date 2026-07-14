"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import { APP_NAME } from "@/lib/branding";

const STEPS = [
  {
    title: "Sign in with a username",
    body: "No password — your username is your student profile. The coach's notes about your play (Lessons) accumulate under it, so use the same name every session to build a coaching history.",
  },
  {
    title: "Upload a game",
    body: "Paste a PGN into the upload box and pick which color you played (it's auto-detected when your username matches the PGN headers). You can export a PGN from chess.com (Share → PGN) or lichess (Analysis board → FEN & PGN).",
    tip: "Annotated games work best. If you add your own {comments} to the PGN — what you were thinking, what you were afraid of — the coach reads them and compares your reasoning against the engine's verdict.",
  },
  {
    title: "Let the analysis run",
    body: "Analysis takes a minute or two: Stockfish evaluates every move, then your coach picks the handful of moments that mattered, writes takeaways, and updates its long-term notes on your habits. Chat unlocks when it finishes.",
  },
  {
    title: "Review the takeaways and replay the game",
    body: "Takeaways appear on the left, and the board below them replays the game — click any move in the list or use the ← → arrow keys to step through. The board is oriented to the side you played.",
  },
  {
    title: "Talk to your coach",
    body: "Ask anything: \"What was my biggest mistake?\", \"What should I have played instead of 14.Nxe5?\", \"What should I study next?\". Suggested questions get you started. When the coach discusses a position, an amber chip appears under its reply — click it to show that position on the board, and click any move in the move list to return to the game.",
  },
  {
    title: "Keep uploading games",
    body: "This is where the coaching gets personal. Recurring mistakes become Lessons the coach remembers across games and sessions — if you keep drifting into the same bad trades or ignoring your king's safety, expect to hear about it until it stops.",
  },
];

export default function GuidePage() {
  const [username, setUsername] = useState<string>("");

  useEffect(() => {
    setUsername(localStorage.getItem("username") ?? "");
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <Header username={username || undefined} />

      <main className="mx-auto w-full max-w-2xl flex-1 overflow-y-auto p-6">
        <h1 className="text-2xl font-bold text-stone-100">How to use {APP_NAME}</h1>
        <p className="mt-2 text-sm text-stone-400">
          {APP_NAME} is a chess coach that studies <em>your</em> games. It finds the moments
          that decided each game, explains them at your level, and remembers your recurring
          mistakes so its advice compounds over time.
        </p>

        <ol className="mt-8 space-y-6">
          {STEPS.map((step, i) => (
            <li key={i} className="flex gap-4">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-400 text-sm font-bold text-stone-950">
                {i + 1}
              </span>
              <div>
                <h2 className="font-semibold text-stone-100">{step.title}</h2>
                <p className="mt-1 text-sm leading-relaxed text-stone-400">{step.body}</p>
                {step.tip && (
                  <p className="mt-2 rounded-lg border border-amber-400/30 bg-amber-400/5 px-3 py-2 text-sm text-amber-200/90">
                    <span className="font-semibold">Tip:</span> {step.tip}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>

        <div className="mt-10 border-t border-stone-800 pt-6 text-center">
          <Link
            href={username ? "/coach" : "/"}
            className="inline-block rounded-lg bg-amber-400 px-6 py-2.5 text-sm font-semibold text-stone-950 hover:bg-amber-300"
          >
            {username ? "Back to coaching" : "Start a coaching session"}
          </Link>
        </div>
      </main>
    </div>
  );
}
