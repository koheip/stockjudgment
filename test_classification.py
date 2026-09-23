import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
import streamlit as st
import streamlit.errors
from streamlit.testing.v1 import AppTest
from main import app, classify_company, classify_with_ai, predict_stock
from fastapi.testclient import TestClient
from evidence import annual_records, evidence_coverage, collect_evidence
import pandas as pd


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"TYPESAFE_API_KEY": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.good = dict(revenueGrowth=.05, earningsGrowth=.05, operatingMargins=.1,
                         returnOnEquity=.1, freeCashflow=1, debtToEquity=100, trailingPE=25)

    def test_positive_and_negative(self):
        self.assertEqual(classify_company(self.good)["category"], "GROW")
        self.assertEqual(classify_company(dict.fromkeys(self.good, 0))["category"], "LOW_GROWTH")

    def test_missing_and_nonfinite(self):
        self.assertEqual(classify_company({})["category"], "HOLD")
        self.good["earningsGrowth"] = float("nan")
        self.assertEqual(classify_company(self.good)["category"], "HOLD")

    def test_sixty_percent_boundary(self):
        data = dict(revenueGrowth=.05, earningsGrowth=.05, operatingMargins=.1,
                    returnOnEquity=0, freeCashflow=0)
        self.assertEqual(classify_company(data)["score"], 60)
        self.assertEqual(classify_company(data)["category"], "GROW")
        data["operatingMargins"] = .09
        self.assertEqual(classify_company(data)["category"], "LOW_GROWTH")

    @patch("main.yf.Ticker")
    def test_api(self, ticker):
        ticker.return_value.get_info.return_value = dict(self.good, quoteType="EQUITY", shortName="Example", currency="USD")
        result = predict_stock("aapl", horizon_years=3)
        self.assertEqual(result["prediction_horizon_years"], 3)
        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["classification"]["category"], "HOLD")
        self.assertEqual(result["classification"]["mode"], "unavailable")
        ticker.return_value.get_info.return_value = {"quoteType": "ETF"}
        with self.assertRaises(HTTPException) as raised:
            predict_stock("ETF")
        self.assertEqual(raised.exception.status_code, 422)
        ticker.return_value.get_info.side_effect = RuntimeError("unavailable")
        with self.assertRaises(HTTPException) as raised:
            predict_stock("AAPL")
        self.assertEqual(raised.exception.status_code, 502)

    def test_ui_results(self):
        result = dict(ticker="AAPL", company_name="Example", currency="USD", financial_currency="USD",
                      latest_price=100, sector="Technology", retrieved_at="2026-09-23",
                      classification=classify_company(self.good))
        with patch("requests.get") as request:
            request.return_value.ok = True
            request.return_value.json.return_value = result
            at = AppTest.from_file("front.py").run()
            at.text_area[0].set_value("AAPL")
            at.number_input[0].set_value(5)
            at.button[0].click().run()
            self.assertEqual(request.call_args.kwargs["params"], {"horizon_years": 5})
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.metric[0].value, "1社")
        self.assertTrue(any('comparison-table' in m.value and 'AAPL' in m.value for m in at.markdown))

    def test_cloud_rejects_local_api(self):
        with patch("streamlit.context", SimpleNamespace(url="https://example.streamlit.app")), patch.dict(os.environ, {"STOCK_API_URL": "http://localhost:8001"}), patch("requests.get") as request:
            at = AppTest.from_file("front.py").run()
            at.button[0].click().run()
            self.assertEqual(len(at.exception), 0)
            self.assertTrue(any("ローカル用" in error.value for error in at.error))
            request.assert_not_called()

    def test_cloud_requires_token(self):
        with patch("streamlit.context", SimpleNamespace(url="https://example.streamlit.app")), patch.dict(os.environ, {"STOCK_API_URL": "https://mirai-stock-api.onrender.com", "STOCK_API_TOKEN": ""}), patch("requests.get") as request:
            at = AppTest.from_file("front.py").run()
            at.button[0].click().run()
            self.assertEqual(len(at.exception), 0)
            self.assertTrue(any("トークンが未設定" in error.value for error in at.error))
            request.assert_not_called()

    def test_cloud_reports_invalid_secrets_toml(self):
        with patch("streamlit.context", SimpleNamespace(url="https://example.streamlit.app")), patch.dict(os.environ, {"STOCK_API_URL": "https://mirai-stock-api.onrender.com", "STOCK_API_TOKEN": ""}), patch("requests.get") as request:
            at = AppTest.from_file("front.py").run()
            error = st.errors.StreamlitSecretNotFoundError("Error parsing secrets file at x.toml: invalid char")
            with patch.object(type(st.secrets), "items", side_effect=error):
                at.button[0].click().run()
            self.assertTrue(any("書き方に誤り" in e.value for e in at.error))
            request.assert_not_called()

    def test_cloud_finds_token_in_section_or_lowercase(self):
        with patch("streamlit.context", SimpleNamespace(url="https://example.streamlit.app")), patch.dict(os.environ, {"STOCK_API_URL": "https://mirai-stock-api.onrender.com", "STOCK_API_TOKEN": ""}), patch("requests.get") as request:
            request.return_value.ok, request.return_value.status_code = False, 401
            request.return_value.json.return_value = {"detail": "x"}
            at = AppTest.from_file("front.py")
            at.secrets["general"] = {"stock_api_token": ' "abc" '}
            at.run()
            at.button[0].click().run()
            self.assertEqual(request.call_args.kwargs["headers"], {"X-API-Key": "abc"})

    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"})
    @patch("main.TypeSafeClient")
    def test_ai_overrides_screening(self, factory):
        client = factory.return_value.__enter__.return_value
        client.system_one.return_value = SimpleNamespace(model="jev-test", choices={
            "growth": SimpleNamespace(choice="LOW_GROWTH", confidence=.8)})
        result = classify_with_ai("TEST", {}, classify_company(self.good), horizon_years=3)
        self.assertEqual(client.system_one.call_args.kwargs["state"]["horizon_years"], 3)
        self.assertIn("3年後", client.system_one.call_args.kwargs["questions"]["growth"]["instructions"])
        self.assertEqual(result["category"], "LOW_GROWTH")
        self.assertEqual(result["screening_category"], "GROW")
        self.assertEqual(result["mode"], "jev")
        self.assertEqual(result["confidence"], .8)
        self.assertNotIn("score", client.system_one.call_args.kwargs["state"])

    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"})
    @patch("main.TypeSafeClient")
    def test_ai_failure_and_invalid_response(self, factory):
        client = factory.return_value.__enter__.return_value
        for choice, confidence in [("UNKNOWN", .8), ("GROW", float("nan")), ("GROW", 2)]:
            client.system_one.return_value = SimpleNamespace(model="jev-test", choices={
                "growth": SimpleNamespace(choice=choice, confidence=confidence)})
            result = classify_with_ai("TEST", {}, classify_company(self.good))
            self.assertEqual(result["category"], "HOLD")
            self.assertEqual(result["mode"], "unavailable")
        client.system_one.side_effect = RuntimeError("secret-key")
        result = classify_with_ai("TEST", {}, classify_company(self.good))
        self.assertNotIn("secret-key", str(result))
        self.assertEqual(result["mode"], "unavailable")

    @patch("main.TypeSafeClient")
    def test_insufficient_data_skips_ai(self, factory):
        result = classify_with_ai("TEST", {}, classify_company({}))
        self.assertEqual(result["mode"], "insufficient_data")
        factory.assert_not_called()

    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "無効なキー"})
    @patch("main.TypeSafeClient")
    def test_invalid_key_skips_ai(self, factory):
        result = classify_with_ai("TEST", {}, classify_company(self.good))
        self.assertEqual(result["mode"], "unavailable")
        self.assertIn("形式が不正", result["status_message"])
        factory.assert_not_called()

    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"})
    @patch("main.TypeSafeClient")
    def test_missing_growth_still_calls_ai(self, factory):
        client = factory.return_value.__enter__.return_value
        client.system_one.return_value = SimpleNamespace(model="jev-test", choices={
            "growth": SimpleNamespace(choice="GROW", confidence=.55)})
        screening = classify_company({"operatingMargins": .2, "freeCashflow": 100})
        result = classify_with_ai("TEST", {}, screening)
        self.assertEqual(result["mode"], "jev")
        self.assertEqual(result["screening_category"], "HOLD")
        self.assertEqual(result["category"], "GROW")

    def test_invalid_horizons_rejected_before_fetch(self):
        with patch("main.yf.Ticker") as ticker, TestClient(app) as client:
            for value in [0, -1, 31, "1.5", "invalid"]:
                self.assertEqual(client.get("/predict/AAPL", params={"horizon_years": value}).status_code, 422)
            ticker.assert_not_called()

    def test_annual_evidence_supplies_missing_fields(self):
        frame = pd.DataFrame({pd.Timestamp("2025-12-31"): [120, -5], pd.Timestamp("2024-12-31"): [100, 10]}, index=["Total Revenue", "Net Income"])
        records = annual_records(frame, ["Total Revenue", "Net Income", "Operating Income"])
        self.assertEqual(records[0]["Net Income"], -5)
        self.assertNotIn("Operating Income", records[0])
        self.assertEqual(evidence_coverage(classify_company({}), {"income": records}), ["growth", "profitability"])
        self.assertEqual(evidence_coverage(classify_company({}), {"price_history": {"price_cagr": .2}}), [])

    def test_failed_optional_sources_do_not_discard_income(self):
        from unittest.mock import MagicMock
        stock = MagicMock()
        stock.get_income_stmt.return_value = pd.DataFrame({pd.Timestamp("2025-12-31"): [10]}, index=["Net Income"])
        stock.get_cash_flow.side_effect = RuntimeError()
        stock.get_balance_sheet.side_effect = RuntimeError()
        stock.history.side_effect = RuntimeError()
        evidence = collect_evidence(stock)
        self.assertEqual(evidence["income"][0]["Net Income"], 10)
        self.assertEqual(len(evidence["warnings"]), 2)


if __name__ == "__main__":
    unittest.main()
