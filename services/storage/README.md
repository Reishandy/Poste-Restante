# Poste Restante — Storage Service

A stateless, blind key-value storage node designed to store encrypted mailbox payloads. The service never inspects plaintext, operates independently without coordinating with other storage nodes, and maintains zero identity or session state—holding opaque ciphertext behind capability tokens until retrieved or expired.

---

## 1. Quick Start

### Prerequisites
* Docker and Docker Compose (recommended), or Python 3.14+ with a running MongoDB 7.x instance.

### Run with Docker Compose
```bash
cp .env.example .env
docker compose up --build -d
```
The service will start listening on port `8000` (configurable via `APP_PORT`).

### Run for Local Development
```bash
docker run -d --name mongo -p 27017:27017 mongo:7

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
  "app": "Poste Restante Storage Service",
  "service": "storage",
  "version": "1.0.0",
  "database": "ok",
  "hpke_public_key": "3z5V9k2t1Q...base64..."
}
```
> *Note:* The returned `hpke_public_key` is this node's public identity key, required by clients to seal encrypted requests.

---

## 2. Communicating with the Service

All external interactions pass through two public endpoints:

| Endpoint | Method | Authentication | Description |
|---|---|---|---|
| `/` | `GET` | None | Health check and node HPKE public key |
| `/ohttp` | `POST` | HPKE (RFC 9458) | Encapsulated gateway for all mailbox operations |

Direct external access to `/mailbox/*` routes is forbidden (`403 Forbidden`). All mailbox read, write, and delete operations must be submitted as the **inner payload** of an Oblivious HTTP (OHTTP) envelope to ensure the storage node never learns client network identities.

### Client Workflow
1. **Retrieve Identity Key:** Fetch the node's HPKE public key via `GET /` (or obtain it from a directory).
2. **Build Inner Request:** Construct the intended `/mailbox/{mailbox_id}` request formatted as Binary HTTP (BHTTP, RFC 9292).
3. **Solve PoW (Writes Only):** For `PUT` operations, compute a Proof-of-Work nonce meeting the current target difficulty and attach the `X-PoW-Nonce` header.
4. **Encapsulate:** Seal the BHTTP request bytes with HPKE according to RFC 9458 using the node's public key.
5. **Send via Relay:** Transmit the encapsulated envelope via `POST /ohttp` (typically dispatched through an independent proxy relay).
6. **Decapsulate Response:** Decrypt the returning `message/ohttp-res` envelope to recover the inner HTTP response code and body.

---

## 3. Mailbox API (Inner Endpoints)

These endpoints run behind the OHTTP gateway and are accessible only when encapsulated inside a BHTTP message.

### Store Mailbox
Stores encrypted content under a unique mailbox identifier. Requires Proof-of-Work verification.

* **Method:** `PUT`
* **Path:** `/mailbox/{mailbox_id}`
* **Headers:**
  * `Content-Type: application/json`
  * `X-PoW-Nonce: <mined_nonce>`
* **Request Body:**
  ```json
  {
    "content": "<ciphertext_string>",
    "token": "<capability_token>"
  }
  ```
* **Responses:**
  * `201 Created` — Payload stored successfully (`{"detail": "ok"}`).
  * `400 Bad Request` — Invalid or expired Proof-of-Work nonce, or the `mailbox_id` already exists (write-once; cannot be overwritten).
  * `422 Unprocessable Content` — Missing required fields.

### Retrieve Mailbox
Fetches stored content using the bearer capability token established during write. This operation is non-destructive (does not delete on read).

* **Method:** `GET`
* **Path:** `/mailbox/{mailbox_id}`
* **Headers:**
  * `X-Ownership-Token: <capability_token>`
* **Responses:**
  * `200 OK` — `{"detail": "ok", "content": "<ciphertext_string>"}`
  * `400 Bad Request` — Invalid token or non-existent/expired mailbox ID (identical response to prevent mailbox enumeration).
  * `422 Unprocessable Content` — Missing `X-Ownership-Token` header.

### Delete Mailbox
Deletes stored content after successful client retrieval.

* **Method:** `DELETE`
* **Path:** `/mailbox/{mailbox_id}`
* **Headers:**
  * `X-Ownership-Token: <capability_token>`
* **Responses:**
  * `200 OK` — `{"detail": "ok"}` (idempotent; returns success whether the mailbox existed or was previously deleted).
  * `400 Bad Request` — Invalid capability token.
  * `422 Unprocessable Content` — Missing `X-Ownership-Token` header.

---

## 4. Client Proof-of-Work (PoW)

To deter write-spam without maintaining client IP state or session accounts, `PUT /mailbox/{mailbox_id}` requires a Proof-of-Work nonce passed via the `X-PoW-Nonce` header. Reads (`GET`) and deletes (`DELETE`) do not require PoW because they are gated by ownership tokens.

### How the Challenge Works
* **Epoch:** Current Unix timestamp divided into windows: `epoch = floor(unix_time / POW_EPOCH_WINDOW_SECONDS)` (default 600s / 10 minutes).
* **Challenge String:** Formatted as `"{epoch}:{mailbox_id}:{nonce}"`.
* **Condition:** `SHA-256(challenge)` must contain at least `POW_DIFFICULTY_BITS` (default `18`) consecutive leading zero bits (~262,144 hash evaluations, ~100ms on a mobile device).
* **Drift Tolerance:** The server verifies against `epoch`, `epoch - 1`, and `epoch + 1` to accommodate network latency and slight clock drift.
* **Replay Protection:** The nonce is strictly bound to the target `mailbox_id` and cannot be replayed on another mailbox.

### Client Solver Implementation
```python
import hashlib
import time

def count_leading_zero_bits(digest: bytes) -> int:
    zeros = 0
    for byte in digest:
        if byte == 0:
            zeros += 8
        else:
            zeros += 8 - byte.bit_length()
            break
    return zeros

def solve_pow(mailbox_id: str, difficulty: int = 18, epoch_window: int = 600) -> str:
    """Mines a valid nonce string for the current epoch window."""
    epoch = int(time.time() // epoch_window)
    nonce = 0
    while True:
        candidate = str(nonce)
        challenge = f"{epoch}:{mailbox_id}:{candidate}".encode("utf-8")
        digest = hashlib.sha256(challenge).digest()
        
        if count_leading_zero_bits(digest) >= difficulty:
            return candidate
        nonce += 1
```

---

## 5. Configuration

Configured using environment variables or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Poste Restante Storage Service` | Service name shown in health check responses |
| `APP_PORT` | `8000` | Port published by the service container |
| `DEV_MODE` | `false` | When true, includes unhandled exception details in responses |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection URI |
| `MONGO_DB_NAME` | `poste_restante_storage_db` | Target MongoDB database name |
| `MONGO_PASSWORD` | *(None)* | Root password for database authentication (required for Compose) |
| `MAILBOX_EXPIRY_SECONDS` | `7776000` (90 days) | TTL index interval for purging uncollected mailboxes |
| `HPKE_KEY_DIR` | `./data/keys` | Directory holding `private.key` and `public.key`. Must be persisted. |
| `POW_DIFFICULTY_BITS` | `18` | Leading zero bits required for PoW validation (~262k hash rounds) |
| `POW_EPOCH_WINDOW_SECONDS` | `600` (10 min) | Freshness window duration for PoW epochs |

---

## 6. Testing

Run automated tests against an active MongoDB instance:

```bash
pytest
```