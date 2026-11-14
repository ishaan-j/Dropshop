"""Seed demo data (see docs/data-model.md → Demo seed data).  Run:  python -m data.seed  (from backend/)

TODO(L4, with L5 for the Nessie parts):
  1. Create the demo user in Mongo (+ Nessie customer/account via finance.nessie, store ids)
  2. Insert ~5 purchases across 3 retailers (reuse shapes from app/mock_data.py)
  3. Insert 30 days of synthetic price history into Tiger Data, with a clear drop on the hero product
  4. Create matching Nessie purchases so "confirmed by your bank" works in the demo
"""

if __name__ == "__main__":
    raise NotImplementedError("TODO(L4)")
