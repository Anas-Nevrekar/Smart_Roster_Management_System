import { useCallback, useEffect, useState } from "react";
import { getApiFailure } from "../lib/api";
export function useResource<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null); const [error, setError] = useState<string | null>(null); const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => { setLoading(true); setError(null); try { setData(await load()); } catch (e) { setError(getApiFailure(e).message); } finally { setLoading(false); } }, [load]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { data, error, loading, retry: refresh };
}
