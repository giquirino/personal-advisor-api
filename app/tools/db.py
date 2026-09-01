"""Acesso compartilhado ao banco de dados PostgreSQL."""

import psycopg2

from app.config import DATABASE_URL


def get_conn():
    """Cria uma conexão com o banco de dados configurado."""
    return psycopg2.connect(DATABASE_URL)
