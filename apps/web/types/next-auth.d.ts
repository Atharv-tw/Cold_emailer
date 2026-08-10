import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session extends DefaultSession {
    apiUser?: {
      id: string;
      email: string;
      name: string;
      avatar: string;
      connected: boolean;
      missing_scopes: string[];
      profile_complete: boolean;
      calendar_connected: boolean;
      // Optional because the JWT is written at sign-in and only refreshed
      // there. The layout re-fetches /v1/auth/me on every page load precisely
      // so these are current; a token minted before this field existed simply
      // omits it, and false is the safe reading of absent for both.
      is_paid?: boolean;
      is_admin?: boolean;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    // Never serialised into the client session - see auth.ts.
    apiToken?: string;
    apiUser?: Session["apiUser"];
  }
}
