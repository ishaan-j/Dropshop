"""Create MongoDB indexes. Run once per environment:  python -m data.mongo_indexes  (from backend/)"""

# TODO(L4): implement with pymongo (sync is fine here)
INDEXES = {
    "purchases": [[("user_id", 1), ("purchased_at", -1)], [("status", 1)], [("product_id", 1)]],
    "claims": [[("user_id", 1), ("created_at", -1)], [("purchase_id", 1)], [("status", 1)]],
    "agent_events": [[("user_id", 1), ("time", -1)]],
    "retailer_policies": [[("retailer", 1)]],  # unique
}

if __name__ == "__main__":
    raise NotImplementedError("TODO(L4)")
