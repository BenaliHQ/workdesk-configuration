"""The budget test: the word and rule limits the contract sets on itself.

The contract page is not in this repository. Give its location to the
runner with `--contract <file>`. Without it, the checks on the page are
reported as NOT RUN.

A word is anything with a letter or a digit in it. The header block at
the top of the page, table bars, dashes and arrows are not words.
"""

import os
import re
import unittest
from pathlib import Path

# The contract's "Budgets" table. Changing a number here means the
# contract changed first, with the operator's yes.
LIMITS = {
    "Rules on this page": 12,
    "Words on this page": 1800,
    "Words loaded into a session, everything counted": 3000,
    "Object types": 8,
    "Source kinds": 9,
    "Signals": 2,
    "Skills": 4,
    "Alerts a day": 1,
    "Questions Workdesk asks you": 0,
}

HAS_LETTER_OR_DIGIT = re.compile(r"[^\W_]")


def body(text):
    """The page without the header block at the top."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for number, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[number + 1:])
    return text


def words(text):
    return [word for word in body(text).split() if HAS_LETTER_OR_DIGIT.search(word)]


def section(text, heading):
    """The lines under one second-level heading."""
    found, inside = [], False
    for line in body(text).splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == heading
            continue
        if inside:
            found.append(line)
    return found


def rules(text):
    return [line for line in section(text, "The rules") if re.match(r"\d+\. ", line)]


def budget_table(text):
    table = {}
    for line in section(text, "Budgets"):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            continue
        number = cells[1].replace(",", "")
        if number.isdigit():
            table[cells[0]] = int(number)
    return table


SAMPLE = """---
type: spec
status: draft
---

# A page

Two words. **Bold counts** once each.

```
You save
   ↓
Sources
```

## The rules

**Trace**

1. First rule.
2. Second rule.

Not a rule: 3 words here.

## Budgets

| Limit | Value |
|---|---|
| Rules on this page | 12 |
| Words on this page | 1,800 |

Adding means removing.

## After

1. A numbered line outside the rules.
"""


class Counting(unittest.TestCase):
    def test_the_header_block_is_not_counted(self):
        self.assertNotIn("type:", body(SAMPLE))
        self.assertEqual(body("no header block"), "no header block")

    def test_bars_dashes_and_arrows_are_not_words(self):
        self.assertEqual(words("| a | b |\n|---|---|\n   ↓\n- one"), ["a", "b", "one"])

    def test_words_on_the_sample_page(self):
        # Counted by hand, line by line.
        self.assertEqual(len(words(SAMPLE)), 50)

    def test_only_numbered_lines_under_the_rules_heading_are_rules(self):
        self.assertEqual(rules(SAMPLE), ["1. First rule.", "2. Second rule."])

    def test_the_budget_table_is_read_with_its_commas(self):
        self.assertEqual(
            budget_table(SAMPLE),
            {"Rules on this page": 12, "Words on this page": 1800},
        )


class ContractPage(unittest.TestCase):
    def setUp(self):
        location = os.environ.get("WD_CONTRACT", "").strip()
        if not location:
            self.skipTest("NOT RUN: no contract page was given. Use --contract <file>.")
        page = Path(location).expanduser()
        self.assertTrue(page.is_file(), "There is no contract page at %s." % page)
        self.text = page.read_text(encoding="utf-8")

    def test_words_on_the_page(self):
        count = len(words(self.text))
        print("\n    words on the contract page: %d of %d"
              % (count, LIMITS["Words on this page"]))
        self.assertLessEqual(count, LIMITS["Words on this page"])

    def test_rules_on_the_page(self):
        count = len(rules(self.text))
        print("\n    rules on the contract page: %d of %d"
              % (count, LIMITS["Rules on this page"]))
        self.assertGreater(count, 0, "No rules were found on the page.")
        self.assertLessEqual(count, LIMITS["Rules on this page"])

    def test_the_limits_here_match_the_page(self):
        self.assertEqual(budget_table(self.text), LIMITS)


if __name__ == "__main__":
    unittest.main()
