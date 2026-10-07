# Oracle Always Free capacity watch

Runs on standard Linux GitHub-hosted runners at minute 7 and 37 each hour.
GitHub schedules can be delayed. Public repositories use free standard runners;
no paid runner, cache, artifact storage, or AI model is used by this workflow.

The workflow is gated by repository variable `ORACLE_WATCH_ENABLED=true`.
Keep it disabled until all credentials are configured and a manual run passes.
Pause the old desktop schedule before enabling this workflow so launch attempts
cannot overlap across the two systems. Do not run the Console Create form in parallel.

## Secrets

| Name | Value |
| --- | --- |
| `OCI_CONFIG_JSON` | JSON object containing `user`, `fingerprint`, `tenancy`, and `region` (`ap-singapore-1`) |
| `OCI_API_PRIVATE_KEY` | Dedicated Oracle API signing private key in PEM format; never the SSH private key |
| `OCI_SSH_PUBLIC_KEY` | Existing public SSH key for the new VM |
| `ORACLE_NOTIFY_EMAIL` | Gmail sender and recipient address |
| `ORACLE_NOTIFY_APP_PASSWORD` | Dedicated Gmail App Password, not the normal Gmail password |

Configure through GitHub repository Settings → Secrets and variables → Actions.
Do not commit credentials, put them in workflow inputs, or paste them into logs.
Codex Gmail connector credentials do not transfer to GitHub runners.
Gmail App Password requires 2-Step Verification and may be unavailable for some accounts.

## Behavior and limits

- One launch attempt per run, alternating A1 1 OCPU / 6 GB and E2 Micro.
- Singapore must be the tenancy Home region. Uses the existing public subnet
  named `subnet-20260907-0112`, Oracle Linux 9 official compatible image, and 50 GB
  Balanced boot disk. Never changes the old E5 instance or deletes disks.
- Scans instances and boot/block volumes across all active compartments in Home
  region; stopped VMs and unattached disks count. Blocks exceeding A1 total 2 OCPU /
  12 GB, two Micro instances, or 200 GB storage. Missing API permission fails closed.
- No API launch retries inside a run. Stable retry tokens and a fixed VM name
  prevent retrying an ambiguous successful launch. GitHub concurrency prevents
  overlapping runs of this workflow.
- A VM with this name but without the workflow ownership tag stops the job for
  review. A VM being provisioned is checked on the next run; no second VM is created.
- Once RUNNING with a public IP, sends a success email containing SSH details,
  records a notification tag on its own VM, and disables this workflow.
  Notification normally arrives on the following 30-minute check.
- If email delivery fails, no new VM is created; the existing VM remains for retry.
  SMTP delivery and the notification tag are not atomic: a failure after successful
  delivery can result in a duplicate email. Failed workflow runs use GitHub's normal
  notifications; this workflow does not depend on a browser session.
- A1 is ARM; it does not directly run the current MT5/Wine x86 setup.
- Public logs omit VM IDs/IPs. Resource/account identifiers belong in Secrets.

## References

- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://support.google.com/accounts/answer/185833
