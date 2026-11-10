# Study Planner

A shared study planner with browser-local study tasks and PostgreSQL-backed reminders.

## Repository layout

- `api/` — Python reminder API and PostgreSQL migration
- `web/` — static browser application and nginx configuration
- `tests/` — dependency-free unit and repository contract tests

## Test locally

```bash
python3 -m unittest discover -s tests -v
node --test tests/test_web_notifications.cjs
docker build -t study-planner-api:test ./api
docker build -t study-planner-web:test ./web
```

## Contributing

Fork this repository, create a branch, run the tests above, and open a pull request. Pull requests run only on GitHub-hosted runners and cannot access deployment secrets.

While the website is open, it checks shared reminders every 15 seconds and shows an in-page notification when another visitor adds, edits, completes, reopens, or deletes one. The first load and your own changes do not notify you. Notifications do not appear when the website is closed.
