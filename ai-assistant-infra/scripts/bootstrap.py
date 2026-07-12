#!/usr/bin/env python3
import os
import time

import psycopg2
from psycopg2 import sql


def get_env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def wait_for_postgres(host, user, password, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(
                host=host,
                port=5432,
                user=user,
                password=password,
                dbname="postgres",
            )
            conn.close()
            return
        except psycopg2.OperationalError:
            time.sleep(2)
    raise RuntimeError(f"Postgres not ready after {timeout}s")


def ensure_database(cur, db_name):
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if not cur.fetchone():
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        print(f"Created database: {db_name}")
    else:
        print(f"Database already exists: {db_name}")


def ensure_user(cur, username, password):
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
    if not cur.fetchone():
        cur.execute(
            sql.SQL("CREATE USER {} WITH ENCRYPTED PASSWORD %s").format(sql.Identifier(username)),
            (password,),
        )
        print(f"Created user: {username}")
    else:
        print(f"User already exists: {username}")


def grant_schema_permissions(db_name, user_name):
    with psycopg2.connect(
        host=get_env("POSTGRES_HOST", "postgres"),
        port=5432,
        user=get_env("POSTGRES_DB_USER", "postgres"),
        password=get_env("POSTGRES_DB_PASSWORD"),
        dbname=db_name,
    ) as conn, conn.cursor() as cur:
        cur.execute(
            sql.SQL("REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT ALL ON SCHEMA public TO {};").format(
                sql.Identifier(user_name)
            )
        )
        print(f"Granted schema permissions for {user_name} on {db_name}")


def main():
    wait_for_postgres(
        get_env("POSTGRES_HOST", "postgres"),
        get_env("POSTGRES_DB_USER", "postgres"),
        get_env("POSTGRES_DB_PASSWORD"),
    )

    databases = [
        get_env("AIASSIST_DB_NAME", "aiassistant"),
        get_env("AIASSIST_DEV_DB_NAME", "aiassistant_dev"),
        get_env("AIASSIST_LIVE_DB_NAME", "aiassistant_live"),
        get_env("N8N_DB_NAME", "n8n"),
        get_env("LANGGRAPH_DB_NAME", "langgraph"),
        get_env("LANGGRAPH_DEV_DB_NAME", "langgraph_dev"),
        get_env("LANGGRAPH_LIVE_DB_NAME", "langgraph_live"),
        get_env("LANGFUSE_DB_NAME", "langfuse"),
        get_env("OPENOBSERVE_DB_NAME", "openobserve_db"),
        get_env("LITELLM_DB_NAME", "litellm"),
        get_env("LITELLM_DEV_DB_NAME", "litellm_dev"),
        get_env("LITELLM_LIVE_DB_NAME", "litellm_live"),
        get_env("CLICKHOUSE_DB_NAME", "clickhouse"),
        get_env("OPENHANDS_DB_NAME", "openhands"),
        get_env("TEAMCITY_DB_NAME", "teamcity"),
    ]

    users = []
    for user_var, pass_var in [
        ("AIASSIST_DB_USER", "AIASSIST_DB_PASSWORD"),
        ("AIASSIST_DEV_DB_USER", "AIASSIST_DEV_DB_PASSWORD"),
        ("AIASSIST_LIVE_DB_USER", "AIASSIST_LIVE_DB_PASSWORD"),
        ("N8N_DB_USER", "N8N_DB_PASSWORD"),
        ("LANGGRAPH_DB_USER", "LANGGRAPH_DB_PASSWORD"),
        ("LANGGRAPH_DEV_DB_USER", "LANGGRAPH_DEV_DB_PASSWORD"),
        ("LANGGRAPH_LIVE_DB_USER", "LANGGRAPH_LIVE_DB_PASSWORD"),
        ("LANGFUSE_DB_USER", "LANGFUSE_DB_PASSWORD"),
        ("OPENOBSERVE_DB_USER", "OPENOBSERVE_DB_PASSWORD"),
        ("LITELLM_DB_USER", "LITELLM_DB_PASSWORD"),
        ("LITELLM_DEV_DB_USER", "LITELLM_DEV_DB_PASSWORD"),
        ("LITELLM_LIVE_DB_USER", "LITELLM_LIVE_DB_PASSWORD"),
        ("CLICKHOUSE_DB_USER", "CLICKHOUSE_DB_PASSWORD"),
        ("OPENHANDS_DB_USER", "OPENHANDS_DB_PASSWORD"),
        ("TEAMCITY_DB_USER", "TEAMCITY_DB_PASSWORD"),
    ]:
        username = os.environ.get(user_var)
        password = os.environ.get(pass_var)
        if username and password:
            users.append((username, password))

    db_user_map = []
    for db_var, user_var in [
        ("AIASSIST_DB_NAME", "AIASSIST_DB_USER"),
        ("AIASSIST_DEV_DB_NAME", "AIASSIST_DEV_DB_USER"),
        ("AIASSIST_LIVE_DB_NAME", "AIASSIST_LIVE_DB_USER"),
        ("N8N_DB_NAME", "N8N_DB_USER"),
        ("LANGGRAPH_DB_NAME", "LANGGRAPH_DB_USER"),
        ("LANGGRAPH_DEV_DB_NAME", "LANGGRAPH_DEV_DB_USER"),
        ("LANGGRAPH_LIVE_DB_NAME", "LANGGRAPH_LIVE_DB_USER"),
        ("LANGFUSE_DB_NAME", "LANGFUSE_DB_USER"),
        ("OPENOBSERVE_DB_NAME", "OPENOBSERVE_DB_USER"),
        ("LITELLM_DB_NAME", "LITELLM_DB_USER"),
        ("LITELLM_DEV_DB_NAME", "LITELLM_DEV_DB_USER"),
        ("LITELLM_LIVE_DB_NAME", "LITELLM_LIVE_DB_USER"),
        ("CLICKHOUSE_DB_NAME", "CLICKHOUSE_DB_USER"),
        ("OPENHANDS_DB_NAME", "OPENHANDS_DB_USER"),
        ("TEAMCITY_DB_NAME", "TEAMCITY_DB_USER"),
    ]:
        db = os.environ.get(db_var)
        user = os.environ.get(user_var)
        if db and user:
            db_user_map.append((db, user))

    with psycopg2.connect(
        host=get_env("POSTGRES_HOST", "postgres"),
        port=5432,
        user=get_env("POSTGRES_DB_USER", "postgres"),
        password=get_env("POSTGRES_DB_PASSWORD"),
        dbname="postgres",
    ) as conn, conn.cursor() as cur:
        for db in databases:
            ensure_database(cur, db)
        for username, password in users:
            ensure_user(cur, username, password)
        for db_name, user_name in db_user_map:
            cur.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC;").format(sql.Identifier(db_name))
            )
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {};").format(
                    sql.Identifier(db_name), sql.Identifier(user_name)
                )
            )
            cur.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO {};").format(
                    sql.Identifier(db_name), sql.Identifier(user_name)
                )
            )
            print(f"Applied database permissions for {user_name} on {db_name}")

    for db_name, user_name in db_user_map:
        grant_schema_permissions(db_name, user_name)

    print("Bootstrap complete")


if __name__ == "__main__":
    main()
