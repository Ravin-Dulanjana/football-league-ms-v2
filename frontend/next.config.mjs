/** @type {import('next').NextConfig} */

const nextConfig = {
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
