"""Integration tests hitting real Brazilian government APIs.

These tests verify that real APIs are accessible and return expected data.
Run with: pytest tests/integration/test_real_apis.py -v

Mark: @pytest.mark.integration — skipped by default, run with -m integration
"""
import pytest

pytestmark = pytest.mark.integration


class TestIBGEAPIs:
    """Test real IBGE REST API responses."""

    def test_municipalities_endpoint(self):
        from python.pipeline.http_client import PipelineHTTPClient

        with PipelineHTTPClient(timeout=30) as http:
            data = http.get_json(
                "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
            )
        assert isinstance(data, list)
        assert len(data) > 5000, f"Expected ~5,570 municipalities, got {len(data)}"
        # Check structure
        first = data[0]
        assert "id" in first
        assert "nome" in first

    def test_states_endpoint(self):
        from python.pipeline.http_client import PipelineHTTPClient

        with PipelineHTTPClient(timeout=30) as http:
            data = http.get_json(
                "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
            )
        assert isinstance(data, list)
        assert len(data) == 27, f"Expected 27 states, got {len(data)}"

    def test_census_population_endpoint(self):
        from python.pipeline.http_client import PipelineHTTPClient

        with PipelineHTTPClient(timeout=60) as http:
            data = http.get_json(
                "https://servicodados.ibge.gov.br/api/v3/agregados/4714"
                "/periodos/2022/variaveis/93"
                "?localidades=N6[all]&view=flat"
            )
        assert isinstance(data, list)
        assert len(data) > 5000, f"Expected ~5,570 population records, got {len(data)}"

    def test_state_boundary_geojson(self):
        from python.pipeline.http_client import PipelineHTTPClient

        with PipelineHTTPClient(timeout=30) as http:
            data = http.get_json(
                "https://servicodados.ibge.gov.br/api/v3/malhas/estados/35"
                "?formato=application/vnd.geo+json"
            )
        assert "type" in data
        assert data.get("features") or data.get("type") == "FeatureCollection"


class TestINMETAPI:
    """Test real INMET weather API."""

    def test_stations_endpoint(self):
        from python.pipeline.http_client import PipelineHTTPClient

        with PipelineHTTPClient(timeout=30) as http:
            data = http.get_json("https://apitempo.inmet.gov.br/estacoes/T")
        assert isinstance(data, list)
        assert len(data) > 400, f"Expected ~500+ stations, got {len(data)}"


class TestCKANResolution:
    """Test CKAN dataset resolution on dados.gov.br."""

    def test_resolve_broadband_dataset(self):
        from python.pipeline.http_client import PipelineHTTPClient

        with PipelineHTTPClient(timeout=30) as http:
            url = http.resolve_ckan_resource_url(
                "acessos---banda-larga-fixa",
                resource_format="CSV",
                ckan_base="https://dados.gov.br/dados/api/3/action",
            )
        assert url.startswith("http")
        assert "csv" in url.lower() or "dados" in url.lower()


class TestDataValidation:
    """Validate data quality expectations after pipeline runs."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Get database connection for validation queries."""
        import psycopg2
        from python.pipeline.config import DatabaseConfig

        config = DatabaseConfig()
        try:
            self.conn = psycopg2.connect(config.url)
            yield
            self.conn.close()
        except Exception:
            pytest.skip("Database not available")

    def test_municipalities_count(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM admin_level_2 WHERE country_code = 'BR'")
        count = cur.fetchone()[0]
        cur.close()
        assert count >= 5000, f"Expected ~5,570 municipalities, got {count}"

    def test_states_count(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM admin_level_1 WHERE country_code = 'BR'")
        count = cur.fetchone()[0]
        cur.close()
        assert count == 27, f"Expected 27 states, got {count}"

    def test_broadband_data_volume(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM broadband_subscribers")
        count = cur.fetchone()[0]
        cur.close()
        # Should have millions after real data load
        assert count > 10000, f"Expected significant broadband data, got {count}"

    def test_coordinates_within_brazil(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM base_stations
            WHERE latitude < -34 OR latitude > 6
               OR longitude < -74 OR longitude > -28
        """)
        out_of_bounds = cur.fetchone()[0]
        cur.close()
        assert out_of_bounds == 0, f"{out_of_bounds} stations outside Brazil bounds"
