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


# mock out ping; it's a useless call and causes issues with VCR
from binance.client import Client

Client.ping = lambda _self: {}
