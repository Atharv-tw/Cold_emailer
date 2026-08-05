import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

/**
 * Google sign-in, and the handoff to our own API.
 *
 * Two things are going on. Auth.js owns the browser session; the API owns the
 * mailbox. The refresh token Google issues is the API's business, not the
 * browser's, so it is forwarded server-side once at sign-in and never sent to
 * the client - which is also why the API's session token is kept inside the
 * encrypted Auth.js JWT rather than exposed to page JavaScript.
 *
 * `access_type: "offline"` with `prompt: "consent"` is what makes Google issue
 * a refresh token at all. Without the explicit prompt, a returning user who
 * already consented gets an access token and nothing else, and the API ends up
 * with an account it cannot send from tomorrow.
 */

const SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/gmail.send",
  "https://www.googleapis.com/auth/gmail.readonly",
  // Optional: create follow-up reminders on the user's calendar. Google shows
  // it as a separate, uncheckable-on-its-own item; declining it leaves the
  // rest of the product working, only without the mirrored reminders.
  "https://www.googleapis.com/auth/calendar.events",
].join(" ");

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

type ApiSession = {
  id: string;
  email: string;
  name: string;
  avatar: string;
  connected: boolean;
  missing_scopes: string[];
  profile_complete: boolean;
  calendar_connected: boolean;
};

async function exchange(account: {
  id_token?: string | null;
  refresh_token?: string | null;
  scope?: string | null;
  expires_at?: number | null;
}): Promise<{ token: string; user: ApiSession } | null> {
  if (!account.id_token) return null;

  const response = await fetch(`${API_BASE}/v1/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_token: account.id_token,
      refresh_token: account.refresh_token ?? null,
      scopes: account.scope ? account.scope.split(" ") : [],
      expires_at: account.expires_at
        ? new Date(account.expires_at * 1000).toISOString()
        : null,
    }),
  });

  if (!response.ok) {
    // The API's `detail` is our own message and never contains a token, so it
    // is safe to log - and without it a failed sign-in is just a number, which
    // is not enough to act on.
    let detail = "";
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? "";
    } catch {
      detail = (await response.text().catch(() => "")).slice(0, 300);
    }
    console.error(`API sign-in failed: ${response.status} ${detail}`);
    return null;
  }

  // The API sets its session as a cookie for same-origin deployments and we
  // also read it from the Set-Cookie header, because in development the web
  // app and the API are on different ports and the cookie will not stick.
  const raw = response.headers.get("set-cookie") ?? "";
  const match = raw.match(/outreach_session=([^;]+)/);
  const user = (await response.json()) as ApiSession;
  return match ? { token: match[1], user } : null;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      authorization: {
        params: {
          scope: SCOPES,
          access_type: "offline",
          prompt: "consent",
          include_granted_scopes: "true",
        },
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        const result = await exchange(account);
        if (result) {
          token.apiToken = result.token;
          token.apiUser = result.user;
        }
      }
      return token;
    },
    async session({ session, token }) {
      // apiToken stays out of the client payload on purpose.
      session.apiUser = token.apiUser as ApiSession | undefined;
      return session;
    },
  },
  pages: {
    signIn: "/",
  },
});
