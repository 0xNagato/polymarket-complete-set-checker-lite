import json, os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import pm_lite as L  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


def load(n):
    with open(os.path.join(FIX, n), encoding="utf-8") as fh:
        return json.load(fh)


class TestMath(unittest.TestCase):
    def test_fee_formula(self):
        # 100 shares at 0.50, 4% rate -> 100*0.04*0.25 = 1.00
        self.assertAlmostEqual(L.taker_fee(100, 0.5, 0.04), 1.0)
        self.assertEqual(L.taker_fee(100, 0.5, 0.0), 0.0)

    def test_gap_vanishes_after_fees(self):
        # 0.48 + 0.50 = 0.98 looks like a 2-cent gap; at 7% fees it is a loss
        q = L.binary_set_quote(0.48, 0.50, 100, 0.07)
        self.assertAlmostEqual(q["gap_before_fees"], 0.02)
        self.assertLess(q["profit_after_fees"], 0)
        self.assertAlmostEqual(q["fees"], 3.4972, places=4)

    def test_zero_fee_gap_survives(self):
        q = L.binary_set_quote(0.48, 0.50, 100, 0.0)
        self.assertAlmostEqual(q["profit_after_fees"], 2.0)

    def test_sell_mode(self):
        q = L.binary_set_quote(0.52, 0.50, 100, 0.0, mode="sell")
        self.assertAlmostEqual(q["profit_after_fees"], 2.0)

    def test_bad_price(self):
        with self.assertRaises(ValueError):
            L.binary_set_quote(1.2, 0.5, 10, 0.0)


class TestFixtures(unittest.TestCase):
    def setUp(self):
        self.ms = load("markets.json")
        self.books = {b["asset_id"]: b for b in load("books.json")}

    def test_efficient_market_has_no_edge(self):
        rows = L.check_market(self.ms[0], self.books)
        self.assertTrue(rows)
        self.assertTrue(all(r["profit_after_fees"] <= 0 for r in rows))

    def test_fee_rate_from_schedule_and_fallback(self):
        self.assertEqual(L.fee_rate_for(self.ms[0])[0], 0.04)
        self.assertEqual(L.fee_rate_for({})[0], L.FALLBACK_FEE_RATE)
        self.assertEqual(L.fee_rate_for({"feesEnabled": False})[0], 0.0)

    def test_market_filter(self):
        self.assertTrue(L.market_ok(self.ms[0], 1000))
        self.assertFalse(L.market_ok(self.ms[0], 10_000_000))


if __name__ == "__main__":
    unittest.main()
