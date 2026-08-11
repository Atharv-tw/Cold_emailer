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
    /**
     * The API's stable name for this refusal - "profile_incomplete",
     * "duplicate_target" - or "" when it did not send one.
     *
     * Screens that do more than print the message branch on this rather than
     * on the wording, which is the part that gets rewritten. See
     * `apps/api/app/errors.py` for the list.
     */
    readonly code: string = "",
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
 * Turn the API's `detail` into something a person can read, plus its code.
 *
 * Three shapes arrive here. A refusal the UI has to recognise is an object -
 * `{code, message}`, from `app/errors.py`. A plainer one is just a string.
 * FastAPI's own validation failures are neither: the detail is a list of
 * `{loc, msg}` objects, and interpolating that yields "[object Object]",
 * which names neither the field nor the problem - the only two things worth
 * reporting.
 */
function describe(detail: unknown): { message?: string; code: string } {
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const { code, message } = detail as { code?: unknown; message?: unknown };
    return {
      message: typeof message === "string" && message ? message : undefined,
      code: typeof code === "string" ? code : "",
    };
  }
  return { message: describeText(detail), code: "" };
}

function describeText(detail: unknown): string | undefined {
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

/**
 * The raw response, with the bearer token attached and nothing interpreted.
 *
 * `api()` treats any non-2xx as an error and parses the body as JSON, which is
 * right almost everywhere. It is wrong when the status *is* the answer - a 302
 * carrying a `Location` to follow, say - so this returns the response
 * untouched and leaves the caller to decide what it means.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await apiToken();
  const isMultipart = init.body instanceof FormData;

  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(isMultipart ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
    cache: "no-store",
  });
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
    let message = response.statusText;
    let code = "";
    try {
      const described = describe(((await response.json()) as { detail?: unknown }).detail);
      message = described.message ?? message;
      code = described.code;
    } catch {
      // A non-JSON error body is still an error; the status carries it.
    }
    throw new ApiError(response.status, message, code);
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
