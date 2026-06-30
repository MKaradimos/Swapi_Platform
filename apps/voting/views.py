# Intentionally empty: voting is exposed through the catalog viewsets'
# `/vote/` action (apps/catalog/views.py), backed by services.py here.
# Keeping voting endpoints on the catalog routes means a client never
# needs to know voting is a separate app under the hood.
