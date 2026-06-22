from __future__ import annotations

from .ast import (
    BeginStatement,
    BinaryExpression,
    CommitStatement,
    CreateTableStatement,
    DeleteStatement,
    DropTableStatement,
    ExplainStatement,
    Identifier,
    JoinClause,
    InsertStatement,
    Literal,
    RollbackStatement,
    SelectStatement,
    TableRef,
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
        if self._match("EXPLAIN"):
            analyze = self._match("ANALYZE")
            return ExplainStatement(self._statement(), analyze=analyze)
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
        table = self._table_ref()
        joins = []
        while self._match("JOIN", "INNER", "LEFT", "RIGHT"):
            join_type = self.previous().type
            if join_type in {"LEFT", "RIGHT"} and self._match("OUTER"):
                join_type = f"{join_type} OUTER"
                self._consume("JOIN")
            elif join_type != "JOIN":
                self._consume("JOIN")
            join_table = self._table_ref()
            condition = None
            if self._match("ON"):
                condition = self._expression()
            joins.append(JoinClause(join_type, join_table, condition))
        where = None
        if self._match("WHERE"):
            where = self._expression()
        return SelectStatement(columns, table, joins, where)

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
        storage_format = "row"
        if self._match("STORAGE"):
            if self._match("COLUMN"):
                storage_format = "column"
            elif self._match("ROW"):
                storage_format = "row"
            else:
                raise ParseError("Expected COLUMN or ROW after STORAGE")
        return CreateTableStatement(table, columns, storage_format)

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
            return Identifier(self._qualified_identifier())
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

    def _table_ref(self):
        name = self._consume_identifier()
        alias = None
        if self._match("AS"):
            alias = self._consume_identifier()
        elif self._check("IDENTIFIER"):
            alias = self._advance().value
        return TableRef(name, alias)

    def _consume_identifier(self):
        if self._check("IDENTIFIER"):
            return self._qualified_identifier()
        raise ParseError("Expected identifier")

    def _qualified_identifier(self):
        value = self._advance().value
        if self._match("DOT"):
            value = f"{value}.{self._consume_identifier()}"
        return value

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
