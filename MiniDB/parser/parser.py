from __future__ import annotations

from .ast import (
    BeginStatement,
    BinaryExpression,
    CommitStatement,
    CreateTableStatement,
    DeleteStatement,
    DropTableStatement,
    Identifier,
    InsertStatement,
    Literal,
    RollbackStatement,
    SelectStatement,
    UpdateStatement,
)
from ..errors import ParseError
from ..lexer import Lexer, Token
from ..types import Column


class Parser:
    def __init__(self) -> None:
        self.lexer = Lexer()

    def parse(self, sql: str):
        self.tokens = self.lexer.tokenize(sql)
        self.current = 0
        statement = self._statement()
        while self._match("SEMICOLON"):
            pass
        self._consume("EOF")
        return statement

    def _statement(self):
        if self._match("SELECT"):
            return self._select()
        if self._match("INSERT"):
            return self._insert()
        if self._match("CREATE"):
            return self._create_table()
        if self._match("DROP"):
            self._consume("TABLE")
            return DropTableStatement(self._consume_identifier())
        if self._match("UPDATE"):
            return self._update()
        if self._match("DELETE"):
            return self._delete()
        if self._match("BEGIN"):
            return BeginStatement()
        if self._match("COMMIT"):
            return CommitStatement()
        if self._match("ROLLBACK"):
            return RollbackStatement()
        raise ParseError("Unsupported statement")

    def _select(self):
        columns = []
        if self._match("STAR"):
            columns = ["*"]
        else:
            columns.append(self._consume_identifier())
            while self._match("COMMA"):
                columns.append(self._consume_identifier())
        self._consume("FROM")
        table = self._consume_identifier()
        where = None
        if self._match("WHERE"):
            where = self._expression()
        return SelectStatement(columns, table, where)

    def _insert(self):
        self._consume("INTO")
        table = self._consume_identifier()
        self._consume("VALUES")
        self._consume("LPAREN")
        values = [self._literal()]
        while self._match("COMMA"):
            values.append(self._literal())
        self._consume("RPAREN")
        return InsertStatement(table, values)

    def _create_table(self):
        self._consume("TABLE")
        table = self._consume_identifier()
        self._consume("LPAREN")
        columns = [Column(self._consume_identifier(), self._consume_type())]
        while self._match("COMMA"):
            columns.append(Column(self._consume_identifier(), self._consume_type()))
        self._consume("RPAREN")
        return CreateTableStatement(table, columns)

    def _update(self):
        table = self._consume_identifier()
        self._consume("SET")
        assignments = {self._consume_identifier(): self._assignment_value()}
        while self._match("COMMA"):
            assignments[self._consume_identifier()] = self._assignment_value()
        where = None
        if self._match("WHERE"):
            where = self._expression()
        return UpdateStatement(table, assignments, where)

    def _delete(self):
        self._consume("FROM")
        table = self._consume_identifier()
        where = None
        if self._match("WHERE"):
            where = self._expression()
        return DeleteStatement(table, where)

    def _expression(self):
        left = self._operand()
        operator = self._consume("OPERATOR").value
        right = self._operand()
        expr = BinaryExpression(left, operator, right)
        while self._match("AND", "OR"):
            op = self.previous().type
            rhs = self._expression()
            expr = BinaryExpression(expr, op, rhs)
        return expr

    def _operand(self):
        if self._check("IDENTIFIER"):
            return Identifier(self._advance().value)
        return Literal(self._literal())

    def _literal(self):
        if self._match("NUMBER"):
            return self.previous().value
        if self._match("STRING_LITERAL"):
            return self.previous().value
        raise ParseError("Expected literal")

    def _assignment_value(self):
        if self._check("IDENTIFIER"):
            return Identifier(self._advance().value)
        return Literal(self._literal())

    def _consume_identifier(self):
        if self._check("IDENTIFIER"):
            return self._advance().value
        raise ParseError("Expected identifier")

    def _consume_type(self):
        if self._match("INT"):
            return "INT"
        if self._match("STRING"):
            return "STRING"
        raise ParseError("Expected column type")

    def _match(self, *types):
        if self._check(*types):
            self._advance()
            return True
        return False

    def _consume(self, token_type):
        if self._check(token_type):
            return self._advance()
        raise ParseError(f"Expected {token_type}")

    def _check(self, *types):
        if self.current >= len(self.tokens):
            return False
        return self.tokens[self.current].type in types

    def _advance(self):
        token = self.tokens[self.current]
        self.current += 1
        return token

    def previous(self):
        return self.tokens[self.current - 1]

    def _is_at_end(self):
        return self.tokens[self.current].type == "EOF"
