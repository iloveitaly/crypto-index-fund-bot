import pytest
from vcr.persisters.deduplicated_filesystem import DeduplicatedFilesystemPersister


def pytest_recording_configure(config, vcr):
    vcr.register_persister(DeduplicatedFilesystemPersister)


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "filter_headers": [
            "X-MBX-APIKEY",
            "X-CMC_PRO_API_KEY",
            # headers with random IDs which cause requests not to match
            "x-mbx-uuid",
            "X-Amz-Cf-Id",
            "Via",
            "Date",
            "Strict-Transport-Security",
        ],
        "filter_query_parameters": ["signature", "timestamp"],
        "decode_compressed_response": True,
        # in our case, binance will hit `ping` multiple times
        # https://github.com/kevin1024/vcrpy/issues/516
        "allow_playback_repeats": True,
    }


def clear_functools_cache():
    # clear all LRU cache
    # https://stackoverflow.com/questions/40273767/clear-all-lru-cache-in-python
    # these sort of hacks are making me think this is an anti-pattern
    import functools
    import gc

    gc.collect()
    wrappers = [a for a in gc.get_objects() if isinstance(a, functools._lru_cache_wrapper)]

    for wrapper in wrappers:
        wrapper.cache_clear()


# https://stackoverflow.com/questions/22627659/run-code-before-and-after-each-test-in-py-test
@pytest.fixture(autouse=True)
def clear_state():
    clear_functools_cache()

    # clear redis cache
    from django.core.cache import cache

    cache.clear()

    import bot.utils

    bot.utils._cached_result = {}

    yield
