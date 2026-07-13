# Mystic LAB 100-primitive benchmark

Measured in a headed, foreground Chromium 149.0.0.0 window on a MacBook Air (Mac16,12, Apple M4, 16 GB) running macOS 26.2. The viewport was 1280×720 at DPR 1.

The deterministic 100-primitive scene warmed for three seconds and collected 601 rendered frames over ten seconds: average frame time 16.67 ms, p50 16.70 ms, p95 18.20 ms, and approximate 59.99 FPS. Renderer counters reported 9,242 triangles and 102 draw calls; scene initialization was 117.1 ms and deterministic selection latency was 14.7 ms.

This is a reference measurement for this specific foreground machine and browser only. Browser GPU-memory telemetry was unavailable and is intentionally not reported.
