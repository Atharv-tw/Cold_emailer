/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Without this Next walks up and finds an unrelated lockfile in the home
  // directory, then warns about it on every build.
  outputFileTracingRoot: import.meta.dirname,
  // The PWA layer (manifest, service worker, push) lands in milestone 7 and
  // is added to this same app - there is no separate mobile build.
};

export default nextConfig;
