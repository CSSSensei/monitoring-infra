import asyncio
import logging
import os
import time

import aiohttp
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

BUCKETS = [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]


def make_metrics(registry: CollectorRegistry):
    return {
        "up": Gauge("proxy_up", "Proxy availability (1=up, 0=down)", registry=registry),
        "duration": Histogram(
            "proxy_request_duration_seconds",
            "Proxy request latency in seconds",
            buckets=BUCKETS,
            registry=registry,
        ),
        "checks": Counter(
            "proxy_check_total",
            "Total proxy checks",
            ["result"],
            registry=registry,
        ),
    }


async def check_proxy(proxy_url: str, target_url: str, timeout: float, metrics: dict) -> None:
    start = time.monotonic()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                target_url,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                await resp.read()
        duration = time.monotonic() - start
        metrics["duration"].observe(duration)
        metrics["up"].set(1)
        metrics["checks"].labels(result="success").inc()
    except asyncio.TimeoutError:
        metrics["up"].set(0)
        metrics["checks"].labels(result="timeout").inc()
    except Exception as exc:
        logger.warning("proxy check failed: %s", exc)
        metrics["up"].set(0)
        metrics["checks"].labels(result="error").inc()


async def run(proxy_url: str, port: int, interval: float, target: str, timeout: float) -> None:
    from prometheus_client import REGISTRY
    metrics = make_metrics(REGISTRY)
    start_http_server(port)
    logger.info("proxy_exporter listening on :%d", port)
    while True:
        await check_proxy(proxy_url, target, timeout, metrics)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        run(
            proxy_url=os.environ["PROXY_URL"],
            port=int(os.environ.get("METRICS_PORT", "9200")),
            interval=float(os.environ.get("CHECK_INTERVAL", "30")),
            target=os.environ.get("TARGET_URL", "https://api.telegram.org"),
            timeout=float(os.environ.get("TIMEOUT", "10")),
        )
    )
