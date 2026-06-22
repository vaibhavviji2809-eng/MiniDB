# MiniDB

MiniDB is a small educational database engine that walks through the classic layers of a database system:

SQL -> Lexer -> Parser -> Planner -> Optimizer -> Storage Engine -> Execution Engine -> Result

It now also includes:

- cost-based planning
- hash, merge, nested-loop, and index joins
- MVCC-style versioned rows
- multiple buffer pool strategies
- `EXPLAIN` / `EXPLAIN ANALYZE`
- row-store and column-store tables
- vectorized filter and projection steps

## Run

```bash
python -m MiniDB.cli.main
```

## Example

```sql
CREATE TABLE users (
    id INT,
    name STRING,
    age INT
);

INSERT INTO users VALUES (1,"Vaibhav",20);

SELECT name
FROM users
WHERE age > 18;
```

```sql
EXPLAIN ANALYZE
SELECT users.name, orders.total
FROM users
JOIN orders ON users.id = orders.user_id;
```
