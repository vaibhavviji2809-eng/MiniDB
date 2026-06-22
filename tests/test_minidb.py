import unittest
import tempfile
from pathlib import Path

from MiniDB.engine import DatabaseEngine
from MiniDB.lexer import Lexer
from MiniDB.parser import Parser


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
        self.assertEqual(stmt.table, "users")
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


if __name__ == "__main__":
    unittest.main()
