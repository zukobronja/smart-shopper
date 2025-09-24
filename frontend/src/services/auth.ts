import { buildUrl } from "./http";

export interface GoogleLoginResponse {
  authorization_url: string;
  state: string;
  provider: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  auth_provider: string;
  status: string;
  email_verified: boolean;
  profile_picture?: string | null;
  total_searches: number;
  created_at: string;
  last_login?: string | null;
}

export async function fetchGoogleAuthorizationUrl(redirectTo?: string): Promise<GoogleLoginResponse> {
  const url = new URL(buildUrl("/auth/google/login"));
  if (redirectTo) {
    url.searchParams.set("redirect_to", redirectTo);
  }

  const response = await fetch(url.toString(), {
    method: "GET",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Failed to initiate Google login (status ${response.status})`);
  }

  const data = (await response.json()) as GoogleLoginResponse;
  if (!data.authorization_url) {
    throw new Error("Google login response missing authorization URL");
  }
  return data;
}

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const response = await fetch(buildUrl("/auth/me"), {
    method: "GET",
    credentials: "include",
  });

  if (response.status === 401) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to load current user (status ${response.status})`);
  }

  return (await response.json()) as CurrentUser;
}

export async function logout(): Promise<void> {
  const response = await fetch(buildUrl("/auth/logout"), {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Logout failed (status ${response.status})`);
  }
}
