from langchain.tools import tool
from typing import List, Optional
from pydantic import BaseModel, Field

from app.tools.db import get_conn


# Essa classe garante que o objeto de Python passe todos esses campos
class AddTransactionArgs(BaseModel):
    amount: float = Field(..., description="Valor da transação (use positivo).")
    source_text: str = Field(..., description="Texto original do usuário.")
    occurred_at: Optional[str] = Field(
        default=None,
        description="Timestamp ISO 8601; se ausente, usa NOW() no banco."
    )
    type_id: Optional[int] = Field(default=None, description="ID em transaction_types (1=INCOME, 2=EXPENSES, 3=TRANSFER).")
    type_name: Optional[str] = Field(default=None, description="Nome do tipo: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="FK de categories (opcional).")
    category_name: Optional[str] = Field(default=None, description="Nome da categoria (ex: comida, transporte, etc.)")
    description: Optional[str] = Field(default=None, description="Descrição (opcional).")
    payment_method: Optional[str] = Field(default=None, description="Forma de pagamento (opcional).")

TYPE_ALIASES = {
    "INCOME": "INCOME", "ENTRADA": "INCOME", "RECEITA": "INCOME", "SALÁRIO": "INCOME",
    "EXPENSE": "EXPENSES", "EXPENSES": "EXPENSES", "DESPESA": "EXPENSES", "GASTO": "EXPENSES",
    "TRANSFER": "TRANSFER", "TRANSFERÊNCIA": "TRANSFER", "TRANSFERENCIA": "TRANSFER"
}

TYPE_CATEGORIES = {
    # COMIDA
    "COMIDA": "comida", "ALMOÇO": "comida", "JANTAR": "comida",
    "CAFÉ": "comida", "CAFE": "comida", "RESTAURANTE": "comida",
    "LANCHONETE": "comida", "MERCADO": "comida", "SUPERMERCADO": "comida",
    "IFOOD": "comida", "UBER EATS": "comida", "DELIVERY": "comida",
    "PADARIA": "comida",

    # BESTEIRA
    "BESTEIRA": "besteira", "DOCE": "besteira", "DOCES": "besteira",
    "CHOCOLATE": "besteira", "BALAS": "besteira", "SALGADINHO": "besteira",
    "REFRIGERANTE": "besteira", "SNACK": "besteira", "FAST FOOD": "besteira",

    # ESTUDO
    "ESTUDO": "estudo", "ESCOLA": "estudo", "FACULDADE": "estudo",
    "CURSO": "estudo", "CURSOS": "estudo", "LIVRO": "estudo",
    "LIVROS": "estudo", "MATERIAL": "estudo", "CADERNO": "estudo",
    "CANETA": "estudo", "APOSTILA": "estudo", "EDUCAÇÃO": "estudo",

    # FÉRIAS
    "FÉRIAS": "férias", "FERIAS": "férias", "VIAGEM": "férias",
    "HOTEL": "férias", "POUSADA": "férias", "TURISMO": "férias", "RESORT": "férias",

    # TRANSPORTE
    "TRANSPORTE": "transporte", "UBER": "transporte", "99": "transporte",
    "TAXI": "transporte", "ÔNIBUS": "transporte", "ONIBUS": "transporte",
    "METRÔ": "transporte", "METRO": "transporte", "COMBUSTÍVEL": "transporte",
    "GASOLINA": "transporte", "ETANOL": "transporte", "DIESEL": "transporte",
    "PASSAGEM": "transporte",

    # MORADIA
    "MORADIA": "moradia", "ALUGUEL": "moradia", "CONDOMÍNIO": "moradia",
    "CONDOMINIO": "moradia", "LUZ": "moradia", "ÁGUA": "moradia",
    "AGUA": "moradia", "INTERNET": "moradia", "GÁS": "moradia",
    "GAS": "moradia", "IPTU": "moradia",

    # SAÚDE
    "SAÚDE": "saúde", "SAUDE": "saúde", "FARMÁCIA": "saúde",
    "FARMACIA": "saúde", "REMÉDIO": "saúde", "REMEDIO": "saúde",
    "MÉDICO": "saúde", "MEDICO": "saúde", "EXAME": "saúde",
    "PLANO DE SAÚDE": "saúde", "DENTISTA": "saúde",

    # LAZER
    "LAZER": "lazer", "CINEMA": "lazer", "FILME": "lazer",
    "STREAMING": "lazer", "NETFLIX": "lazer", "SPOTIFY": "lazer",
    "SHOW": "lazer", "FESTA": "lazer", "BAR": "lazer",
    "VIAGEM CURTA": "lazer",

    # CONTAS
    "CONTAS": "contas", "BOLETO": "contas", "FATURA": "contas",
    "CARTÃO": "contas", "CARTAO": "contas", "DÍVIDA": "contas",
    "DIVIDA": "contas", "PAGAMENTO": "contas",

    # INVESTIMENTO
    "INVESTIMENTO": "investimento", "AÇÃO": "investimento",
    "ACAO": "investimento", "AÇÕES": "investimento", "ACOES": "investimento",
    "CRIPTO": "investimento", "BITCOIN": "investimento",
    "RENDA FIXA": "investimento", "TESOURO": "investimento",
    "CDB": "investimento", "POUPANÇA": "investimento",

    # PRESENTE
    "PRESENTE": "presente", "PRESENTES": "presente",
    "ANIVERSÁRIO": "presente", "ANIVERSARIO": "presente",
    "NATAL": "presente", "SURPRESA": "presente",

    # OUTROS
    "OUTROS": "outros", "DIVERSOS": "outros", "VARIADO": "outros",
    "ALEATÓRIO": "outros", "ALEATORIO": "outros"
}

def _resolve_type_id(cur, type_id: Optional[int], type_name: Optional[str]) -> Optional[int]:
    if type_name:
        t = type_name.strip().upper()
        if t in TYPE_ALIASES:
            t = TYPE_ALIASES[t]
        cur.execute(
            "SELECT id FROM transaction_types WHERE UPPER(type)=%s LIMIT 1;",
            (t,)
        )
        row = cur.fetchone()
        return row[0] if row else None
    if type_id:
        return int(type_id)
    return 2  # Default EXPENSES

def _resolve_category_id(
    cur,
    category_id: Optional[int],
    category_name: Optional[str],
    source_text: Optional[str]
) -> Optional[int]:

    if category_name:
        nome = category_name.strip().upper()

        if nome in TYPE_CATEGORIES:
            nome = TYPE_CATEGORIES[nome]

        cur.execute(
            "SELECT id FROM categories WHERE UPPER(name)=%s LIMIT 1;",
            (nome.upper(),)
        )
        row = cur.fetchone()
        if row:
            return row[0]

    if source_text:
        texto = source_text.upper()

        for palavra, categoria in TYPE_CATEGORIES.items():
            if palavra in texto:
                cur.execute(
                    "SELECT id FROM categories WHERE UPPER(name)=%s LIMIT 1;",
                    (categoria.upper(),)
                )
                row = cur.fetchone()
                if row:
                    return row[0]

    if category_id:
        return int(category_id)

    return None

# Tool: add_transaction -> Insere uma nova transação no banco
@tool("add_transaction", args_schema=AddTransactionArgs)
def add_transaction(
    amount: float,
    source_text: str,
    occurred_at: Optional[str] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> dict:
    """Insere uma transação financeira no banco de dados Postgres."""

    conn = get_conn()
    cur = conn.cursor()

    try:
        resolved_type_id = _resolve_type_id(cur, type_id, type_name)
        if not resolved_type_id:
            return {"status": "error", "message": "Tipo inválido."}

        resolved_category_id = _resolve_category_id(cur, category_id, category_name, source_text)

        if occurred_at:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, type, category_id, description, payment_method, occurred_at, source_text)
                VALUES
                    (%s, %s, %s, %s, %s, %s::timestamptz, %s)
                RETURNING id, occurred_at;
                """,
                (
                    amount,
                    resolved_type_id,
                    resolved_category_id,
                    description,
                    payment_method,
                    occurred_at,
                    source_text,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO transactions
                    (amount, type, category_id, description, payment_method, occurred_at, source_text)
                VALUES
                    (%s, %s, %s, %s, %s, NOW(), %s)
                RETURNING id, occurred_at;
                """,
                (
                    amount,
                    resolved_type_id,
                    resolved_category_id,
                    description,
                    payment_method,
                    source_text,
                ),
            )

        new_id, occurred = cur.fetchone()
        conn.commit()

        return {
            "status": "ok",
            "id": new_id,
            "occurred_at": str(occurred)
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}

    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
        

class QueryTransactionsArgs(BaseModel):
    limit: int = Field(default=10, description="Número máximo de transações a retornar.")
    date: Optional[str] = Field(default=None, description="Filtrar por data no formato YYYY-MM-DD.")
    type_filter: Optional[str] = Field(default=None, description="Filtrar por tipo: INCOME | EXPENSES | TRANSFER.")
 
# Tool: query_transactions -> Busca as últimas transações
@tool(args_schema=QueryTransactionsArgs)
def query_transactions(
    limit: int = 10,
    date: Optional[str] = None,
    type_filter: Optional[str] = None,
) -> dict:
    """Lista as transações mais recentes do banco de dados, com filtros opcionais por data e tipo."""
    conn = get_conn()
    cur = conn.cursor()
 
    try:
        if type_filter:
            type_filter = TYPE_ALIASES.get(type_filter.strip().upper(), type_filter.strip().upper())
 
        cur.execute("""
            SELECT t.amount, tt.type, c.name, t.description, t.occurred_at
            FROM transactions t
            LEFT JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE (%s IS NULL OR DATE(t.occurred_at) = %s::date)
              AND (%s IS NULL OR UPPER(tt.type) = %s)
            ORDER BY t.occurred_at DESC
            LIMIT %s;
        """, (date, date, type_filter, type_filter, limit))
 
        rows = cur.fetchall()
 
        return {
            "status": "ok",
            "data": [
                {
                    "amount": r[0],
                    "type": r[1],
                    "category": r[2],
                    "description": r[3],
                    "occurred_at": str(r[4]),
                }
                for r in rows
            ]
        }
 
    finally:
        cur.close()
        conn.close()
 

# Tool: total_balance -> Calcula saldo total
@tool
def total_balance():
    """Calcula o saldo total (entradas - despesas)."""
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) -
                COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0)
            FROM transactions;
        """)

        total = cur.fetchone()[0]

        return {"status": "ok", "total_balance": float(total)}

    finally:
        cur.close()
        conn.close()


class DailyBalanceArgs(BaseModel):
    date: str = Field(..., description="Filtrar por data no formato YYYY-MM-DD.")
    
# Tool: daily_balance -> Calcula saldo de um dia específico
@tool(args_schema=DailyBalanceArgs)
def daily_balance(date: str) -> dict:
    """Calcula o saldo de um dia específico (entradas - despesas)."""
    conn = get_conn()
    cur = conn.cursor()
 
    try:
        cur.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 1 THEN amount END), 0) -
                COALESCE(SUM(CASE WHEN type = 2 THEN amount END), 0)
            FROM transactions
            WHERE DATE(occurred_at) = %s;
        """, (date,))
        total = cur.fetchone()[0]
        return {"status": "ok", "date": date, "balance": float(total)}
 
    finally:
        cur.close()
        conn.close()
        
        
def _local_date_filter_sql(field: str = "occurred_at") -> str:
    """
    Retorna um trecho SQL para filtragem por dia local em America/Sao_Paulo.
    Ex.: (occurred_at AT TIME ZONE 'America/Sao_Paulo')::date = %s::date
    """
    return f"(({field} AT TIME ZONE 'America/Sao_Paulo')::date = %s::date)"
        

class UpdateTransactionArgs(BaseModel):
    id: Optional[int] = Field(
        default=None,
        description="ID da transação a atualizar. Se ausente, será feita uma busca por (match_text + date_local)."
    )
    match_text: Optional[str] = Field(
        default=None,
        description="Texto para localizar transação quando id não for informado (busca em source_text/description)."
    )
    date_local: Optional[str] = Field(
        default=None,
        description="Data local (YYYY-MM-DD) em America/Sao_Paulo; usado em conjunto com match_text quando id ausente."
    )
    amount: Optional[float] = Field(default=None, description="Novo valor.")
    type_id: Optional[int] = Field(default=None, description="Novo type_id (1/2/3).")
    type_name: Optional[str] = Field(default=None, description="Novo type_name: INCOME | EXPENSES | TRANSFER.")
    category_id: Optional[int] = Field(default=None, description="Nova categoria (id).")
    category_name: Optional[str] = Field(default=None, description="Nova categoria (nome).")
    description: Optional[str] = Field(default=None, description="Nova descrição.")
    payment_method: Optional[str] = Field(default=None, description="Novo meio de pagamento.")
    occurred_at: Optional[str] = Field(default=None, description="Novo timestamp ISO 8601.")

@tool("update_transaction", args_schema=UpdateTransactionArgs)
def update_transaction(
    id: Optional[int] = None,
    match_text: Optional[str] = None,
    date_local: Optional[str] = None,
    amount: Optional[float] = None,
    type_id: Optional[int] = None,
    type_name: Optional[str] = None,
    category_id: Optional[int] = None,
    category_name: Optional[str] = None,
    description: Optional[str] = None,
    payment_method: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> dict:
    """
    Atualiza uma transação existente.
    Estratégias:
      - Se 'id' for informado: atualiza diretamente por ID.
      - Caso contrário: localiza a transação mais recente que combine (match_text em source_text/description)
        E (date_local em America/Sao_Paulo), então atualiza.
    Retorna: status, rows_affected, id, e o registro atualizado.
    """
    if not any([amount, type_id, type_name, category_id, category_name, description, payment_method, occurred_at]):
        return {"status": "error", "message": "Nada para atualizar: forneça pelo menos um campo (amount, type, category, description, payment_method, occurred_at)."}

    conn = get_conn()
    cur = conn.cursor()
    try:
        # Resolve target_id
        target_id = id
        if target_id is None:
            if not match_text or not date_local:
                return {"status": "error", "message": "Sem 'id': informe match_text E date_local para localizar o registro."}

            # Buscar o mais recente no dia local informado que combine o texto
            cur.execute(
                f"""
                SELECT t.id
                FROM transactions t
                WHERE (t.source_text ILIKE %s OR t.description ILIKE %s)
                  AND {_local_date_filter_sql("t.occurred_at")}
                ORDER BY t.occurred_at DESC
                LIMIT 1;
                """,
                (f"%{match_text}%", f"%{match_text}%", date_local)
            )
            row = cur.fetchone()
            if not row:
                return {"status": "error", "message": "Nenhuma transação encontrada para os filtros fornecidos."}
            target_id = row[0]

        # Resolver type_id / category_id a partir de nomes, se fornecidos
        resolved_type_id = _resolve_type_id(cur, type_id, type_name) if (type_id or type_name) else None
        resolved_category_id = category_id
        if category_name and not category_id:
            resolved_category_id = _resolve_category_id(
                cur, category_id=None, category_name=category_name, source_text=None
            )

        # Montar SET dinâmico
        sets = []
        params: List[object] = []
        if amount is not None:
            sets.append("amount = %s")
            params.append(amount)
        if resolved_type_id is not None:
            sets.append("type = %s")
            params.append(resolved_type_id)
        if resolved_category_id is not None:
            sets.append("category_id = %s")
            params.append(resolved_category_id)
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if payment_method is not None:
            sets.append("payment_method = %s")
            params.append(payment_method)
        if occurred_at is not None:
            sets.append("occurred_at = %s::timestamptz")
            params.append(occurred_at)

        if not sets:
            return {"status": "error", "message": "Nenhum campo válido para atualizar."}

        params.append(target_id)

        cur.execute(
            f"UPDATE transactions SET {', '.join(sets)} WHERE id = %s;",
            params
        )
        rows_affected = cur.rowcount
        conn.commit()

        # Retornar o registro atualizado
        cur.execute(
            """
            SELECT
              t.id, t.occurred_at, t.amount, tt.type AS type_name,
              c.name AS category_name, t.description, t.payment_method, t.source_text
            FROM transactions t
            JOIN transaction_types tt ON tt.id = t.type
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.id = %s;
            """,
            (target_id,)
        )
        r = cur.fetchone()
        updated = None
        if r:
            updated = {
                "id": r[0],
                "occurred_at": str(r[1]),
                "amount": float(r[2]),
                "type": r[3],
                "category": r[4],
                "description": r[5],
                "payment_method": r[6],
                "source_text": r[7],
            }

        return {
            "status": "ok",
            "rows_affected": rows_affected,
            "id": target_id,
            "updated": updated
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


# Exporta a lista de tools
TOOLS = [
    add_transaction,
    query_transactions,
    total_balance,
    daily_balance,
    update_transaction,
]
