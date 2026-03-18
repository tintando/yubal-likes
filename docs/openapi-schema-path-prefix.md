# OpenAPI Schema Path Prefix Mismatch

**Date:** 2026-03-18
**Files changed:** `web/src/api/client.ts`, `web/src/api/schema.d.ts`, `web/src/api/*.ts`, `web/package.json`

## Symptom

After regenerating `schema.d.ts` with `openapi-typescript`, the TypeScript build broke with errors like:

```
Argument of type '"/jobs"' is not assignable to parameter of type 'PathsWithMethod<paths, "post">'
```

Every typed API call failed because the path strings in code no longer matched the paths in the schema.

## Root cause

The OpenAPI schema served by FastAPI includes the full `/api/` prefix on all paths (e.g., `/api/jobs`, `/api/cookies/status`) because routes are mounted via `APIRouter(prefix="/api")` in `app.py`.

However, the `openapi-fetch` client in `client.ts` was configured with `baseUrl: "/api"`, which prepends `/api` to whatever path string you pass. This meant the schema had to contain paths *without* the prefix (e.g., `/jobs`) so the client would construct the correct URL `/api/jobs`.

The old `schema.d.ts` had paths without the `/api/` prefix. It's unclear how it was originally generated that way — possibly hand-edited or generated from a different server configuration — but once regenerated from the actual server, every path gained the `/api/` prefix and all typed calls broke.

## Fix

Changed `baseUrl` from `"/api"` to `"/"` in `client.ts`, so the client no longer prepends anything:

```ts
// Before
export const api = createClient<paths>({ baseUrl: "/api" });

// After
export const api = createClient<paths>({ baseUrl: "/" });
```

Then updated all API call sites to use the full path including `/api/`:

```ts
// Before
await api.GET("/jobs");

// After
await api.GET("/api/jobs");
```

This way the paths in code match the schema exactly, and the schema can be regenerated from the server at any time without manual edits.

Also updated the `generate-api` script in `package.json` to target port 8000 (the Docker container) instead of 8765 (a dev server port that was no longer in use).

## Files changed

- `web/src/api/client.ts` — `baseUrl: "/api"` → `baseUrl: "/"`
- `web/src/api/jobs.ts` — all paths prefixed with `/api`
- `web/src/api/subscriptions.ts` — all paths prefixed with `/api`
- `web/src/api/cookies.ts` — all paths prefixed with `/api`
- `web/src/api/drive.ts` — all paths prefixed with `/api`
- `web/src/api/replaygain.ts` — all paths prefixed with `/api`
- `web/src/api/likes.ts` — new file, written with `/api` paths from the start
- `web/src/api/schema.d.ts` — regenerated from Docker container
- `web/package.json` — `generate-api` script port 8765 → 8000

## How to regenerate the schema going forward

1. Start the Docker container: `docker compose up -d`
2. Run: `bun run generate-api` (from `web/`)
3. The schema will match the server and all typed calls will work without edits.
