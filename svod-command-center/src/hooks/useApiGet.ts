import { useEffect, useState } from 'react';
import { apiGet } from '@/lib/api';

export function useApiGet<T>(path: string, initialData: T) {
  const [data, setData] = useState<T>(initialData);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refetchIndex, setRefetchIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setIsLoading(true);
        const result = await apiGet<T>(path);
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.message || 'Ошибка запроса');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [path, refetchIndex]);

  const refetch = () => setRefetchIndex((i) => i + 1);

  return { data, isLoading, error, refetch };
}
