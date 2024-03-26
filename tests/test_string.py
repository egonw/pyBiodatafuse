#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the Stringdb annotator."""

import unittest
from unittest.mock import Mock, patch

import pandas as pd

from pyBiodatafuse.annotators import stringdb
from pyBiodatafuse.annotators.stringdb import get_ppi, get_version_stringdb
from pyBiodatafuse.constants import STRING


class TestString(unittest.TestCase):
    """Test the String class."""

    @patch("pyBiodatafuse.annotators.stringdb.requests.get")
    def test_get_version_stringdb(self, mock_requests_get):
        """Test the get_version_stringdb."""
        mock_requests_get.return_value.json.return_value = [
            {"string_version": "12.0", "stable_address": "https://version-12-0.string-db.org"}
        ]

        obtained_version = get_version_stringdb()

        expected_version = {"source_version": "12.0"}

        assert obtained_version == expected_version

    def test_get_ppi(self):
        """Test the get_ppi function."""
        stringdb.check_endpoint_stringdb = Mock(return_value=True)
        stringdb.get_version_stringdb = Mock(return_value={"source_version": "12.0"})
        stringdb.get_string_ids = Mock(
            return_value=[
                {
                    "queryIndex": 0,
                    "queryItem": "ENSG00000119523",
                    "stringId": "9606.ENSP00000417764",
                    "ncbiTaxonId": 9606,
                    "taxonName": "Homo sapiens",
                    "preferredName": "ALG2",
                    "annotation": "Alpha-1,3/1,6-mannosyltransferase ALG2; Mannosylates Man(2)GlcNAc(2)-dolichol diphosphate and Man(1)GlcNAc(2)-dolichol diphosphate to form Man(3)GlcNAc(2)-dolichol diphosphate; Belongs to the glycosyltransferase group 1 family. Glycosyltransferase 4 subfamily.",
                },
                {
                    "queryIndex": 1,
                    "queryItem": "ENSG00000138435",
                    "stringId": "9606.ENSP00000261007",
                    "ncbiTaxonId": 9606,
                    "taxonName": "Homo sapiens",
                    "preferredName": "CHRNA1",
                    "annotation": "Acetylcholine receptor subunit alpha; After binding acetylcholine, the AChR responds by an extensive change in conformation that affects all subunits and leads to opening of an ion-conducting channel across the plasma membrane.",
                },
                {
                    "queryIndex": 2,
                    "queryItem": "ENSG00000172339",
                    "stringId": "9606.ENSP00000359224",
                    "ncbiTaxonId": 9606,
                    "taxonName": "Homo sapiens",
                    "preferredName": "ALG14",
                    "annotation": "UDP-N-acetylglucosamine transferase subunit ALG14 homolog; May be involved in protein N-glycosylation. May play a role in the second step of the dolichol-linked oligosaccharide pathway. May anchor the catalytic subunit ALG13 to the ER. Belongs to the ALG14 family.",
                },
            ]
        )

        stringdb._get_ppi_data = Mock(
            return_value=[
                {
                    "stringId_A": "9606.ENSP00000261007",
                    "stringId_B": "9606.ENSP00000359224",
                    "preferredName_A": "CHRNA1",
                    "preferredName_B": "ALG14",
                    "ncbiTaxonId": "9606",
                    "score": 0.543,
                    "nscore": 0,
                    "fscore": 0,
                    "pscore": 0,
                    "ascore": 0,
                    "escore": 0,
                    "dscore": 0,
                    "tscore": 0.543,
                },
                {
                    "stringId_A": "9606.ENSP00000359224",
                    "stringId_B": "9606.ENSP00000417764",
                    "preferredName_A": "ALG14",
                    "preferredName_B": "ALG2",
                    "ncbiTaxonId": "9606",
                    "score": 0.633,
                    "nscore": 0,
                    "fscore": 0,
                    "pscore": 0,
                    "ascore": 0.067,
                    "escore": 0,
                    "dscore": 0.119,
                    "tscore": 0.589,
                },
            ]
        )

        bridgedb_dataframe = pd.DataFrame(
            {
                "identifier": ["ALG14", "ALG2", "CHRNA1"],
                "identifier.source": ["HGNC", "HGNC", "HGNC"],
                "target": ["ENSG00000172339", "ENSG00000119523", "ENSG00000138435"],
                "target.source": ["Ensembl", "Ensembl", "Ensembl"],
            }
        )

        obtained_data, metadata = get_ppi(bridgedb_dataframe)

        expected_data = pd.Series(
            [
                [
                    {"stringdb_link_to": "CHRNA1", "Ensembl": "ENSP00000261007", "score": 0.543},
                    {"stringdb_link_to": "ALG2", "Ensembl": "ENSP00000417764", "score": 0.633},
                ],
                [{"stringdb_link_to": "ALG14", "Ensembl": "ENSP00000359224", "score": 0.633}],
                [{"stringdb_link_to": "ALG14", "Ensembl": "ENSP00000359224", "score": 0.543}],
            ]
        )
        expected_data.name = STRING

        pd.testing.assert_series_equal(obtained_data[STRING], expected_data)
        self.assertIsInstance(metadata, dict)
