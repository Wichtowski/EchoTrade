# docker-mailserver for EchoTrade invites

This folder contains the local mail setup used to send EchoTrade invite emails.

## What this is for

- `echo-core` creates the invite link.
- If SMTP is configured, `echo-core` also sends the invite email.
- `docker-mailserver` is the SMTP/IMAP server for that delivery path.

## 1. Start the mail server

```bash
make mail-up
```

## 2. Create a mailbox account

Use the docker-mailserver setup utility from the running container:

```bash
docker exec -it echotrade-echo-mail-1 setup email add echotrade@oskarwichtowski.com 'change-this-password'
```

If your container name differs, replace `echotrade-echo-mail-1` with the actual one from `docker ps`.

## 3. Point EchoTrade to that mailbox

Set these values in `.env`:

```bash
ECHO_MAIL_HOSTNAME=mail
ECHO_MAIL_DOMAIN=oskarwichtowski.com
ECHO_SMTP_HOST=echo-mail
ECHO_SMTP_PORT=587
ECHO_SMTP_USERNAME=echotrade@oskarwichtowski.com
ECHO_SMTP_PASSWORD=change-this-password
ECHO_SMTP_FROM_EMAIL=echotrade@oskarwichtowski.com
ECHO_SMTP_FROM_NAME=EchoTrade
ECHO_SMTP_STARTTLS=false
ECHO_SMTP_SSL=false
```

Then restart `echo-core`.

## 4. Share the right public app URL

Invite links are built from:

```bash
ECHO_PUBLIC_APP_URL=http://localhost:3000
```

For a deployed server, set this to your real HTTPS app URL before sending invites.

## Notes

- The compose service is intended as a private/self-hosted mail path.
- The bundled local config starts without TLS, so keep it for private/dev use only.
- For real-world remote delivery, you will still want a proper domain, DNS, SPF, DKIM, and TLS setup.
- If SMTP is not configured yet, the Access page still works and lets you copy invite links manually.
- Revoking an accepted invite from the Access page removes that invited user account and deletes their private portfolio data.
