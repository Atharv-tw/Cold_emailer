import { getToken } from "next-auth/jwt";
import { cookies, headers } from "next/headers";

/**
 * Server-side calls to the API.
 *
 * Everything goes through here so the API session token is read from the
 * encrypted Auth.js JWT on the server and attached as a bearer header. No
 * component fetches the API from the browser with a credential, because there
 * is no credential in the browser to fetch it with.
 */

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function apiToken(): Promise<string | undefined> {
  const token = await getToken({
    req: { headers: await headers(), cookies: await cookies() } as never,
    secret: process.env.AUTH_SECRET!,
  });
  return token?.apiToken as string | undefined;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await apiToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? detail;
    } catch {
      // A non-JSON error body is still an error; the status carries it.
    }
    throw new ApiError(response.status, detail);
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
