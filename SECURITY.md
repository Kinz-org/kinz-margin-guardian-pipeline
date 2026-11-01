# Security Policy

## Supported Versions

Only the latest `main` branch is supported with security updates.

## Reporting a Vulnerability

Email: nassim@kinzoils.com

Please include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You will receive a response within 48 hours.

## Security Measures

- API endpoints use JWT authentication (HS256, expiry from `JWT_EXPIRE_MINUTES`).
  There is a single API user from `API_USER`/`API_PASSWORD`; every token carries
  `role: admin` and no route checks roles yet.
- Rate limiting via `slowapi` on API routes (default 120 requests/minute)
- The API password is compared to the `API_PASSWORD` env var; it is not hashed or
  stored in the database.
- No audit log of mutations yet.
- PostgreSQL with connection pooling
- Docker container isolation

## Dependencies

Dependencies are pinned where possible. The API requires
`fastapi httpx PyJWT slowapi` for the test suite to run in CI.
