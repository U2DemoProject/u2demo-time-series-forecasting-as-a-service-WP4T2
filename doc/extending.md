# Extending the Service

The data-source and model-repository "categories" (see [sources.md](sources.md)) are resolved by small
factories keyed on a discriminated `type` field. Adding a new category is a three-step pattern in each case.

## Add a new data-source type

Say you want an `s3` data source.

1. **Define the config schema** in [`app/schemas/common.py`](../app/schemas/common.py) with a literal `type`
   discriminator, then add it to the `DataSourceConfig` union:

   ```python
   class S3DataSourceConfig(BaseModel):
       type: Literal["s3"]
       bucket: str
       key: str

   DataSourceConfig = InlineDataSourceConfig | UrlDataSourceConfig | S3DataSourceConfig
   ```

2. **Implement the source** in `app/sources/` by subclassing `DataSource` and returning a normalized dict:

   ```python
   # app/sources/s3_source.py
   class S3DataSource(DataSource[S3DataSourceConfig]):
       def fetch(self, config: S3DataSourceConfig) -> dict[str, Any]:
           ...  # download and return a ForecastTrainingInput / ForecastInput dict
   ```

3. **Register it** in [`app/factories/data_source_factory.py`](../app/factories/data_source_factory.py):

   ```python
   if config.type == "s3":
       return S3DataSource()
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
