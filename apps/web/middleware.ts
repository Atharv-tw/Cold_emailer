import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Get the user agent from the headers
  const userAgent = request.headers.get('user-agent') || '';
  
  // Basic mobile detection (can be expanded to use next/server's userAgent if preferred,
  // but regex against the header is highly reliable and fast for Edge runtime)
  const isMobile = /Mobile|Android|iP(hone|od)|IEMobile|BlackBerry|Kindle|Silk-Accelerated|(hpw|web)OS|Opera M(obi|ini)/i.test(userAgent);

  const { pathname } = request.nextUrl;
  
  // Clone the URL to rewrite it
  const url = request.nextUrl.clone();
  
  // Rewrite the path to /mobile/... or /desktop/...
  if (isMobile) {
    url.pathname = `/mobile${pathname}`;
  } else {
    url.pathname = `/desktop${pathname}`;
  }
  
  return NextResponse.rewrite(url);
}

// Only run this middleware on pages. Exclude API, _next/static, _next/image, favicon, static assets, etc.
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt, manifest.webmanifest (metadata files)
     * - sw.js, and anything with a static asset extension
     *
     * The extension list covers svg and ico as well as png. It used to be png
     * alone, which meant /icon.svg and /logo.svg were rewritten to
     * /desktop/icon.svg and 404'd - so the favicon silently did not exist. Any
     * static file served from public/ or by Next's metadata conventions has to
     * be matched here, because a rewrite turns a missing extension into a
     * missing file rather than an error anyone notices.
     *
     * The photo formats went the same way the first time a .jpg was added to
     * public/ - listed here now rather than one extension at a time.
     */
    '/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|manifest.webmanifest|sw.js|.*\\.(?:png|jpg|jpeg|gif|webp|avif|svg|ico|webmanifest|xml|txt)).*)',
  ],
};
