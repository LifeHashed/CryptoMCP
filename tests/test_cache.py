from crypto_market_mcp.cache import TTLCache


def test_ttl_cache_get_set_and_expiry(monkeypatch):
    cache = TTLCache(ttl_seconds=1, maxsize=2)

    fake_time = 1000.0

    def _time():
        return fake_time

    # Patch the time.time function used inside the cache module
    import crypto_market_mcp.cache as cache_module
    monkeypatch.setattr(cache_module, "time", type("_T", (), {"time": staticmethod(_time)})())

    cache.set("a", 1)
    assert cache.get("a") == 1

    # Advance time beyond TTL
    fake_time = 1002.0
    assert cache.get("a") is None
