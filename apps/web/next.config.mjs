/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The PWA layer (manifest, service worker, push) lands in milestone 7 and
  // is added to this same app - there is no separate mobile build.
};

export default nextConfig;
