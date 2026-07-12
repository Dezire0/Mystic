# Mystic Gemini App UI Bridge Extension

Load this unpacked Manifest V3 extension only in a dedicated Chrome profile. Log into `gemini.google.com` manually, open the extension popup, and click **Start Mystic Session**. The extension displays the next approved Mystic prompt. Submit it manually in Gemini, then paste only the visible response into the extension and click **Import Visible Response**.

This is `manual_send` compliance mode. It intentionally does not inject into, click, scrape, or otherwise automate `gemini.google.com`, because the current machine-readable instructions disallow automated access to the app/chat paths. It has no host, cookie, debugger, browsing-history, or web-request permissions and never calls Gemini network endpoints or inspects browser storage.
