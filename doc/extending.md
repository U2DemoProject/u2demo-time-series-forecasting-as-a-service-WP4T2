# Extending the Service

The data-source and model-repository "categories" (see [sources.md](sources.md)) are resolved by small
factories keyed on a discriminated `type` field. Adding a new category is a three-step pattern in each case.

## Add a new data-source type

Say you want a `db` data source that reads the input series straight from a SQL database.

1. **Define the config schema** in [`app/schemas/common.py`](../app/schemas/common.py) with a literal `type`
   discriminator, then add it to the `DataSourceConfig` union. Keep the DSN out of the request body by
   accepting an `EnvRef` (see [sources.md](sources.md#authentication-and-secrets)):

   ```python
   class DbDataSourceConfig(BaseModel):
       type: Literal["db"]
       dsn: str | EnvRef          # e.g. {"env": "FORECAST_DB_DSN"}
       query: str                 # returns rows shaped like the target series

   DataSourceConfig = InlineDataSourceConfig | UrlDataSourceConfig | DbDataSourceConfig
   ```

2. **Implement the source** in `app/sources/` by subclassing `DataSource`, running the query, and shaping the
   rows into the payload the runtime expects (a `ForecastTrainingInput` / `ForecastInput` dict):

   ```python
   # app/sources/db_source.py
   class DbDataSource(DataSource[DbDataSourceConfig]):
       def fetch(self, config: DbDataSourceConfig) -> dict[str, Any]:
           dsn = _resolve_secret(config.dsn)          # reuse the EnvRef helper
           with connect(dsn) as conn:                 # your DB driver of choice
               rows = conn.execute(config.query).fetchall()
           return {                                   # -> ForecastInput-shaped dict
               "forecast_type": "deterministic",
               "time_parameters": {"timestep_minutes": 60, "horizon_hours": 24},
               "target_series": {
                   "series_id": "series-1",
                   "variable_name": "value",
                   "historical_values": [
                       {"time": row.time.isoformat(), "value": float(row.value)}
                       for row in rows
                   ],
               },
           }
   ```

3. **Register it** in [`app/factories/data_source_factory.py`](../app/factories/data_source_factory.py):

   ```python
   if config.type == "db":
       return DbDataSource()
   ```

A request then selects it like any other category:

```json
{ "data_source": { "type": "db", "dsn": { "env": "FORECAST_DB_DSN" }, "query": "SELECT time, value FROM readings WHERE asset_id = 'house-1' ORDER BY time" } }
```

## Add a new model-repository type

Say you want a `gcs` model store.

1. **Define the config schema** in `app/schemas/common.py` and add it to the `ModelSourceConfig` union
   (mirror `VolumeModelSourceConfig` / `UrlModelSourceConfig`).

2. **Implement the repository** in `app/repositories/` by subclassing `ModelRepository` and implementing
   `save_model`, `load_model`, and `model_exists` (see
   [`app/repositories/base.py`](../app/repositories/base.py) for the exact contract — note the
   `{model_id}_{version}/` artifact layout).

3. **Register it** in
   [`app/factories/model_repository_factory.py`](../app/factories/model_repository_factory.py):

   ```python
   if source_config.type == "gcs":
       return GcsModelRepository(...)
   ```

## Guidelines

- **Fail with typed errors.** Raise `SourceValidationError` (from `app.core.errors`) for bad upstream
  responses / config so the API surfaces a `422` rather than a `500`.
- **Resolve secrets via `EnvRef`.** Reuse the `{"env": "VAR"}` pattern instead of putting credentials in
  request bodies (see `_resolve_secret` in `app/repositories/url_repository.py`).
- **Add a test.** Mirror `tests/test_url_model_repository.py` / `tests/test_routes.py`; mock network I/O.
- **Keep the union in sync.** The `type` literal in the config schema is the single source of truth — the
  factory and the OpenAPI `/docs` schema both derive from it.
