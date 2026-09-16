# Data & Model Sources

The service is built around two independent, pluggable "source" abstractions. Each request selects a
concrete implementation through a discriminated **`type`** field — this is the "category" you configure:

| Axis                       | Request field  | `type` values      | Purpose                                             |
| -------------------------- | -------------- | ------------------ | --------------------------------------------------- |
| **Data source**            | `data_source`  | `inline`, `url`    | Where the training / forecast *input data* comes from |
| **Model source / repository** | `model_source` | `volume`, `url` | Where the trained *model artifact* is stored / loaded |

The two axes are orthogonal: you can, for example, fetch data from a `url` while persisting the model to a
local `volume`, or read inline data and push the artifact to a remote `url`.

Schemas live in [`app/schemas/common.py`](../app/schemas/common.py); the selection logic lives in
[`app/factories/`](../app/factories/). To add a new category, see [extending.md](extending.md).

---

## 1. Data sources (`data_source`)

The resolved payload must be a `ForecastTrainingInput`-shaped dict (for `/train`) or a `ForecastInput`-shaped
dict (for `/forecast`) — the same schema you would pass inline. See the
[core library](https://github.com/U2DemoProject/u2demo-time-series-forecasting-WP4T2) for those shapes.

### `inline` — payload embedded in the request

```json
{
  "data_source": {
    "type": "inline",
    "payload": {
      "forecast_type": "deterministic",
      "time_parameters": { "timestep_minutes": 60, "horizon_hours": 24 },
      "model_config": { "model_id": "house-1", "model_version": "1.0.0" },
      "target_series": {
        "series_id": "house-1",
        "variable_name": "consumption",
        "training_values": [ { "time": "2024-01-01T00:00:00Z", "value": 240.0 } ]
      }
    }
  }
}
```

### `url` — fetched from a remote HTTP endpoint

The service issues the configured request and expects a JSON body matching the input schema.

```json
{
  "data_source": {
    "type": "url",
    "request": {
      "method": "GET",
      "url": "https://data.example.org/households/house-1/training.json",
      "headers": { "Authorization": "Bearer <token>" },
      "query": { "from": "2024-01-01", "to": "2024-01-14" },
      "body": null,
      "timeout_seconds": 30,
      "retry": { "max_attempts": 3, "backoff_seconds": 1.0 }
    }
  }
}
```

Field reference: `method` (`GET`|`POST`), `url` (required), `headers`, `query`, `body` (for `POST`),
`timeout_seconds` (default 30), `retry.max_attempts` (default 1), `retry.backoff_seconds` (default 0.0).

---

## 2. Model sources (`model_source`)

`model_source` controls where the trained artifact is **written** (on `/train`) and **read** (on `/forecast`).
It is optional — when omitted it defaults to the local `volume`.

### `volume` — local mounted storage (default)

Artifacts are stored as tarballs under `MODELS_DIR` (default `storage/models/`).

```json
{ "model_source": { "type": "volume" } }
```

### `url` — remote artifact store (HTTP/HTTPS or SFTP)

The `location` object is discriminated by its `scheme`. Downloaded artifacts are cached under `CACHE_DIR`.

**HTTP / HTTPS** (`scheme: "http"` or `"https"`):

```json
{
  "model_source": {
    "type": "url",
    "location": {
      "scheme": "https",
      "url": "https://models.example.org/house-1/1.0.0.tar.gz",
      "headers": {},
      "upload_method": "PUT",
      "auth": { "token": { "env": "MODEL_STORE_TOKEN" } },
      "checksum_sha256": null,
      "timeout_seconds": 60
    }
  }
}
```

**SFTP** (`scheme: "sftp"`):

```json
{
  "model_source": {
    "type": "url",
    "location": {
      "scheme": "sftp",
      "host": "sftp.example.org",
      "port": 22,
      "username": "svc-forecast",
      "remote_path": "/models/house-1/1.0.0.tar.gz",
      "auth": { "private_key_path": { "env": "SFTP_KEY_PATH" } },
      "timeout_seconds": 60
    }
  }
}
```

### Authentication and secrets

Auth blocks accept a literal value **or** an `{"env": "VAR_NAME"}` reference (`EnvRef`) that is resolved from
the worker's environment at call time — prefer `env` so secrets never travel in request bodies.

| Location | `auth` options |
| -------- | -------------- |
| HTTP/HTTPS | `{"username": ..., "password": ...}` (Basic) · `{"token": ...}` (Bearer) · `null` |
| SFTP       | `{"password": ...}` · `{"private_key_path": ...}` |

`checksum_sha256`, when set, is verified against the downloaded artifact and mismatches are rejected.

---

## 3. Precedence: `data_source` vs typed input

Both `/train` and `/forecast` accept the typed input **and** a `data_source` as alternatives. The typed field
always wins when both are present:

| Endpoint    | Typed field (wins)         | Fallback                                  |
| ----------- | -------------------------- | ----------------------------------------- |
| `/train`    | `forecast_training_input`  | `data_source` (payload → `ForecastTrainingInput`) |
| `/forecast` | `forecast_input`           | `data_source` (payload → `ForecastInput`) |

At least one of the two must be provided, or the request fails validation. A `data_source` whose resolved
payload does not validate against the expected schema returns `422` with a `SourceValidationError` detail.

---

## 4. Security note (host allow-lists)

`ALLOWED_DATA_HOSTS` and `ALLOWED_MODEL_HOSTS` are defined in [settings](../app/core/config.py) as
comma-separated allow-lists (default `*`). **They are currently reserved and not yet enforced** — any
reachable host is accepted. Until enforcement lands, treat `url` sources as trusted-input only and run the
worker where outbound access is already network-restricted.
