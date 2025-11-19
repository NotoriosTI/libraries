from env_manager import init_config, get_config, require_config

init_config(
    "config/config_vars.yaml",
    secret_origin=None,
    gcp_project_id=None,
    strict=None,
    dotenv_path=None,
    debug=True,
)
def main():
    def get_pg_dsn() -> str:
        user = get_config("DB_USER")
        password = get_config("DB_PASSWORD")
        host = get_config("DB_HOST")
        port = get_config("DB_PORT")
        db = get_config("JUAN_DB_NAME")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"

if __name__ == "__main__":
    main()