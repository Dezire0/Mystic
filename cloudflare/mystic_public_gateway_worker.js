const CONFIG_URL = "https://gist.githubusercontent.com/Dezire0/778759ccca8f7d9a54c1f98662b6a9ec/raw/mystic-origin.json";

async function loadOrigin() {
  const response = await fetch(CONFIG_URL, {
    cf: {
      cacheEverything: true,
      cacheTtl: 5,
    },
  });
  if (!response.ok) {
    throw new Error(`config fetch failed: ${response.status}`);
  }
  const payload = await response.json();
  if (!payload.origin) {
    throw new Error("origin missing");
  }
  return payload.origin;
}

export default {
  async fetch(request) {
    let origin;
    try {
      origin = await loadOrigin();
    } catch (error) {
      return new Response(`Mystic origin unavailable: ${error.message}`, { status: 503 });
    }

    const sourceUrl = new URL(request.url);
    const targetUrl = new URL(origin);
    targetUrl.pathname = sourceUrl.pathname;
    targetUrl.search = sourceUrl.search;

    const headers = new Headers(request.headers);
    headers.set("host", targetUrl.host);
    headers.set("x-forwarded-host", sourceUrl.host);
    headers.set("x-mystic-public-gateway", "cloudflare-worker");

    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
    });

    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set("x-mystic-public-origin", origin);
    responseHeaders.set("x-mystic-public-url", sourceUrl.origin);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  },
};
