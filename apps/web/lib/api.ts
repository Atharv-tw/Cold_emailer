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
  const isProd = process.env.NODE_ENV === "production";
  const token = await getToken({
    req: { headers: await headers(), cookies: await cookies() } as never,
    secret: process.env.AUTH_SECRET!,
    salt: isProd ? "__Secure-authjs.session-token" : "authjs.session-token",
    secureCookie: isProd,
  });
  return token?.apiToken as string | undefined;
}

/**
 * Turn the API's `detail` into something a person can read.
 *
 * Our own errors are strings. FastAPI's own validation failures are not - the
 * detail is a list of `{loc, msg}` objects, and interpolating that yields
 * "[object Object]", which names neither the field nor the problem. Those are
 * the only two things worth reporting.
 */
function describe(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail || undefined;
  if (!Array.isArray(detail)) return undefined;

  const lines = detail.map((item) => {
    const { loc, msg } = (item ?? {}) as { loc?: unknown[]; msg?: string };
    // `loc` opens with the source - "body", "query" - and the rest is the
    // path to the field that was rejected.
    const field = Array.isArray(loc) ? loc.slice(1).join(".") : "";
    const message = msg ?? "is not valid";
    return field ? `${field}: ${message}` : message;
  });

  return lines.join("; ") || undefined;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await apiToken();

  // A FormData body must carry its own multipart Content-Type, boundary and
  // all, and only fetch can write that. Setting the header here - even to be
  // overridden later by a caller passing `headers: {}`, which merges nothing -
  // sends a multipart upload announcing itself as JSON, and the API rejects it
  // with a validation error naming a field the caller did send.
  const isMultipart = init.body instanceof FormData;

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isMultipart ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = describe(((await response.json()) as { detail?: unknown }).detail) ?? detail;
    } catch {
      // A non-JSON error body is still an error; the status carries it.
    }
    throw new ApiError(response.status, detail);
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
