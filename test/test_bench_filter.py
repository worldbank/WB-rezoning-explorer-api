"""Benchmark."""

from concurrent import futures
import pytest
import rasterio

# the file to test on and the filter value are hardcoded
tif = "testus-cog.tif"


def _filter(tif, window):
    with rasterio.open(tif) as src:
        arr = src.read(window=window)
        return (arr > 8000).astype(src.profile["dtype"])


def bench_filter(tif, threads):
    """Benchmark filter"""

    with rasterio.Env(NUM_THREADS="all"):
        with rasterio.open(tif) as src:
            profile = src.profile

            with rasterio.open("temp.tif", "w+", **profile) as dst:
                # Materialize a list of source block windows
                # that we will use in several statements below.
                windows = [window for ij, window in src.block_windows()]

                with futures.ThreadPoolExecutor(max_workers=threads) as executor:
                    # We map the filter function over the windows + tif
                    for window, result in zip(
                        windows, executor.map(_filter, [tif] * len(windows), windows)
                    ):
                        dst.write(result, window=window)
    return True


@pytest.mark.benchmark(warmup_iterations=0)
@pytest.mark.parametrize("threads", [1, 2, 5, 10])
def test_filter(benchmark, threads):
    """Test filter for multiple threads."""
    benchmark.name = f"{threads} threads"
    benchmark.pedantic(bench_filter, args=(tif, threads), iterations=1)
