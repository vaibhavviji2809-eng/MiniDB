# Vectorized Execution

MiniDB uses batch helpers for filter and projection so operators can process rows in chunks instead of one row at a time.

This follows the same broad idea as modern vectorized engines like DuckDB.

