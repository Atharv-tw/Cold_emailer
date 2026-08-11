import { ApiError } from "@/lib/api";

/**
 * How a server action reports a failure the user is meant to read.
 *
 * A server action that throws does not reach the browser with its message. In
 * a production build Next.js replaces every uncaught server error with "An
 * error occurred in the Server Components render. The specific message is
 * omitted in production builds…" and a digest - deliberately, because a
 * thrown error is assumed to be a bug that might name a table or a path. So
 * "alex@example.com is already on your list" - a sentence written for the
 * user, in an API the user is allowed to see - arrived on screen as that
 * paragraph instead.
 *
 * The fix is to stop throwing. An expected refusal is a value: the action
 * returns `{ok: false, error}`, which is data and crosses the boundary
 * untouched. Anything that is genuinely a bug still throws and still gets
 * obfuscated, which is the behaviour we want for those.
 *
 * `error.code` is the API's stable name for the refusal, so a screen can do
 * more than print the sentence - `profile_incomplete` opens the modal that
 * links to the profile. It is "" when the API sent no code.
 */
export type ActionError = { code: string; message: string };

export type Result<T> = { ok: true; data: T } | { ok: false; error: ActionError };

/**
 * Run an API call and turn an `ApiError` into a returned failure.
 *
 * Only `ApiError` is caught. A TypeError from a bug in the action body is not
 * something to render at the user, so it is left to throw.
 */
export async function attempt<T>(run: () => Promise<T>): Promise<Result<T>> {
  try {
    return { ok: true, data: await run() };
  } catch (caught) {
    if (caught instanceof ApiError) {
      return { ok: false, error: { code: caught.code, message: caught.message } };
    }
    throw caught;
  }
}

/** A refusal the action decided on itself, before any request went out. */
export function refuse(code: string, message: string): { ok: false; error: ActionError } {
  return { ok: false, error: { code, message } };
}

/**
 * The message to show, with a fallback for the case where there is no
 * sentence worth showing - a 500, a dropped connection.
 */
export function messageOf(error: ActionError, fallback: string): string {
  return error.message.trim() || fallback;
}
