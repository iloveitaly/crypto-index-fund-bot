from vcr.persisters.deduplicated_filesystem import DeduplicatedFilesystemPersister

def pytest_recording_configure(config, vcr):
  vcr.register_persister(DeduplicatedFilesystemPersister)
