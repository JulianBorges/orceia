"""
Testes de contrato das rotas de orçamento.
Valida que os endpoints respondem com o schema correto e que
/save-linhas NUNCA aciona a IA (OpenAI).
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def sample_linhas() -> list[dict]:
    return [
        {
            "id": f"serv_{1000000 + i}",
            "id_planilha": "planilha_test_001",
            "item": f"{i+1}.0",
            "descricao": f"Serviço de teste {i+1}",
            "und": "M2",
            "quant": 10.0,
            "preco_unitario": 50.0,
            "codigo": "",
            "ai_status": "PENDENTE",
        }
        for i in range(3)
    ]


@pytest.fixture
def auth_headers() -> dict:
    """Headers que simulam uma requisição autenticada vinda do proxy Next.js."""
    return {
        "x-api-secret": "test-secret-key",
        "x-tenant-id": "tenant_test",
    }


# -------------------------------------------------------------------
# Patch de infraestrutura (evita conexões reais)
# -------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_infrastructure():
    """
    Substitui todas as dependências de infraestrutura por mocks.
    Os testes validam a lógica das rotas, não a infraestrutura.
    """
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_conn
    mock_conn.execute = AsyncMock(return_value="DELETE 1")
    mock_conn.executemany = AsyncMock(return_value=None)
    mock_conn.fetchrow = AsyncMock(return_value={"id": "tenant_test"})

    with (
        patch("core.db.get_db_pool", return_value=mock_pool),
        patch("core.redis_client.redis_client", new=AsyncMock()),
        patch("core.config.settings.API_SECRET_KEY", "test-secret-key"),
    ):
        yield


# -------------------------------------------------------------------
# Testes de /save-linhas
# -------------------------------------------------------------------

class TestSaveLinhas:
    @pytest.mark.asyncio
    async def test_save_linhas_nao_aciona_openai(self, sample_linhas, auth_headers):
        """
        CONTRATO CRÍTICO: /save-linhas NUNCA deve chamar a OpenAI.
        Este é o Bug #5 do Post-Mortem — validar em cada refatoração.
        """
        with patch("core.ai_client.openai_client") as mock_openai:
            from main import app
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/orcamento/save-linhas",
                    json={"linhas": sample_linhas},
                    headers=auth_headers,
                )

            # A OpenAI NUNCA deve ser chamada pelo save-linhas
            mock_openai.beta.chat.completions.parse.assert_not_called()
            mock_openai.embeddings.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_linhas_retorna_200_com_linhas_validas(self, sample_linhas, auth_headers):
        """Save com linhas válidas deve retornar 200 com status success."""
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/orcamento/save-linhas",
                json={"linhas": sample_linhas},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["linhas_salvas"] == len(sample_linhas)

    @pytest.mark.asyncio
    async def test_save_linhas_retorna_200_com_lista_vazia(self, auth_headers):
        """Save com lista vazia deve retornar 200 sem erro."""
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/orcamento/save-linhas",
                json={"linhas": []},
                headers=auth_headers,
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_save_linhas_rejeita_sem_autenticacao(self, sample_linhas):
        """Requisição sem x-api-secret deve ser rejeitada com 403."""
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/orcamento/save-linhas",
                json={"linhas": sample_linhas},
                # Sem headers de autenticação
            )

        assert response.status_code == 403


# -------------------------------------------------------------------
# Testes de DELETE /linhas
# -------------------------------------------------------------------

class TestDeleteLinhas:
    @pytest.mark.asyncio
    async def test_delete_linhas_retorna_200(self, auth_headers):
        """DELETE com IDs válidos deve retornar 200."""
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                "/orcamento/linhas",
                json={"ids": ["serv_1000001", "serv_1000002"], "id_planilha": "planilha_test_001"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["removidas"] == 2

    @pytest.mark.asyncio
    async def test_delete_linhas_vazio_retorna_zero(self, auth_headers):
        """DELETE com lista vazia deve retornar 0 removidas."""
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                "/orcamento/linhas",
                json={"ids": [], "id_planilha": "planilha_test_001"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["removidas"] == 0
