[![Deploy to CMO Studio](https://studio.cmopartners.co/deploy-button.svg)](https://studio.cmopartners.co/deploy?repo=https://github.com/cmo-partners-as/cmo-studio-template-booking)

# Booking app

**For AI agents:** read [AGENTS.md](AGENTS.md) and the CMO Studio guide at https://studio.cmopartners.co/llms.txt.

A small booking page. Visitors pick a free time slot, leave their name and email, and get a confirmation email. Bookings are saved in Postgres. You see them in a simple `/admin` list.

Built with Flask. Runs on [CMO Studio](https://studio.cmopartners.co/?ref=template-booking).

## How it works

- The home page shows free slots: Monday to Friday, 09:00 to 16:00, one slot per hour, for the next two weeks.
- A slot can only be booked once.
- `/admin` shows all bookings. The browser asks for a password: use `ADMIN_PASSWORD` (any username).
- If the database is not linked yet, the app starts and shows a page that says what to do.

## Environment variables

| Name | Needed | What it does |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection URL. Set when you link a database in CMO Studio. |
| `ADMIN_PASSWORD` | yes | Password for `/admin`. |
| `MAIL_FROM` | for email | Sender address, on your verified domain. |
| `CMO_MAIL_API_KEY`, `CMO_MAIL_URL` | for email | Set by CMO Studio when email is enabled. |
| `BUSINESS_NAME` | no | Name on the page and in emails. |
| `OWNER_EMAIL` | no | Get a copy of every new booking. |

Without the mail variables the app still works. It skips the email and writes a line to the log.

## Run locally

```
pip install -r requirements.txt
DATABASE_URL=postgresql://user:pass@localhost:5432/db ADMIN_PASSWORD=secret python app.py
```

## Change it with your AI agent

- "Change the opening hours to 10:00 to 18:00 and add Saturdays."
- "Add a phone number field to the booking form and show it in /admin."
- "Make slots 30 minutes long and let me cancel a booking from /admin."

## License

MIT
