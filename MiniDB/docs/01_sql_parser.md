# SQL Parser

MiniDB tokenizes SQL text into a token stream and then uses a recursive-descent parser to build an AST.

Supported statements:

- `CREATE TABLE`
- `INSERT INTO`
- `SELECT`
- `UPDATE`
- `DELETE`
- `DROP TABLE`
- `BEGIN`, `COMMIT`, `ROLLBACK`

