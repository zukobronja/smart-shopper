import { useEffect, useState } from "react";
import { CurrentUser, fetchCurrentUser, logout } from "../services/auth";

interface UseCurrentUserResult {
  user: CurrentUser | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  signOut: () => Promise<void>;
}

export function useCurrentUser(): UseCurrentUserResult {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await fetchCurrentUser();
      setUser(result);
    } catch (err) {
      console.warn("Failed to load current user", err);
      setError(err instanceof Error ? err.message : "Failed to load user");
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const signOut = async () => {
    try {
      await logout();
      setUser(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to log out");
      throw err;
    }
  };

  useEffect(() => {
    load();
  }, []);

  return { user, loading, error, reload: load, signOut };
}
