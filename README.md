# Study Planner

A shared study planner with browser-local study tasks and PostgreSQL-backed reminders.

## Repository layout

- `api/` — Python reminder API and PostgreSQL migration
- `web/` — static browser application and nginx configuration
- `tests/` — dependency-free unit and repository contract tests

## Test locally

```bash
python3 -m unittest discover -s tests -v
docker build -t study-planner-api:test ./api
docker build -t study-planner-web:test ./web
```

## Contributing

Fork this repository, create a branch, run the tests above, and open a pull request. Pull requests run only on GitHub-hosted runners and cannot access deployment secrets.
