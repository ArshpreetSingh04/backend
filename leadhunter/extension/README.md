# LeadHunter Companion (browser-extension stub)

A Manifest V3 stub for the companion extension that will pair with the LeadHunter
desktop app.

**Current state:** scaffold only. It installs, logs a message, answers a `PING`
with `PONG`, and does a naive read-only scrape of emails on the page to prove the
content-script wiring.

**Planned role**
- One-click "capture this business as a lead" from any page.
- Provide live page context to the research engine.
- Talk to the desktop app over a native-messaging host. `[needs-key:native-host]`

> The real research automation drives a real browser with human-like
> mouse/keyboard (via the desktop app), never raw JS injection. This extension is
> only a convenience/observation layer.

## Load it (Chrome/Edge)
1. Go to `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select this `extension/` folder.
