# Debugging "Requested format is not available" for UGC Downloads

**Date:** 2026-03-18
**File changed:** `packages/yubal/src/yubal/services/download_service.py`

## Symptom

Certain UGC (user-generated content) songs consistently failed to download with:

```
ERROR: [youtube] MrALHfFXWMs: Requested format is not available.
Use --list-formats for a list of available formats
```

This happened for every UGC track that needed downloading, not just intermittently. Tracks that were already downloaded (and skipped) masked the issue — it appeared as if only specific videos were affected.

## Debugging process

### 1. Initial hypothesis: format string or transient issue

Examined the yt-dlp format selector in `_build_yt_dlp_options()`:

```python
"format": "bestaudio[ext=opus]/bestaudio[acodec=opus]/bestaudio/best"
```

Listed formats for both the failing video (`MrALHfFXWMs`) and a working one (`W8kI1na3S2M`) using `yt-dlp --list-formats`. Both had identical audio formats available (opus 251, opus 249, m4a 140, m4a 139). The format string should have matched.

Tested downloading both videos from the host machine — both succeeded. Added `"Requested format is not available"` to retryable errors as a safety net, rebuilt Docker, and redeployed. **The error persisted across all 4 retry attempts**, ruling out a transient issue.

### 2. Reproducing inside Docker

Ran `docker exec` to test the download directly inside the container with the same yt-dlp options. **It succeeded.** This was confusing — same container, same code, same video, different result.

### 3. Narrowing down: cookies

The app resolves cookies from `config/ytdlp/cookies.txt` (193KB, a full cookie jar), while manual tests had been using `config/cookies.txt` (938 bytes, minimal). Testing with the actual app cookies file reproduced the error:

```
# With config/cookies.txt (938 bytes) → SUCCESS
# With config/ytdlp/cookies.txt (193KB) → FAILED
```

### 4. Understanding the authenticated vs unauthenticated path

With verbose output enabled, the difference became clear.

**Without cookies (unauthenticated):**
- yt-dlp uses the `android_vr` player client
- `android_vr` returns formats directly, no JS challenge solving needed
- Download succeeds

**With cookies (authenticated):**
- `android_vr` is **skipped** ("does not support cookies")
- yt-dlp falls back to authenticated clients: `tv_downgraded`, `web_safari`, `web_music`
- `web_safari` formats are skipped (SABR streaming, missing URLs — [yt-dlp#12482](https://github.com/yt-dlp/yt-dlp/issues/12482))
- `web_music` formats require a GVS PO Token (not provided) and are skipped
- `tv_downgraded` formats need JS challenge solving (signature + n-token decryption)
- **JS challenge solver crashes** → signatures can't be decrypted → all remaining format URLs are invalid
- After filtering: **zero audio formats, only storyboard images**
- `"Requested format is not available"`

### 5. Finding the JS challenge solver crash

The deno error in verbose output:

```
TypeError: Cannot read properties of undefined (reading 'origin')
    Function('_result', code)(resultObj);
```

yt-dlp was forcing the **"tv" player JS variant** for the challenge solver:

```
[debug] [youtube] Forcing "tv" player JS variant for player f4f314f0
```

YouTube's "tv" player JS contains `self.location.origin` — a browser-only API that doesn't exist in deno's sandboxed runtime.

### 6. Confirming with upstream

Searched yt-dlp issues and found [#16256](https://github.com/yt-dlp/yt-dlp/issues/16256) — filed the day before, tagged `high-priority` and `site-bug`. The issue affects all deno versions (tested up to 2.7.5). The recommended workaround:

```
--extractor-args "youtube:player_js_variant=main"
```

The "main" variant doesn't contain the `self.location.origin` code.

### 7. Verifying the fix

Tested inside Docker with the real cookies file and `player_js_variant=main`:

```python
"extractor_args": {
    "youtube": {"player_js_variant": ["main"]},
},
```

The JS challenge solver ran successfully, signatures were decrypted, and the download completed.

## Changes made

### `_build_yt_dlp_options()` — added `player_js_variant=main`

```python
"extractor_args": {
    "youtube": {"player_js_variant": ["main"]},
},
```

Forces yt-dlp to use the "main" player JS variant instead of "tv". This allows deno to successfully solve JS challenges, which in turn allows authenticated player clients (`tv_downgraded`) to extract valid format URLs.

### `_is_retryable_error()` — added "Requested format is not available"

```python
"Requested format is not available",
```

Safety net for cases where format unavailability is genuinely transient (e.g., YouTube CDN inconsistencies during bulk downloads).

## Why only UGC was visibly affected

All downloads with the `config/ytdlp/cookies.txt` cookie jar were affected, not just UGC. However, most tracks were already downloaded and skipped (`expected.exists()` check at line 478). UGC tracks that still needed downloading were the only ones that hit the yt-dlp code path, making it appear UGC-specific.

## Future action

The `player_js_variant=main` override should be **removed** once yt-dlp releases a fix for [#16256](https://github.com/yt-dlp/yt-dlp/issues/16256). Keeping it long-term could prevent yt-dlp from switching to a better default variant in the future.
