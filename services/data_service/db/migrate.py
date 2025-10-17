import os
import sys
from pathlib import Path
from core.utils.logger import get_logger

logger = get_logger("data_service.db.migrate")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DEFAULT_SQL = MIGRATIONS_DIR / "0001_create_timescale_ticks.sql"

def _get_dsn() -> str:
    # prefer explicit timescale DSN, fallback to DATABASE_URL
    return os.getenv("TIMESCALE_DSN") or os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL")

def _split_sql(sql_text: str) -> list[str]:
    """
    Simple SQL splitter that respects single quotes, double quotes and dollar-quoted strings.
    Returns list of statements without trailing semicolon.
    """
    statements = []
    current = []
    in_single = False
    in_double = False
    in_dollar = None
    i = 0
    n = len(sql_text)
    while i < n:
        ch = sql_text[i]
        # handle dollar-quote start
        if in_dollar:
            if sql_text.startswith(in_dollar, i):
                current.append(in_dollar)
                i += len(in_dollar)
                in_dollar = None
                continue
            else:
                current.append(ch)
                i += 1
                continue
        if ch == "$":
            j = sql_text.find("$", i + 1)
            if j != -1:
                tag = sql_text[i:j+1]
                in_dollar = tag
                current.append(tag)
                i = j + 1
                continue
            else:
                current.append(ch)
                i += 1
                continue
        # handle quotes
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            i += 1
            continue
        # semicolon ends statement if not inside quotes/dollar
        if ch == ";" and not in_single and not in_double and not in_dollar:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    # final piece
    last = "".join(current).strip()
    if last:
        statements.append(last)
    return statements

def run_migration(sql_path: Path = None):
    sql_path = Path(sql_path or DEFAULT_SQL)
    if not sql_path.exists():
        logger.error("Migration file not found: %s", sql_path)
        raise SystemExit(1)

    dsn = _get_dsn()
    if not dsn:
        logger.error("No DSN found. Set TIMESCALE_DSN or DATABASE_URL in environment.")
        raise SystemExit(1)

    logger.info("Applying migration %s -> %s", sql_path.name, dsn)
    try:
        import psycopg2
        from psycopg2 import extensions
    except Exception:
        logger.exception("psycopg2 is required to run migrations")
        raise

    sql_text = sql_path.read_text(encoding="utf-8")
    statements = _split_sql(sql_text)

    conn = None
    try:
        conn = psycopg2.connect(dsn)
        # Use a normal connection for most statements
        conn.autocommit = False
        cur = conn.cursor()

        # Separate transactional and non-transactional statements
        transactional = []
        non_transactional = []
        for stmt in statements:
            upper = stmt.strip().upper()
            if "CREATE MATERIALIZED VIEW" in upper:
                non_transactional.append(stmt)
            else:
                transactional.append(stmt)

        # Execute transactional statements
        for stmt in transactional:
            try:
                cur.execute(stmt)
            except Exception:
                logger.exception("Failed to execute transactional statement: %s", stmt.splitlines()[0][:120])
                raise

        # Commit transactional statements
        try:
            conn.commit()
        except Exception:
            logger.exception("Failed to commit migrations")
            raise

        # Execute non-transactional statements in autocommit mode on the same connection
        if non_transactional:
            conn.autocommit = True
            for stmt in non_transactional:
                try:
                    logger.info("Executing non-transactional statement in autocommit")
                    cur.execute(stmt)
                except Exception:
                    logger.exception("Non-transactional statement failed")
                    raise

        logger.info("Migration applied successfully: %s", sql_path.name)
        cur.close()
    except Exception as e:
        logger.exception("Migration failed: %s", e)
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                logger.debug("Error closing connection")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as ex:
        logger.error("Migration runner exited with error: %s", ex)
        sys.exit(1)
    sys.exit(0)
