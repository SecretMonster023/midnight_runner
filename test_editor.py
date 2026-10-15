import unittest
from editor import validate


class TableValidationTests(unittest.TestCase):
    def setUp(self):
        self.article = (
            "Affiliate disclosure: We may earn a commission.\n\n"
            "## Verdict\n\n" + "A practical recommendation. " * 65 +
            "\n\n## Comparison\n\n"
            "| Product | Fit | Tradeoff |\n"
            "|---|---|---|\n"
            "| Jobber | Solo | Add-ons |\n"
            "| Housecall Pro | HVAC | Tiers |\n"
            "\n## What to verify before you buy\n\n"
            "Check costs and contract terms.\n"
            "[Jobber pricing](https://www.getjobber.com/pricing/) "
            "[Housecall Pro pricing](https://www.housecallpro.com/pricing/) "
            "[ServiceTitan pricing](https://www.servicetitan.com/pricing)\n"
        )
        self.urls = {
            "https://www.getjobber.com/pricing/",
            "https://www.housecallpro.com/pricing/",
            "https://www.servicetitan.com/pricing",
        }

    def test_three_column_table_is_one_table(self):
        self.assertNotIn("more than one comparison table", validate(self.article, self.urls))

    def test_two_tables_are_rejected(self):
        duplicate = self.article + "\n| A | B | C |\n|:---|:---:|---:|\n| 1 | 2 | 3 |\n"
        self.assertIn("more than one comparison table", validate(duplicate, self.urls))


if __name__ == "__main__":
    unittest.main()
