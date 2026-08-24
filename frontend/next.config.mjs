/** @type {import('next').NextConfig} */

// ---------------------------------------------------------------------------
// Content-Security-Policy
//
// Scoped to what this app actually loads — no copy-paste permissive boilerplate.
//
// script-src 'self'
//   Next.js bundles all scripts. No third-party scripts are loaded.
//
// style-src 'self' 'unsafe-inline'
//   Next.js injects critical CSS inline during SSR. 'unsafe-inline' is
//   unavoidable without nonce-based CSP (a future upgrade path).
//
// img-src 'self' data: blob: https://<cloudfront-domain>
//   - 'self': favicons, app-bundled images
//   - data:/blob:: Next.js image optimiser may use these schemes
//   - CloudFront: player photos and club logos served from our CDN
//
// connect-src 'self'
//   All API calls go through /api/proxy (same origin). No direct browser
//   calls to the FastAPI backend — the backend URL is never exposed.
//
// font-src 'self' data:
//   Local fonts; data: covers any inlined font face declarations.
//
// frame-ancestors 'none'
//   Prevent this page from being embedded in an <iframe> (clickjacking).
//
// base-uri 'self'
//   Restrict <base href="..."> to same origin (mitigates base-tag injection).
//
// form-action 'self'
//   Forms may only submit to same origin (login form, etc.).
//
// object-src 'none'
//   Disallow Flash/Java plugins (long obsolete, but belt-and-suspenders).
// ---------------------------------------------------------------------------

const cloudfrontDomain = process.env.NEXT_PUBLIC_CLOUDFRONT_DOMAIN ?? "";

const imgSrc = cloudfrontDomain
  ? `'self' data: blob: https://${cloudfrontDomain}`
  : "'self' data: blob:";

const csp = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  `img-src ${imgSrc}`,
  "connect-src 'self'",
  "font-src 'self' data:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
]
  .join("; ")
  .concat(";");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Never hardcode the backend URL here — use environment variables only.
  // The proxy in app/api/**/route.ts reads process.env.API_BASE_URL at runtime.

  async headers() {
    return [
      {
        // Apply security headers to every route served by Next.js.
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: csp,
          },
          {
            // Prevent MIME-type sniffing — browser must respect Content-Type.
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            // Only send referrer for same-origin requests.
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            // Deny iframe embedding (belt-and-suspenders alongside CSP frame-ancestors).
            key: "X-Frame-Options",
            value: "DENY",
          },
        ],
      },
    ];
  },

  images: {
    // CloudFront domain for serving player photos and club logos.
    // Populated from NEXT_PUBLIC_CLOUDFRONT_DOMAIN env var.
    remotePatterns: cloudfrontDomain
      ? [
          {
            protocol: "https",
            hostname: cloudfrontDomain,
          },
        ]
      : [],
  },
};

export default nextConfig;
