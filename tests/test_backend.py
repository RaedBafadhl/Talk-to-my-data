"""
Unit & Integration Tests for Pillar 3 (Backend & Analytics Engine)
"""

import sys
import os
import unittest
from fastapi.testclient import TestClient

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from backend.main import app
from llm.security import validate_sql
from backend.kpi import compute_kpis
from backend.formatter import format_response, detect_chart_config


class TestPillar3Backend(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_sql_security_valid(self):
        safe, msg = validate_sql(
            "SELECT product_name, SUM(quantity) FROM sales GROUP BY product_name"
        )
        self.assertTrue(safe)
        self.assertEqual(msg, "")

    def test_sql_security_invalid_mutation(self):
        safe, msg = validate_sql("DELETE FROM sales WHERE quantity < 0")
        self.assertFalse(safe)
        self.assertIn("mutating or administrative keyword detected", msg)

    def test_sql_security_multi_statement(self):
        safe, msg = validate_sql("SELECT * FROM sales; DROP TABLE products")
        self.assertFalse(safe)
        self.assertIn("forbidden pattern or multi-statement detected", msg)

    def test_kpi_computation(self):
        data = [
            {"category": "Audio", "sales": 100.0, "quantity": 2, "order_number": "O1"},
            {"category": "Audio", "sales": 200.0, "quantity": 4, "order_number": "O2"},
        ]
        kpis = compute_kpis(data)
        self.assertEqual(kpis["total_revenue"], 300.0)
        self.assertEqual(kpis["total_units"], 6)
        self.assertEqual(kpis["aov"], 150.0)
        self.assertEqual(kpis["row_count"], 2)

    def test_chart_detection_line(self):
        data = [
            {"order_date": "2025-01-01", "revenue": 5000},
            {"order_date": "2025-02-01", "revenue": 6200},
        ]
        chart = detect_chart_config(data)
        self.assertIsNotNone(chart)
        self.assertEqual(chart["type"], "line")
        self.assertEqual(chart["x_field"], "order_date")
        self.assertEqual(chart["y_field"], "revenue")

    def test_chart_detection_bar(self):
        data = [
            {"category": "Audio", "sales": 5000},
            {"category": "Computers", "sales": 12000},
            {"category": "Cameras", "sales": 3400},
            {"category": "TVs", "sales": 8900},
            {"category": "Cell Phones", "sales": 15000},
            {"category": "Games", "sales": 7200},
            {"category": "Home Appliances", "sales": 4100},
        ]
        chart = detect_chart_config(data)
        self.assertIsNotNone(chart)
        self.assertEqual(chart["type"], "bar")

    def test_format_response_structure(self):
        sql = "SELECT category, SUM(sales) as revenue FROM sales GROUP BY category"
        data = [{"category": "Audio", "revenue": 500.0}]
        res = format_response(sql, data, "Show sales by category")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["sql"], sql)
        self.assertIsInstance(res["table"], list)
        self.assertIn("summary", res)


if __name__ == "__main__":
    unittest.main()
