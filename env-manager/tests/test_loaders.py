from env_manager.loaders import DotEnvLoader, GCPSecretLoader


def test_dotenv_loader_reads_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DB_PASSWORD=secret\nPORT=1234\n")

    loader = DotEnvLoader(dotenv_path=str(env_file))

    assert loader.get("DB_PASSWORD") == "secret"
    assert loader.get("PORT") == "1234"
    assert loader.get("MISSING") is None
    assert loader.get_many(["DB_PASSWORD", "MISSING"]) == {
        "DB_PASSWORD": "secret",
        "MISSING": None,
    }

    # Ensure environment overrides .env values
    monkeypatch.setenv("DB_PASSWORD", "override")
    assert loader.get("DB_PASSWORD") == "override"


def test_gcp_loader_fetches_and_caches(mocker):
    client_mock = mocker.Mock()
    response = mocker.Mock()
    response.payload.data = b"top-secret"
    client_mock.access_secret_version.return_value = response
    mocker.patch(
        "env_manager.loaders.gcp.secretmanager.SecretManagerServiceClient",
        return_value=client_mock,
    )

    loader = GCPSecretLoader(project_id="project-123")

    assert loader.get("API_KEY") == "top-secret"
    assert loader.get("API_KEY") == "top-secret"
    client_mock.access_secret_version.assert_called_once()


def test_gcp_loader_handles_missing_secret(mocker, capsys):
    client_mock = mocker.Mock()
    from google.api_core import exceptions as gcp_exceptions

    client_mock.access_secret_version.side_effect = gcp_exceptions.NotFound(
        "missing"
    )
    mocker.patch(
        "env_manager.loaders.gcp.secretmanager.SecretManagerServiceClient",
        return_value=client_mock,
    )

    loader = GCPSecretLoader(project_id="project-123")

    assert loader.get("MISSING") is None
    captured = capsys.readouterr().out
    assert "Secret 'MISSING' not found in GCP project 'project-123'." in captured
