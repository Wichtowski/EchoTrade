# n8n Workflow Orchestration

EchoTrade uses [n8n](https://n8n.io/) for workflow orchestration.

## Access

```
URL:  http://localhost:5678
User: echo
Pass: echo
```

Production access is additionally protected at the Caddy layer with Basic Auth before traffic reaches n8n.
Generate the Caddy-compatible password hash with:

```bash
caddy hash-password
```

Add the generated value to the GitHub Actions secret `N8N_BASIC_AUTH_HASH`, redeploy the backend stack, and test that the public n8n route asks for Basic Auth.

In production, n8n stays on the private Docker app/data networks and is not published on a host port.

## Included Workflow Templates

Import these from the n8n UI via **Settings → Import from File**.

| File | Description | Phase |
|------|-------------|-------|
| `daily-portfolio-summary.json` | Daily snapshot creation and Discord confirmation | 2 |
| `urgent-alerts.json` | Polling → portfolio risk warnings → Discord alert | 2 |
| `weekly-review.json` | Sunday weekly review run and Discord delivery | 4 |
| `opportunity-scan-mwf.json` | Monday / Wednesday / Friday opportunity scan and Discord delivery | 4 |

## EchoCore API Base URL

Inside n8n, configure the EchoCore base URL as:

```
http://echo-core:8000
```

## Internal API Authentication

Protected EchoCore routes now accept an internal automation header:

```
X-Echo-Internal-Token: <value of ECHO_INTERNAL_API_TOKEN>
```

When you have more than one user, portfolio-scoped workflows must also target a concrete user:

```
X-Echo-User-Id: <user UUID from /auth/me>
```

Set the same `ECHO_INTERNAL_API_TOKEN` value for `echo-core` and `echo-n8n`. Set `ECHO_AUTOMATION_USER_ID` to the user UUID that owns the automated portfolio flows, then re-import the workflow JSON files so the header mapping is present in the HTTP nodes.

## Timezone

Set to `Europe/Warsaw` via `GENERIC_TIMEZONE` env var.
