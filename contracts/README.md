# Contracts and examples

The proposed API agreement is `docs/05-API-CONTRACT.md`. JSON files here are **test/design examples**, not production datasets or proof of implemented endpoints. The application must read real PostgreSQL data. Example dates are illustrative and must not be hard-coded into the production clock.

`billing-vectors.json` defines six arithmetic cases, a partial/full payment case and four calendar-anchor cases. `scripts/check_pack.py` verifies these examples independently. It does not test the application's future implementation, concurrency or authorization.

After implementing the API, Midhun P M exports its actual OpenAPI to contracts/openapi.json and the coordinator compares it with the agreed contract. Do not hand-author a success-only fake API and call it complete.
