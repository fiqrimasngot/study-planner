# Contributing

1. Fork the repository and branch from `main`.
2. Make one focused change with tests.
3. Run `python3 -m unittest discover -s tests -v`.
4. Run both Docker build commands from `README.md`.
5. Open a pull request and explain the user-visible change.

Do not include credentials, database contents, private URLs, or generated Python cache files. Maintainers merge only after the `CI / test` and `CI / docker-build` checks pass.
