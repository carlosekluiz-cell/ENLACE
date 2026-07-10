"""Unit tests for MinTIC Broadband pipeline (Colombia).

Tests transform logic with mock Socrata broadband data to verify
technology mapping, l2_id lookups, and subscriber aggregation.
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from python.pipeline.flows.mintic_broadband import MinTICBroadbandPipeline


MOCK_BROADBAND_DATA = [
    {
        "codigo_municipio": "05001",
        "municipio": "Medellin",
        "ano": "2024",
        "trimestre": "4",
        "nit": "900123456",
        "proveedor": "CLARO",
        "tecnologia": "Fibra optica",
        "no_accesos": "150000",
    },
    {
        "codigo_municipio": "11001",
        "municipio": "Bogota",
        "ano": "2024",
        "trimestre": "4",
        "nit": "800456789",
        "proveedor": "MOVISTAR",
        "tecnologia": "HFC",
        "no_accesos": "200000",
    },
    {
        "codigo_municipio": "76001",
        "municipio": "Cali",
        "ano": "2024",
        "trimestre": "3",
        "nit": "900123456",
        "proveedor": "CLARO",
        "tecnologia": "xDSL",
        "no_accesos": "50000",
    },
    {
        "codigo_municipio": "99999",
        "municipio": "Unknown",
        "ano": "2024",
        "trimestre": "4",
        "nit": "000000000",
        "proveedor": "UNKNOWN",
        "tecnologia": "Otro",
        "no_accesos": "100",
    },
]


class TestMinTICBroadbandPipeline:
    def setup_method(self):
        self.pipeline = MinTICBroadbandPipeline()

    @patch.object(MinTICBroadbandPipeline, '_get_connection')
    @patch.object(MinTICBroadbandPipeline, '_auto_create_provider')
    def test_transform_technology_mapping(self, mock_create, mock_conn):
        """Transform should map Spanish technology names to normalized terms."""
        # Mock DB lookups
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [("05001", 1), ("11001", 2), ("76001", 3)],  # code_to_l2
            [("900123456", 10), ("800456789", 11)],        # nit_to_provider
            [],                                             # name_to_provider
        ]
        mock_conn_obj = MagicMock()
        mock_conn_obj.cursor.return_value = mock_cur
        mock_conn.return_value = mock_conn_obj

        df = pd.DataFrame(MOCK_BROADBAND_DATA)
        result = self.pipeline.transform(df)

        # Verify technology mapping
        techs = result["technology"].unique().tolist()
        assert "fiber" in techs     # Fibra optica -> fiber
        assert "cable" in techs     # HFC -> cable
        assert "dsl" in techs       # xDSL -> dsl

    @patch.object(MinTICBroadbandPipeline, '_get_connection')
    @patch.object(MinTICBroadbandPipeline, '_auto_create_provider')
    def test_transform_skips_unknown_municipalities(self, mock_create, mock_conn):
        """Transform should skip rows with municipality codes not in DB."""
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [("05001", 1), ("11001", 2), ("76001", 3)],  # No 99999
            [("900123456", 10), ("800456789", 11)],
            [],  # name_to_provider
        ]
        mock_conn_obj = MagicMock()
        mock_conn_obj.cursor.return_value = mock_cur
        mock_conn.return_value = mock_conn_obj

        df = pd.DataFrame(MOCK_BROADBAND_DATA)
        result = self.pipeline.transform(df)

        # 99999 should be excluded, leaving 3 records
        assert len(result) == 3

    @patch.object(MinTICBroadbandPipeline, '_get_connection')
    @patch.object(MinTICBroadbandPipeline, '_auto_create_provider')
    def test_transform_trimestre_to_year_month(self, mock_create, mock_conn):
        """Transform should map trimestre (quarter) to last month of quarter."""
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [("05001", 1), ("11001", 2), ("76001", 3)],
            [("900123456", 10), ("800456789", 11)],
            [],  # name_to_provider
        ]
        mock_conn_obj = MagicMock()
        mock_conn_obj.cursor.return_value = mock_cur
        mock_conn.return_value = mock_conn_obj

        df = pd.DataFrame(MOCK_BROADBAND_DATA)
        result = self.pipeline.transform(df)

        year_months = result["year_month"].unique().tolist()
        assert "2024-12" in year_months  # Q4 -> month 12
        assert "2024-09" in year_months  # Q3 -> month 9

    @patch.object(MinTICBroadbandPipeline, '_get_connection')
    @patch.object(MinTICBroadbandPipeline, '_auto_create_provider')
    def test_transform_auto_creates_unknown_providers(self, mock_create, mock_conn):
        """Transform should auto-create providers for unknown NITs."""
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [("05001", 1), ("11001", 2), ("76001", 3), ("99999", 4)],
            [],  # No known providers -> all will be auto-created
            [],  # name_to_provider
        ]
        mock_conn_obj = MagicMock()
        mock_conn_obj.cursor.return_value = mock_cur
        mock_conn.return_value = mock_conn_obj
        mock_create.return_value = 99

        df = pd.DataFrame(MOCK_BROADBAND_DATA)
        result = self.pipeline.transform(df)

        # Should have called auto-create for unique NITs
        assert mock_create.call_count >= 2  # At least 900123456, 800456789
