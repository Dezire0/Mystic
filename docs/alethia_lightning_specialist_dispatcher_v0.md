# ALETHEIA Lightning Specialist Dispatcher v0

This ALETHEIA-only module maps the capability `scientific.pdf_retrieval` to the configured existing Lightning Studio. It does not modify WORLD, HERMES, MNEME, OIKOS, MCP routing, or any production model-selection policy.

The optional dependency is `pip install -e '.[lightning]'`. The adapter was checked against `lightning-sdk` 2026.8.18: `Studio(..., create_ok=False)`, `start(Machine.T4)`, `stop()`, `upload_file`, `download_file`, and `run_with_exit_code`. `create_ok=False` is mandatory: this dispatcher never creates a replacement Studio.

Required environment settings are `LIGHTNING_USER_ID`, `LIGHTNING_API_KEY`, `LIGHTNING_OWNER`, `LIGHTNING_TEAMSPACE`, and `LIGHTNING_STUDIO_NAME`. `LIGHTNING_OWNER_KIND` may be `user` (default) or `org`. Missing configuration fails closed. Credentials are never placed in remote job JSON, artifacts, events, or errors.

Each job validates a safe opaque job ID, local PDFs, hash/size/count limits, and `candidate_k`/`final_k`. It persists a normalized specification hash and input SHA-256 hashes under `mystic_data/aletheia_lightning_jobs/<job_id>/`. A completed result is reused only when the job ID, status, specification hash, and every input hash match.

The lifecycle uses a cross-process filesystem T4 lease, starts the existing Studio on `Machine.T4`, uploads only sanitized job paths under `~/aletheia_worker/jobs/<job_id>/`, runs the existing `aletheia_job.py`, validates `result.json`, creates unproven `EvidenceCandidate` records, and always attempts `stop()` in `finally`. A shutdown failure is preserved separately from a successful evidence result. `LightningScientificJobAdapter` is shaped for the existing durable `ScientificJobWorker`, so that job leases and PENDING → READY → LEASED → RUNNING → SUCCEEDED transitions remain ALETHEIA-owned.

Run the real acceptance test only with a controlled PDF and configured credentials:

```bash
python scripts/run_aletheia_lightning_acceptance.py \
  --job-id lightning-acceptance-001 \
  --query 'Which page explains gravitational lensing?' \
  --pdf /absolute/path/to/controlled.pdf \
  --expected-page 1
```

This is intentionally opt-in because it starts billable GPU capacity. It must demonstrate automatic start, retrieval, evidence conversion, and automatic stop before any production integration is proposed.
