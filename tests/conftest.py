import os
import tempfile

# Set isolation before any application imports, for every test module.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="llmerv-test-")
os.environ["ASR_PROVIDER"] = "mock"
