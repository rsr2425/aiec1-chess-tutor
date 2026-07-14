"use client";

import { useState } from "react";

interface Props {
  username: string;
  status: "idle" | "running" | "done" | "error";
  onUpload: (pgn: string, studentColor: string) => void;
}

export default function UploadCard({ username, status, onUpload }: Props) {
  const [pgn, setPgn] = useState("");
  const [color, setColor] = useState<"white" | "black">("white");

  // Auto-detect color from PGN headers
  function handlePgnChange(text: string) {
    setPgn(text);
    const whiteMatch = text.match(/\[White "([^"]+)"\]/);
    const blackMatch = text.match(/\[Black "([^"]+)"\]/);
    if (whiteMatch && whiteMatch[1].toLowerCase() === username.toLowerCase()) {
      setColor("white");
    } else if (blackMatch && blackMatch[1].toLowerCase() === username.toLowerCase()) {
      setColor("black");
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pgn.trim()) return;
    onUpload(pgn.trim(), color);
  }

  const isRunning = status === "running";

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-stone-400">
        Upload Game
      </h2>

      <textarea
        value={pgn}
        onChange={(e) => handlePgnChange(e.target.value)}
        placeholder="Paste annotated PGN here…"
        rows={6}
        disabled={isRunning}
        className="rounded-lg border border-stone-700 bg-stone-900 p-3 text-sm font-mono text-stone-200 placeholder-stone-600 focus:outline-none focus:ring-2 focus:ring-amber-400 disabled:opacity-50"
      />

      <div className="flex items-center gap-3">
        <span className="text-xs text-stone-500">Playing as:</span>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="radio"
            value="white"
            checked={color === "white"}
            onChange={() => setColor("white")}
            disabled={isRunning}
            className="accent-amber-400"
          />
          <span className="text-sm">White</span>
        </label>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="radio"
            value="black"
            checked={color === "black"}
            onChange={() => setColor("black")}
            disabled={isRunning}
            className="accent-amber-400"
          />
          <span className="text-sm">Black</span>
        </label>
      </div>

      <button
        type="submit"
        disabled={!pgn.trim() || isRunning}
        className="rounded-lg bg-amber-400 py-2 text-sm font-semibold text-stone-950 hover:bg-amber-300 disabled:opacity-40"
      >
        {isRunning ? "Analyzing game…" : "Analyze game"}
      </button>

      {status === "error" && (
        <p className="text-xs text-red-400">Analysis failed. Please try again.</p>
      )}
    </form>
  );
}
