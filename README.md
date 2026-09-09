# Weather Statistics API

A small Django REST API that returns the **minimum, maximum, average** and **median temperature** for a city over a given number of days, sourced live from [WeatherAPI.com](https://www.weatherapi.com/).

Built with production-grade concerns i.e timeouts, retries, a circuit breaker, caching, rate limiting, input validation, structured errors treated as first-class requirements rather than afterthoughts, since a public facing weather endpoint is only as reliable as its handling of a flaky upstream.

## Contents

- [Requirements](#requirements)
- [Setup](#setup)
- [Usage](#usage)
- [API](#api)
- [Architecture](#architecture)
- [Testing](#testing)
- [Development](#development)
- [Docker](#docker)

## Requirements

- Python 3.11+
- A free [WeatherAPI.com](https://www.weatherapi.com/signup.aspx) API key

## Setup

1. Clone the repository and `cd` into it.
2. Create and activate a virtualenv:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   make deps
   ```
4. Copy `.env.example` to `.env` and fill in `WEATHERAPI_KEY`:
   ```bash
   cp .env.example .env
   ```
5. Apply migrations:
   ```bash
   make migrate
   ```
6. Run the dev server:
   ```bash
   make runserver
   ```

The API is now live at `http://127.0.0.1:8000/`.

## Usage

```bash
curl "http://127.0.0.1:8000/api/locations/London/?days=2"
```

```json
{
  "maximum": 27.4,
  "minimum": 18.1,
  "average": 22.6,
  "median": 22.9
}
```

- **Swagger UI:** `http://127.0.0.1:8000/api/docs/`
- **ReDoc:** `http://127.0.0.1:8000/api/redoc/`
- **Raw OpenAPI schema:** `http://127.0.0.1:8000/api/schema/`
- **Django admin:** `http://127.0.0.1:8000/admin/` (run `make superuser` first)
- **Health check:** `http://127.0.0.1:8000/healthz/`: health endpoint that checks DB and cache connectivity, not just that the process is up.

## API

### `GET /api/locations/{city}/?days={number_of_days}`

| Param  | Where | Required | Default | Notes                                                                 |
|--------|-------|----------|---------|------------------------------------------------------------------------|
| `city` | path  | yes      | —       | City name, e.g. `Nairobi`, `London`.                                   |
| `days` | query | no       | `1`     | 1 to `WEATHER_MAX_FORECAST_DAYS` (3 by default. WeatherAPI's free-tier forecast limit). |

**Success  `200 OK`**
```json
{"maximum": 27.4, "minimum": 18.1, "average": 22.6, "median": 22.9}
```

**Errors**  every error response has the same shape, so clients can branch on `code`:
```json
{"error": {"code": "not_found", "message": "No weather data found for city 'Nowhereville'"}}
```

| Status | `code`                | Cause                                                              |
|--------|-----------------------|---------------------------------------------------------------------|
| 400    | `invalid`             | `days` missing or non-numeric or out of range, or an otherwise bad request. |
| 404    | `not_found`           | The provider has no data for that city.                             |
| 429    | `throttled`           | Rate limit exceeded (`THROTTLE_RATE_LOCATIONS`, default 30/min).    |
| 502    | `bad_gateway`         | The provider responded, but with data we couldn't parse.            |
| 503    | `service_unavailable` | The provider is down, misconfigured credentials, or the circuit breaker is open (includes a `Retry-After` header when the circuit is open). |
| 504    | `gateway_timeout`     | The provider didn't respond within the configured timeout.          |

## Architecture

```
weather_api/
├── config/            settings, root urls, wsgi/asgi
├── common/            cross cutting utilities:
│   ├── circuit_breaker.py  circuit breaker
│   ├── http.py              shared requests.Session with retry and backoff
│   └── exceptions.py        uniform {"error": {code, message}} structured error message
└── locations/         the business domain
    ├── clients/weatherapi.py   WeatherAPI.com client
    ├── serializers.py          request and response schemas
    ├── services.py             min, max, avg, median computation
    ├── views.py                
    └── urls.py
tests/                 mirrors the app tree
```

**Resilience and Reliability:**

- **Timeouts**: every upstream call has an explicit connect and a read timeout so a hung
  provider can never hang a request thread indefinitely.
- **Retries**: we  mount a `urllib3.Retry` policy
  that retries connection errors e.g 502,503,504 with backoff, since those
  can be plausibly transient.
- **Circuit breaker**: a naive impelmentation of a cache backed circuit breaker with its states:-  closed, open and half-open kept in
  Django's cache rather than process memory, so it works correctly across multiple worker processes. It opens only on
  timeouts/connection failures. Once open, calls fail fast with status `503` and `Retry-After` in the header instead of piling up doomed requests
  hammering an upstream service that's already down.
- **Caching**: a successful forecast is cached with cache key comprising f  `city` and`days` for `WEATHER_CACHE_TTL_SECONDS` which is 10 minutes by default, so repeat lookups don't hit the upstream service.
- **Rate limiting**: DRF ratelimmiting implemented to protect the API from abuse or any DDOS attacks.
- **Input validation**: `days` is validated and range checked by a serializer before any network call is made.


## Testing

```bash
make test
```

56 tests, 100% coverage (gate: 100%, `pytest.ini`), covering:

- `tests/common/test_circuit_breaker.py` — closed → open → half-open → closed/open transitions, and that non-upstream exceptions never trip it.
- `tests/common/test_exceptions.py` — the uniform error envelope, the `Retry-After` header, and the generic-500 fallback for a truly unexpected exception.
- `tests/common/test_views.py` — the `/healthz/` probe under healthy and unhealthy DB/cache conditions.
- `tests/locations/test_weatherapi_client.py` — every error path (not found, bad auth, malformed payload, non-JSON error body, timeout, connection error), cache hits, and that the breaker actually stops calling the session once open.
- `tests/locations/test_services.py` — the statistics math itself (even/odd-length series, negatives, single values).
- `tests/locations/test_serializers.py` — `days` validation boundaries.
- `tests/locations/test_views.py` — the full request pipeline through `APIClient`, including that Swagger/OpenAPI are actually served and that `Retry-After` reaches the client.

No real network calls are made in tests — the `requests.Session` is injected and mocked at the client boundary.

## Development

```bash
make format   # isort + black
make lint     # flake8
make all      # format + lint + test
```

CI (`.github/workflows/ci.yml`) runs the same lint, format and test steps on every push and PR.

## Docker

```bash
make docker-up
```