import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp import app


ROOT = Path(__file__).resolve().parents[1]


class MarketLabUiContractTests(unittest.TestCase):
    def test_market_lab_page_is_served_without_cache(self):
        client = app.test_client()
        response = client.get("/market-lab")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        body = response.get_data(as_text=True)
        self.assertIn("Market Lab", body)
        self.assertIn("localStorage", body)
        self.assertIn("Paper Portfolio", body)
        self.assertIn("אינו נותן המלצה אישית", body)

    def test_public_market_route_sanitizes_snapshot_and_never_enables_execution(self):
        from core import paper_market
        client = app.test_client()
        snapshot = {
            "status": "AVAILABLE",
            "provider": "Twelve Data",
            "tiles": [{
                "symbol": "SPY", "name": "S&P 500 ETF", "group": "מדדי שוק",
                "kind": "index", "price": 500.0, "change_percent": 1.2,
                "change": 6.0, "currency": "USD", "provider_time": "2026-10-18",
                "status": "AVAILABLE",
            }],
            "missing_symbols": [],
            "fetched_at_utc": "2026-10-18T10:00:00+00:00",
            "cache": "MISS",
            "paper_only": True,
        }
        with patch("core.paper_market.market_snapshot", return_value=snapshot):
            response = client.get("/api/public/market-heatmap")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "AVAILABLE")
        self.assertFalse(payload["execution_enabled"])
        self.assertTrue(payload["paper_only"])
        self.assertEqual(payload["tiles"][0]["symbol"], "SPY")
        self.assertNotIn("api_key", response.get_data(as_text=True).lower())

    def test_missing_provider_returns_blocked_not_fake_quotes(self):
        client = app.test_client()
        with patch("core.paper_market.market_snapshot", return_value={
            "status": "DATA_PROVIDER_NOT_CONFIGURED", "provider": "Twelve Data",
            "tiles": [], "missing_symbols": ["SPY"], "fetched_at_utc": None,
            "cache": "MISS", "paper_only": True, "reason": "Set TWELVEDATA_API_KEY",
        }):
            response = client.get("/api/public/market-heatmap")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["tiles"], [])
        self.assertFalse(response.get_json()["execution_enabled"])

    def test_trade_terminal_links_heatmap_without_order_action(self):
        source = (ROOT / "handlers" / "trade_terminal_handler.py").read_text(encoding="utf-8")
        self.assertIn('commands=["heatmap", "market_lab"]', source)
        self.assertIn('return base + "/market-lab"', source)
        self.assertIn("תיק מדומה", source)

    def test_inline_javascript_parses_when_node_is_available(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable; CI JavaScript syntax check is optional locally")
        html = (ROOT / "market_heatmap.html").read_text(encoding="utf-8")
        start = html.index("<script>") + len("<script>")
        end = html.index("</script>", start)
        script = html[start:end]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8", delete=False) as handle:
            handle.write(script)
            script_path = handle.name
        try:
            result = subprocess.run([node, "--check", script_path], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            Path(script_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
