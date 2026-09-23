import os
import unittest
from unittest.mock import patch, Mock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app
from public_api import PredictionGuard, check_configuration


class PublicApiTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"APP_ENV": "development", "RENDER": "", "STOCK_API_TOKEN": "test-token",
            "API_REQUESTS_PER_MINUTE": "30", "API_DAILY_COMPUTE_LIMIT": "200", "API_CACHE_TTL_SECONDS": "3600"})
        env.start()
        self.addCleanup(env.stop)

    def test_authentication_prevents_compute(self):
        with TestClient(app) as client, patch("main.predict_stock") as compute:
            self.assertEqual(client.get("/predict/AAPL").status_code, 401)
            self.assertEqual(client.get("/predict/AAPL", headers={"X-API-Key": "wrong"}).status_code, 401)
            compute.assert_not_called()
            self.assertEqual(client.get("/").status_code, 200)

    def test_authenticated_request_and_cache(self):
        with TestClient(app) as client, patch("main.guard", PredictionGuard()), patch("main.predict_stock", return_value={"classification": {"mode": "jev"}}) as compute:
            first = client.get("/predict/AAPL?horizon_years=3", headers={"X-API-Key": "test-token"})
            second = client.get("/predict/AAPL?horizon_years=3", headers={"X-API-Key": "test-token"})
            self.assertFalse(first.json()["cache_hit"])
            self.assertTrue(second.json()["cache_hit"])
            compute.assert_called_once_with("AAPL", 3)

    def test_limits_and_busy(self):
        guard = PredictionGuard()
        compute = Mock(return_value={"classification": {"mode": "jev"}})
        with patch.dict(os.environ, {"API_DAILY_COMPUTE_LIMIT": "1"}):
            guard.run("one", compute)
            self.assertTrue(guard.run("one", compute)["cache_hit"])
            with self.assertRaises(HTTPException) as error:
                guard.run("two", compute)
            self.assertEqual(error.exception.status_code, 429)
        guard.work.acquire()
        try:
            with self.assertRaises(HTTPException) as error:
                guard.run("two", compute)
            self.assertEqual(error.exception.status_code, 503)
        finally:
            guard.work.release()
        with patch.dict(os.environ, {"API_REQUESTS_PER_MINUTE": "1"}):
            with self.assertRaises(HTTPException) as error:
                guard.run("one", compute)
            self.assertEqual(error.exception.status_code, 429)

    def test_expiration_and_failures(self):
        guard = PredictionGuard()
        compute = Mock(return_value={"classification": {"mode": "jev"}})
        with patch("public_api.time.monotonic", return_value=0):
            guard.run("one", compute)
        with patch("public_api.time.monotonic", return_value=3601):
            self.assertFalse(guard.run("one", compute)["cache_hit"])
        self.assertEqual(compute.call_count, 2)
        compute.return_value = {"classification": {"mode": "unavailable"}}
        guard.run("failure", compute)
        guard.run("failure", compute)
        self.assertEqual(compute.call_count, 4)

    def test_production_fails_closed(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "STOCK_API_TOKEN": ""}):
            with self.assertRaises(RuntimeError):
                check_configuration()


if __name__ == "__main__":
    unittest.main()
