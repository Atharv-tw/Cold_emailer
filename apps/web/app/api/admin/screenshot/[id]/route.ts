import { NextResponse } from "next/server";

import { apiFetch } from "@/lib/api";

/**
 * Hand the browser a viewable URL for a payment screenshot.
 *
 * This exists because `<img src>` cannot authenticate. The API session token
 * is held server-side and never reaches the browser - that is the rule the
 * whole `lib/api` module exists to keep - so the image cannot be fetched
 * directly from the API by the page displaying it.
 *
 * The flow: this handler asks the API (with the token) for the object, the API
 * checks the caller is an operator and answers 302 to a presigned URL that
 * expires in minutes, and this redirects the browser there. The signed URL is
 * unguessable and short-lived, which is what makes handing it to a browser
 * acceptable for an image showing somebody's payment details.
 *
 * `redirect: "manual"` matters twice: followed automatically, fetch would pull
 * the image through this server and stream it out again for no reason, and the
 * `Location` header - the only thing actually wanted here - would be gone.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const response = await apiFetch(`/v1/admin/payments/${id}/screenshot`, {
    redirect: "manual",
  });

  const location = response.headers.get("location");
  if (location) {
    return NextResponse.redirect(location);
  }

  // No Location means the API refused rather than redirected - most likely a
  // 403 from a non-operator, or a 404 for a claim that is gone. Pass the
  // status through rather than flattening everything to one error.
  return NextResponse.json(
    { error: "could not load the screenshot" },
    { status: response.status === 200 ? 502 : response.status },
  );
}
