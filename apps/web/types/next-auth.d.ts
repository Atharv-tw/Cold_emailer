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
