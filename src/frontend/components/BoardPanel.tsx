"use client";

import { useState, useEffect, useRef } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";

interface Props {
  pgn: string;
  orientation?: "white" | "black";
  overrideFen?: string;
  onStepChange?: () => void; // called when user navigates — parent uses this to clear the override
}

interface GameData {
  fens: string[];
  moves: string[]; // SAN moves, parallel to fens[1..]
}

// Strip comments, variations, and NAGs so chess.js can parse cleanly.
// Annotated PGNs with { comments }, (variations), and $1 NAGs confuse the parser.
function stripAnnotations(pgn: string): string {
  let out = "";
  let inComment = false;
  let depth = 0;
  for (const c of pgn) {
    if (c === "{") { inComment = true; continue; }
    if (c === "}") { inComment = false; continue; }
    if (inComment) continue;
    if (c === "(") { depth++; continue; }
    if (c === ")") { depth = Math.max(0, depth - 1); continue; }
    if (depth > 0) continue;
    out += c;
  }
  return out
    .replace(/\$\d+/g, "")   // NAGs
    .replace(/[!?]+/g, "")   // move annotations
    .replace(/\s+/g, " ")
    .trim();
}

function buildGame(pgn: string): GameData {
  const fens: string[] = [new Chess().fen()];
  const moves: string[] = [];

  // Try the raw PGN first, then fall back to stripped version
  const attempts = [pgn, stripAnnotations(pgn)];
  for (const attempt of attempts) {
    try {
      const game = new Chess();
      game.loadPgn(attempt);
      const history = game.history({ verbose: true });
      if (history.length === 0) continue;
      const tmp = new Chess();
      for (const mv of history) {
        tmp.move(mv.san);
        fens.push(tmp.fen());
        moves.push(mv.san);
      }
      break; // success
    } catch {
      // try next attempt
    }
  }
  return { fens, moves };
}

export default function BoardPanel({ pgn, orientation = "white", overrideFen, onStepChange }: Props) {
  const [{ fens, moves }, setGame] = useState<GameData>(() => buildGame(pgn));
  const [moveIndex, setMoveIndex] = useState(0);
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setGame(buildGame(pgn));
    setMoveIndex(0);
  }, [pgn]);

  // Scroll active move into view when it changes
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [moveIndex]);

  const displayFen = overrideFen ?? fens[moveIndex] ?? "start";

  function step(fn: (i: number) => number) {
    setMoveIndex((i) => {
      const next = fn(i);
      return Math.max(0, Math.min(fens.length - 1, next));
    });
    onStepChange?.();
  }

  const goFirst = () => step(() => 0);
  const goPrev  = () => step((i) => i - 1);
  const goNext  = () => step((i) => i + 1);
  const goLast  = () => step(() => fens.length - 1);

  function goTo(idx: number) {
    setMoveIndex(Math.max(0, Math.min(fens.length - 1, idx)));
    onStepChange?.();
  }

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowLeft")  { e.preventDefault(); goPrev(); }
      if (e.key === "ArrowRight") { e.preventDefault(); goNext(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Build move pairs for display: [[white_idx, black_idx|null], ...]
  const movePairs: [number, number | null][] = [];
  for (let i = 0; i < moves.length; i += 2) {
    movePairs.push([i, i + 1 < moves.length ? i + 1 : null]);
  }

  return (
    <div className="flex flex-col items-center gap-2 w-full">
      {/* Board */}
      <div className="w-full max-w-[380px]">
        <Chessboard
          position={displayFen}
          boardOrientation={orientation}
          arePiecesDraggable={false}
          customBoardStyle={{ borderRadius: "6px", boxShadow: "0 4px 20px rgba(0,0,0,0.5)" }}
        />
      </div>

      {/* Stepper buttons */}
      <div className="flex items-center gap-1 text-stone-400">
        {([
          ["⏮", goFirst],
          ["◀", goPrev],
          ["▶", goNext],
          ["⏭", goLast],
        ] as [string, () => void][]).map(([label, action]) => (
          <button
            key={label}
            onClick={action}
            className="rounded px-2 py-1 text-sm hover:bg-stone-800 hover:text-stone-100 transition-colors"
          >
            {label}
          </button>
        ))}
        <span className="ml-2 text-xs text-stone-600 self-center">
          {overrideFen
            ? <span className="text-amber-400/70">chat position</span>
            : `${moveIndex} / ${fens.length - 1}`}
        </span>
      </div>

      {/* Move list — always visible when game is loaded; clicking any move returns from chat position */}
      {moves.length > 0 && (
        <div className={`w-full max-w-[380px] max-h-32 overflow-y-auto rounded-lg border p-2 transition-colors ${
          overrideFen
            ? "border-amber-400/30 bg-stone-900/40"
            : "border-stone-800 bg-stone-900/60"
        }`}>
          <div className="flex flex-wrap gap-y-0.5 text-xs font-mono leading-5">
            {movePairs.map(([wi, bi], pairIdx) => (
              <span key={pairIdx} className="flex items-baseline gap-0.5 mr-1">
                <span className="text-stone-600 select-none">{pairIdx + 1}.</span>
                {/* White move */}
                <button
                  ref={moveIndex === wi + 1 ? activeRef : null}
                  onClick={() => goTo(wi + 1)}
                  className={`rounded px-1 transition-colors ${
                    moveIndex === wi + 1
                      ? "bg-amber-400 text-stone-950 font-bold"
                      : "text-stone-300 hover:text-stone-100 hover:bg-stone-800"
                  }`}
                >
                  {moves[wi]}
                </button>
                {/* Black move */}
                {bi !== null && (
                  <button
                    ref={moveIndex === bi + 1 ? activeRef : null}
                    onClick={() => goTo(bi + 1)}
                    className={`rounded px-1 transition-colors ${
                      moveIndex === bi + 1
                        ? "bg-amber-400 text-stone-950 font-bold"
                        : "text-stone-300 hover:text-stone-100 hover:bg-stone-800"
                    }`}
                  >
                    {moves[bi]}
                  </button>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
