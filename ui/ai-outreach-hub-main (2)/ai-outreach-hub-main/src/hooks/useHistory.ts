import { useCallback, useEffect, useState } from "react";
import type { AnalysisResult } from "@/services/types";

const KEY = "vqcs.history.v1";

export function useHistory() {
  const [items, setItems] = useState<AnalysisResult[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setItems(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  const persist = (next: AnalysisResult[]) => {
    setItems(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  const add = useCallback(
    (r: AnalysisResult) => {
      const next = [r, ...items].slice(0, 30);
      persist(next);
    },
    [items]
  );

  const remove = useCallback(
    (id: string) => persist(items.filter((i) => i.id !== id)),
    [items]
  );

  const clear = useCallback(() => persist([]), []);

  return { items, add, remove, clear };
}
