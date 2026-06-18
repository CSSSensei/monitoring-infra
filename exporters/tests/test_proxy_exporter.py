import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import CollectorRegistry, generate_latest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from proxy_exporter import check_proxy, make_metrics


@pytest.mark.asyncio
async def test_check_proxy_success_sets_up_metric():
    registry = CollectorRegistry()
    metrics = make_metrics(registry)

    mock_response = MagicMock()
    mock_response.read = AsyncMock(return_value=b"ok")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        await check_proxy("http://proxy:1080", "https://api.telegram.org", timeout=5.0, metrics=metrics)

    output = generate_latest(registry).decode()
    assert 'proxy_up 1.0' in output
    assert 'proxy_check_total{result="success"} 1.0' in output
    assert 'proxy_request_duration_seconds' in output


@pytest.mark.asyncio
async def test_check_proxy_timeout_sets_down():
    registry = CollectorRegistry()
    metrics = make_metrics(registry)

    with patch("aiohttp.ClientSession") as mock_cls:
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_session

        await check_proxy("http://proxy:1080", "https://api.telegram.org", timeout=5.0, metrics=metrics)

    output = generate_latest(registry).decode()
    assert 'proxy_up 0.0' in output
    assert 'proxy_check_total{result="timeout"} 1.0' in output
