# MiniDB

MiniDB is a small educational database engine that walks through the classic layers of a database system:

SQL -> Lexer -> Parser -> Planner -> Optimizer -> Storage Engine -> Execution Engine -> Result

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

