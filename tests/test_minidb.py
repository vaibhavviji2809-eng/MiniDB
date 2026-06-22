import unittest
import tempfile
from pathlib import Path

from MiniDB.engine import DatabaseEngine
from MiniDB.lexer import Lexer
from MiniDB.parser import Parser
from MiniDB.planner import CostModel


class MiniDBTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "database.db"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_lexer_tokens(self):
        tokens = Lexer().tokenize("SELECT * FROM users;")
        self.assertEqual([token.type for token in tokens[:5]], ["SELECT", "STAR", "FROM", "IDENTIFIER", "SEMICOLON"])

    def test_parser_select(self):
        stmt = Parser().parse("SELECT name FROM users;")
        self.assertEqual(stmt.table.name, "users")
        self.assertEqual(stmt.columns, ["name"])

    def test_end_to_end_crud(self):
        engine = DatabaseEngine(str(self.db_path))
        engine.execute("CREATE TABLE users (id INT, name STRING, age INT);")
        engine.execute('INSERT INTO users VALUES (1,"Vaibhav",20);')
        engine.execute('INSERT INTO users VALUES (2,"Asha",17);')
        result = engine.execute("SELECT name FROM users WHERE age > 18;")
        self.assertEqual(result.rows, [{"name": "Vaibhav"}])

    def test_transaction_rollback(self):
        engine = DatabaseEngine(str(self.db_path))
        engine.execute("CREATE TABLE items (id INT, name STRING, age INT);")
        engine.execute("BEGIN;")
        engine.execute('INSERT INTO items VALUES (1,"Pen",1);')
        engine.execute("ROLLBACK;")
        result = engine.execute("SELECT * FROM items;")
        self.assertEqual(result.rows, [])

    def test_explain_and_cost_model(self):
        engine = DatabaseEngine(str(self.db_path))
        engine.execute("CREATE TABLE metrics (id INT, name STRING, age INT);")
        plan = engine.execute("EXPLAIN SELECT name FROM metrics WHERE age > 18;")
        self.assertTrue("TableScan" in plan.rows[0]["explain"] or "IndexScan" in plan.rows[0]["explain"])
        self.assertGreater(CostModel().estimate_table_scan({"row_count": 100}).total, 0)

    def test_join_query(self):
        engine = DatabaseEngine(str(self.db_path))
        engine.execute("CREATE TABLE users (id INT, name STRING, age INT);")
        engine.execute("CREATE TABLE orders (id INT, user_id INT, total INT);")
        engine.execute('INSERT INTO users VALUES (1,"Vaibhav",20);')
        engine.execute('INSERT INTO users VALUES (2,"Asha",21);')
        engine.execute('INSERT INTO orders VALUES (10,1,99);')
        result = engine.execute("SELECT users.name, orders.total FROM users JOIN orders ON users.id = orders.user_id;")
        self.assertEqual(result.rows, [{"users.name": "Vaibhav", "orders.total": 99}])

    def test_column_store(self):
        engine = DatabaseEngine(str(self.db_path))
        engine.execute("CREATE TABLE catalog (id INT, name STRING, age INT) STORAGE COLUMN;")
        engine.execute('INSERT INTO catalog VALUES (1,"Book",3);')
        result = engine.execute("SELECT name FROM catalog;")
        self.assertEqual(result.rows, [{"name": "Book"}])


if __name__ == "__main__":
    unittest.main()
