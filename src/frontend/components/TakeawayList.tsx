interface Takeaway {
  text: string;
  moment_ply: number;
}

interface Props {
  takeaways: Takeaway[];
}

export default function TakeawayList({ takeaways }: Props) {
  return (
    <div className="rounded-lg border border-amber-400/30 bg-amber-400/5 p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-amber-400">
        Key Takeaways
      </h2>
      <ol className="space-y-2">
        {takeaways.map((t, i) => (
          <li key={i} className="flex gap-2 text-sm">
            <span className="flex-shrink-0 font-bold text-amber-400">{i + 1}.</span>
            <span className="text-stone-300">{t.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
