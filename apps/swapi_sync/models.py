# Intentionally empty: swapi_sync is a service/integration layer, not a
# data-owning app. Synced data is persisted via apps.catalog's models
# (see services/sync.py), keeping a single source of truth for catalog
# schema rather than splitting it across two apps.
