#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python file for queriying PubChem (https://pubchem.ncbi.nlm.nih.gov/)."""

import datetime
import os
import warnings
from string import Template
from typing import Tuple

import numpy as np
import pandas as pd
from SPARQLWrapper import JSON, SPARQLWrapper

from pyBiodatafuse.constants import PUBCHEM, PUBCHEM_ENDPOINT, PUBCHEM_INPUT_ID, PUBCHEM_OUTPUT_DICT
from pyBiodatafuse.utils import (
    check_columns_against_constants,
    collapse_data_sources,
    get_identifier_of_interest,
)


def check_endpoint_pubchem() -> bool:
    """Check the availability of the IDSM endpoint.

    :returns: True if the endpoint is available, False otherwise.
    """
    query_string = """SELECT * WHERE {
        <http://rdf.ncbi.nlm.nih.gov/pubchem/taxonomy> ?p ?o
        }
        LIMIT 1
        """
    sparql = SPARQLWrapper(PUBCHEM_ENDPOINT)
    sparql.setOnlyConneg(True)
    sparql.setQuery(query_string)
    try:
        sparql.query()
        return True
    except BaseException:
        return False


# TODO - Add metadata function. Currently, no metadata is returned from IDSM servers


def get_protein_molecule_screened(bridgedb_df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Query PubChem for molecules screened on proteins as targets.

    :param bridgedb_df: BridgeDb output for creating the list of gene ids to query.
    :returns: a DataFrame containing the PubChem output and dictionary of the PubChem metadata.
    """
    # Check if the IDSM endpoint is available
    api_available = check_endpoint_pubchem()
    if not api_available:
        warnings.warn(
            f"{PUBCHEM} endpoint is not available. Unable to retrieve data.", stacklevel=2
        )
        return pd.DataFrame(), {}

    # Record the start time
    start_time = datetime.datetime.now()

    data_df = get_identifier_of_interest(bridgedb_df, PUBCHEM_INPUT_ID)
    protein_list_str = data_df["target"].tolist()
    for i in range(len(protein_list_str)):
        protein_list_str[i] = "<http://purl.uniprot.org/uniprot/" + protein_list_str[i] + ">"

    protein_list_str = list(set(protein_list_str))

    query_protein_list = []

    if len(protein_list_str) > 25:
        for i in range(0, len(protein_list_str), 25):
            tmp_list = protein_list_str[i : i + 25]
            query_protein_list.append(" ".join(f"{g}" for g in tmp_list))

    else:
        query_protein_list.append(" ".join(f"{g}" for g in protein_list_str))

    with open(
        os.path.dirname(__file__) + "/queries/pubchem-proteins-screend-molecule.rq", "r"
    ) as fin:
        sparql_query = fin.read()

    sparql = SPARQLWrapper(PUBCHEM_ENDPOINT)
    sparql.setReturnFormat(JSON)
    sparql.setOnlyConneg(True)

    query_count = 0

    intermediate_df = pd.DataFrame()

    for protein_list_str in query_protein_list:
        query_count += 1

        sparql_query_template = Template(sparql_query)
        substit_dict = dict(protein_list=protein_list_str)
        sparql_query_template_sub = sparql_query_template.substitute(substit_dict)

        sparql.setQuery(sparql_query_template_sub)
        res = sparql.queryAndConvert()

        df = pd.DataFrame(res["results"]["bindings"])
        df = df.applymap(lambda x: x["value"], na_action="ignore")

        intermediate_df = pd.concat([intermediate_df, df], ignore_index=True)

    # Record the end time
    end_time = datetime.datetime.now()

    # Organize the annotation results as an array of dictionaries
    assay_endpoint_types = {
        "http://www.bioassayontology.org/bao#BAO_0000034": "Kd",
        "http://www.bioassayontology.org/bao#BAO_0000186": "AC50",
        "http://www.bioassayontology.org/bao#BAO_0000187": "CC50",
        "http://www.bioassayontology.org/bao#BAO_0000188": "EC50",
        "http://www.bioassayontology.org/bao#BAO_0000190": "IC50",
        "http://www.bioassayontology.org/bao#BAO_0000192": "Ki",
        "http://www.bioassayontology.org/bao#BAO_0002146": "MIC",
    }

    if intermediate_df.empty:
        return pd.DataFrame(), {"datasource": PUBCHEM}

    # drop multitarget assays
    intermediate_df.rename(
        columns={
            "upProt": "target",
            "assay": "pubchem_assay_id",
        },
        inplace=True,
    )

    # Want to keep compounds tested across multiple targets
    intermediate_df["target_count"] = intermediate_df["target_count"].astype(int)
    mask = intermediate_df["target_count"] > 1
    intermediate_df = intermediate_df[mask]

    intermediate_df.drop(columns=["target_count"], inplace=True)

    # Get identifiers from the URL
    intermediate_df["target"] = intermediate_df["target"].map(
        lambda x: x.split("http://purl.uniprot.org/uniprot/")[-1]
    )
    intermediate_df["pubchem_assay_id"] = intermediate_df["pubchem_assay_id"].map(
        lambda x: x.split("http://rdf.ncbi.nlm.nih.gov/pubchem/bioassay/")[-1]
    )

    intermediate_df["outcome"] = intermediate_df["outcome"].map(
        lambda x: x.split("http://rdf.ncbi.nlm.nih.gov/pubchem/vocabulary#")[1]
    )
    intermediate_df["compound_cid"] = intermediate_df["compound_cid"].map(
        lambda x: x.split("http://rdf.ncbi.nlm.nih.gov/pubchem/compound/")[-1]
    )
    intermediate_df["assay_type"] = intermediate_df["assay_type"].map(assay_endpoint_types)

    # Check if all keys in df match the keys in OUTPUT_DICT
    check_columns_against_constants(
        data_df=intermediate_df,
        output_dict=PUBCHEM_OUTPUT_DICT,
        check_values_in=["outcome", "InChI"],
    )

    # Merge the two DataFrames on the target column
    merged_df = collapse_data_sources(
        data_df=data_df,
        source_namespace=PUBCHEM_INPUT_ID,
        target_df=intermediate_df,
        common_cols=["target"],
        target_specific_cols=list(PUBCHEM_OUTPUT_DICT.keys()),
        col_name=f"{PUBCHEM}_Assays",
    )

    print(merged_df)

    merged_df.drop_duplicates(subset=["identifier", "{PUBCHEM}_Assays"], inplace=True)

    # elif not merged_df.empty:
    #     res_keys = merged_df[f"{PUBCHEM}_Assays"][0][0].keys()
    #     # remove duplicate identifier and response row
    #     merged_df[f"{PUBCHEM}_Assays"] = merged_df[f"{PUBCHEM}_Assays"].map(
    #         lambda x: tuple(frozenset(d.items()) for d in x), na_action="ignore"
    #     )
    #     merged_df.drop_duplicates(subset=["identifier", f"{PUBCHEM}_Assays"], inplace=True)
    #     merged_df[f"{PUBCHEM}_Assays"] = merged_df[f"{PUBCHEM}_Assays"].map(
    #         lambda res_tup: list(dict((x, y) for x, y in res) for res in res_tup),
    #         na_action="ignore",
    #     )

    #     # drop rows with duplicate identifiers with empty response
    #     identifiers = merged_df["identifier"].unique()
    #     for identifier in identifiers:
    #         if merged_df.loc[merged_df["identifier"] == identifier].shape[0] > 1:
    #             mask = merged_df[f"{PUBCHEM}_Assays"].apply(
    #                 lambda lst: all(
    #                     [
    #                         all([isinstance(val, float) and np.isnan(val) for val in dct.values()])
    #                         for dct in lst
    #                     ]
    #                 )
    #             )
    #             mask2 = merged_df["identifier"].apply(lambda x, id=identifier: x == id)
    #             merged_df.drop(merged_df[mask & mask2].index, inplace=True)

    #     # set default order to response dictionaries to keep output consistency
    #     merged_df[f"{PUBCHEM}_Assays"] = merged_df[f"{PUBCHEM}_Assays"].apply(
    #         lambda res: list(dict((k, r[k]) for k in res_keys) for r in res)
    #     )
    #     # set numerical identifiers to int to kepp output consistency
    #     merged_df[f"{PUBCHEM}_Assays"] = merged_df[f"{PUBCHEM}_Assays"].apply(
    #         lambda res: int_response_value_types(res, ["compound_cid", "pubchem_assay_id"])
    #     )

    print("Changed")
    print(merged_df)
    merged_df.reset_index(drop=True, inplace=True)

    """Metdata details"""
    # Get the current date and time
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Calculate the time elapsed
    time_elapsed = str(end_time - start_time)

    # Add the datasource, query, query time, and the date to metadata
    molmedb_metadata = {
        "datasource": PUBCHEM,
        "query": {
            "size": len(protein_list_str),
            "time": time_elapsed,
            "date": current_date,
            "url": PUBCHEM_ENDPOINT,
        },
    }

    return merged_df, molmedb_metadata


def int_response_value_types(resp_list: list, key_list: list):
    """Change values in response dictionaries to int to stay consistent with other Annotators.

    :param: resp_list: list of response dictionaries.
    :param: key_list: list of keys to change to int.
    :returns: resp_list with int values in response dictionaries on keys in key_list.
    """
    for r in resp_list:
        for k in key_list:
            try:
                r[k] = int(r[k])
            except ValueError:
                continue
    return resp_list
