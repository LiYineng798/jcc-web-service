import { useEffect, useState } from "react";

type Failure = Error & { status?: number };

export function useResource<T>(url: string, refreshVersion = 0) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    url: string;
    attempt: number;
    data?: T;
    error?: Failure;
    loading: boolean;
  }>({ url, attempt, loading: true });
  useEffect(() => {
    const restore = (event: PageTransitionEvent) => {
      if (event.persisted) setAttempt((value) => value + 1);
    };
    window.addEventListener("pageshow", restore);
    return () => window.removeEventListener("pageshow", restore);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const abort = () => controller.abort();
    window.addEventListener("pagehide", abort, { once: true });
    // Preserve the current collection during same-query refreshes after modal saves.
    // Query changes still show a fresh loading state and never reuse another query.
    setState((previous) =>
      previous.url === url && previous.attempt === attempt && previous.data
        ? { url, attempt, data: previous.data, loading: false }
        : { url, attempt, loading: true },
    );
    window.JccAccount.request<T>(url, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ url, attempt, data, loading: false });
      })
      .catch((error: Failure) => {
        if (!controller.signal.aborted && error.name !== "AbortError")
          setState({ url, attempt, error, loading: false });
      });
    return () => {
      abort();
      window.removeEventListener("pagehide", abort);
    };
  }, [url, attempt, refreshVersion]);
  return {
    ...(state.url === url
      ? state
      : { loading: true, data: undefined, error: undefined }),
    retry: () => setAttempt((value) => value + 1),
  };
}
