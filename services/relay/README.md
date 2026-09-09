# Poste Restante — Relay Service

A stateless, blind Oblivious HTTP (OHTTP, RFC 9458) relay service designed to decouple client network identity from upstream storage gateways. The relay blindly forwards encapsulated binary payloads without decrypting or inspecting contents, strips client-identifying HTTP headers, enforces per-IP rate limits, and returns encapsulated responses directly to the caller.

## 1. Quick Start

### Prerequisites
* Docker and Docker Compose (recommended), or Python 3.14+.

### Run with Docker Compose
```bash
cp .env.example .env
docker compose up --build -d
```
The service will start listening on port `8000` (configurable via `APP_PORT`).

### Run for Local Development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
fastapi dev src/main.py
```

### Verify Service Status
```bash
curl http://localhost:8000/
```
Expected response:
```json
{
  "detail": "ok",
  "app": "Poste Restante Relay Service",
  "service": "relay",
  "version": "1.0.0"
}
```

## 2. Communicating with the Service

All external interactions pass through the public health check or the blind forwarding endpoints:

| Endpoint | Method | Headers / Params | Description |
|---|---|---|---|
| `/` | `GET` | None | Operational status and service identification |
| `/relay` | `POST` | `Target-URI` header or `?target=` | Forwards encapsulated binary OHTTP request upstream |
| `/ohttp` | `POST` | `Target-URI` header or `?target=` | Unlisted compatibility alias for `/relay` |

### Target Destination Resolution
The client must supply the upstream gateway URL through one of two methods:
* **HTTP Header:** `Target-URI: http://storage.internal:8000/ohttp`
* **Query Parameter:** `POST /relay?target=http://storage.internal:8000/ohttp`

If both are provided, the `Target-URI` header takes precedence.

### Header Stripping & Privacy Guarantees
To prevent the upstream storage service from linking requests to a client IP or browser fingerprint, the relay strips all incoming client headers. The upstream dispatch forwards exclusively:
* The exact binary encapsulated request body (`message/ohttp-req`).
* `Content-Type: message/ohttp-req`.

Client IP addresses, `User-Agent`, `Cookie`, `Authorization`, and custom client headers are never forwarded to the destination node.

### Request Flow
1. **Client Encapsulation:** The client serializes a Binary HTTP request (RFC 9292) and encrypts it with the target storage node's HPKE public key to form an RFC 9458 envelope.
2. **Relay Dispatch:** The client issues `POST /relay` (with `Target-URI`) sending raw bytes with `Content-Type: message/ohttp-req`.
3. **Upstream Forwarding:** The relay verifies the media type, applies rate limits, strips client headers, and posts the binary payload to the target storage gateway.
4. **Response Delivery:** The storage node responds with an HPKE-sealed response (`message/ohttp-res`), which the relay streams back to the client.

## 3. Relay API

### Forward Encapsulated Request
Blindly transmits an encapsulated binary payload to the requested storage destination.

* **Method:** `POST`
* **Path:** `/relay` (or `/ohttp`)
* **Query Parameters:**
  * `target` *(optional)*: Upstream destination gateway URI.
* **Headers:**
  * `Content-Type: message/ohttp-req` *(required)*
  * `Target-URI: <gateway_url>` *(required if `target` query param is absent)*
* **Request Body:** Raw binary RFC 9458 encapsulated bytes (`message/ohttp-req`).
* **Responses:**
  * `200 OK` — Upstream gateway processed the request; body contains encapsulated response payload (`message/ohttp-res`).
  * `400 Bad Request` — Missing destination URI or empty request payload.
  * `415 Unsupported Media Type` — `Content-Type` header is not `message/ohttp-req`.
  * `429 Too Many Requests` — Per-IP rate limit quota exceeded.
  * `502 Bad Gateway` — Upstream destination is unreachable, refused connection, or failed network I/O.
  * `504 Gateway Timeout` — Upstream connection or read exceeded `REQUEST_TIMEOUT_SECONDS`.

## 4. Rate Limiting

To prevent DoS abuse while maintaining zero disk persistence, the relay implements an in-memory sliding-window limiter keyed by client IP:

* **Window Duration:** Configurable via `RATE_LIMIT_WINDOW_SECONDS` (default: 60s).
* **Request Quota:** Configurable via `RATE_LIMIT_REQUESTS` (default: 60 requests per window).
* **Rejection Response:** Returns `429 Too Many Requests` with a `Retry-After: <seconds>` header indicating when the oldest request exits the sliding window.
* **Memory Management:** Once active tracked client IPs exceed 5,000, expired IP records are automatically purged to prevent memory growth.

## 5. Configuration

Configured using environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Poste Restante Relay Service` | Instance name returned in health checks |
| `APP_PORT` | `8000` | Port published by the service container |
| `APP_VERSION` | `1.0.0` | Service version identifier |
| `DEV_MODE` | `false` | When true, includes unhandled exception traces in 500 responses |
| `REQUEST_TIMEOUT_SECONDS` | `15.0` | Read and write timeout when forwarding to the storage node |
| `RATE_LIMIT_REQUESTS` | `60` | Maximum requests permitted per client IP within the sliding window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Duration of the rate limiter sliding window in seconds |

## 6. Testing

Execute unit and integration tests with `pytest`:

```bash
pytest
```