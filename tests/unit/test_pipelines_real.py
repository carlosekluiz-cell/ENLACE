"""Unit tests for pipeline real data download/transform logic.

Uses mocked HTTP responses to test each pipeline's transform logic
without hitting real APIs.
"""
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# --- HTTP Client Tests ---

class TestPipelineHTTPClient:
    """Test the shared HTTP client."""

    @patch("python.pipeline.http_client.httpx.Client")
    def test_get_json_retries_on_500(self, mock_client_cls):
        from python.pipeline.http_client import PipelineHTTPClient

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # First call returns 500, second returns 200
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.headers = {}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"data": "ok"}
        resp_200.raise_for_status = MagicMock()

        mock_client.request.side_effect = [resp_500, resp_200]

        client = PipelineHTTPClient(base_delay=0.01)
        client._client = mock_client
        result = client.get_json("https://example.com/api")
        assert result == {"data": "ok"}
        assert mock_client.request.call_count == 2

    def test_resolve_ckan_resource_url(self):
        from python.pipeline.http_client import PipelineHTTPClient

        client = PipelineHTTPClient()
        mock_response = {
            "result": {
                "resources": [
                    {"format": "CSV", "url": "https://dados.gov.br/download/file.csv"},
                    {"format": "JSON", "url": "https://dados.gov.br/download/file.json"},
                ]
            }
        }
        with patch.object(client, "get_json", return_value=mock_response):
            url = client.resolve_ckan_resource_url("test-dataset")
            assert url == "https://dados.gov.br/download/file.csv"

    def test_resolve_ckan_no_csv_falls_back(self):
        from python.pipeline.http_client import PipelineHTTPClient

        client = PipelineHTTPClient()
        mock_response = {
            "result": {
                "resources": [
                    {"format": "XLSX", "url": "https://dados.gov.br/download/file.xlsx"},
                ]
            }
        }
        with patch.object(client, "get_json", return_value=mock_response):
            url = client.resolve_ckan_resource_url("test-dataset")
            assert url == "https://dados.gov.br/download/file.xlsx"


# --- IBGE Census Pipeline Tests ---

class TestIBGECensusPipeline:
    """Test IBGE census transform logic with mocked API responses."""

    def test_transform_municipalities(self):
        from python.pipeline.flows.ibge_census import IBGECensusPipeline

        pipeline = IBGECensusPipeline()
        raw_data = {
            "municipalities": [
                {
                    "id": 3550308,
                    "nome": "São Paulo",
                    "microrregiao": {
                        "mesorregiao": {
                            "UF": {"id": 35, "sigla": "SP"}
                        }
                    },
                },
                {
                    "id": 3304557,
                    "nome": "Rio de Janeiro",
                    "microrregiao": {
                        "mesorregiao": {
                            "UF": {"id": 33, "sigla": "RJ"}
                        }
                    },
                },
            ],
            "states": [
                {"id": 35, "nome": "São Paulo", "sigla": "SP"},
                {"id": 33, "nome": "Rio de Janeiro", "sigla": "RJ"},
            ],
            "state_boundaries": {},
            "population": [
                {"D3C": "3550308", "V": "11451245"},
                {"D3C": "3304557", "V": "6211423"},
            ],
        }

        result = pipeline.transform(raw_data)

        assert len(result["states"]) == 2
        assert len(result["municipalities"]) == 2
        sp_mun = result["municipalities"][result["municipalities"]["name"] == "São Paulo"]
        assert len(sp_mun) == 1
        assert sp_mun.iloc[0]["population"] == 11451245


# --- IBGE PIB Pipeline Tests ---

class TestIBGEPIBPipeline:
    """Test IBGE PIB transform logic."""

    @patch("python.pipeline.flows.ibge_pib.IBGEPIBPipeline._get_connection")
    def test_transform_pib_values(self, mock_conn):
        from python.pipeline.flows.ibge_pib import IBGEPIBPipeline

        # Mock DB connection
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [("3550308", 1)],  # code_to_l2
            [(1, 11000000)],   # l2_pop
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
        mock_conn.return_value.cursor.return_value = mock_cur

        pipeline = IBGEPIBPipeline()
        raw_data = {
            "pib": [
                {"D3C": "3550308", "V": "699288", "D2C": "2021"},
            ]
        }

        result = pipeline.transform(raw_data)
        assert len(result) == 1
        assert result.iloc[0]["pib_municipal_brl"] == 699288000.0  # Multiplied by 1000
        assert result.iloc[0]["year"] == 2021


# --- Anatel Base Stations Tests ---

class TestDMSConversion:
    """Test DMS to decimal coordinate conversion."""

    def test_dms_south_west(self):
        from python.pipeline.flows.anatel_base_stations import dms_to_decimal

        # 23°32'15"S -> -23.5375
        result = dms_to_decimal('23°32\'15"S')
        assert result is not None
        assert abs(result - (-23.5375)) < 0.001

    def test_already_decimal(self):
        from python.pipeline.flows.anatel_base_stations import dms_to_decimal

        result = dms_to_decimal("-23.5375")
        assert result == -23.5375

    def test_none_input(self):
        from python.pipeline.flows.anatel_base_stations import dms_to_decimal

        assert dms_to_decimal(None) is None
        assert dms_to_decimal("") is None
        assert dms_to_decimal("nan") is None


# --- Anatel Broadband Pipeline Tests ---

class TestAnatelBroadbandTransform:
    """Test broadband CSV column mapping and subscriber parsing."""

    def test_subscriber_count_parsing(self):
        """Test that dot-formatted subscriber counts are parsed correctly."""
        # "1.234.567" should become 1234567
        raw = "1.234.567"
        result = int(raw.replace(".", "").replace(",", ""))
        assert result == 1234567

    def test_tech_map_covers_all_variants(self):
        from python.pipeline.flows.anatel_broadband import TECH_MAP

        assert TECH_MAP["Fibra Óptica"] == "fiber"
        assert TECH_MAP["Cabo Coaxial / HFC"] == "cable"
        assert TECH_MAP["xDSL"] == "dsl"
        assert TECH_MAP["Satélite"] == "satellite"
        assert TECH_MAP["Rádio"] == "wireless"


# --- INMET Weather Pipeline Tests ---

class TestINMETValueParsing:
    """Test INMET sentinel value handling."""

    def test_parse_normal_value(self):
        from python.pipeline.flows.inmet_weather import parse_inmet_value

        assert parse_inmet_value("25.3") == 25.3

    def test_parse_sentinel_values(self):
        from python.pipeline.flows.inmet_weather import parse_inmet_value

        assert parse_inmet_value("-9999") is None
        assert parse_inmet_value("-9999.0") is None
        assert parse_inmet_value("") is None
        assert parse_inmet_value(None) is None

    def test_parse_comma_decimal(self):
        from python.pipeline.flows.inmet_weather import parse_inmet_value

        assert parse_inmet_value("25,3") == 25.3


# --- ANEEL Power Pipeline Tests ---

class TestANEELVoltageClassification:
    """Test power line voltage classification."""

    def test_transmission(self):
        from python.pipeline.flows.aneel_power import classify_voltage

        assert classify_voltage(500) == "transmission"
        assert classify_voltage(230) == "transmission"

    def test_subtransmission(self):
        from python.pipeline.flows.aneel_power import classify_voltage

        assert classify_voltage(138) == "subtransmission"
        assert classify_voltage(69) == "subtransmission"

    def test_distribution(self):
        from python.pipeline.flows.aneel_power import classify_voltage

        assert classify_voltage(34.5) == "distribution"
        assert classify_voltage(13.8) == "distribution"


# --- Provider Normalizer Tests ---

class TestProviderNormalizer:
    """Test provider name normalization."""

    def test_claro_group(self):
        from python.pipeline.transformers.provider_normalizer import normalize_provider_name

        assert normalize_provider_name("CLARO S.A.") == "claro sa"
        assert normalize_provider_name("NET SERVICOS DE COMUNICACAO") == "claro sa"

    def test_vivo_group(self):
        from python.pipeline.transformers.provider_normalizer import normalize_provider_name

        assert normalize_provider_name("TELEFONICA BRASIL S.A.") == "telefonica brasil sa vivo"
        assert normalize_provider_name("VIVO S.A.") == "telefonica brasil sa vivo"
