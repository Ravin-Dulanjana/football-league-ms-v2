/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: 'standalone' lets us deploy to EC2 as a plain Node.js process
  // later with zero config changes. Vercel ignores this setting and works fine.
  output: "standalone",

  // Never hardcode the backend URL here — use environment variables only.
  // The proxy in app/api/**/route.ts reads process.env.API_BASE_URL at runtime.

  images: {
    // CloudFront domain for serving player photos and club logos.
    // Populated from NEXT_PUBLIC_CLOUDFRONT_DOMAIN env var.
    remotePatterns: process.env.NEXT_PUBLIC_CLOUDFRONT_DOMAIN
      ? [
          {
            protocol: "https",
            hostname: process.env.NEXT_PUBLIC_CLOUDFRONT_DOMAIN,
          },
        ]
      : [],
  },
};

export default nextConfig;
