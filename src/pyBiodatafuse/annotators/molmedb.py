#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Python file for queriying MolMeDB SPARQL endpoint (https://idsm.elixir-czech.cz/sparql/endpoint/molmedb."""

import datetime
import os
from string import Template

import pandas as pd
from SPARQLWrapper import JSON, SPARQLWrapper

from pyBiodatafuse.utils import collapse_data_sources, get_identifier_of_interest


def get_transporter_inhibitor(bridgedb_df: pd.DataFrame):
    """Query MolMeDB for inhibitors of transporters encoded by genes.

    :param bridgedb_df: BridgeDb output for creating the list of gene ids to query
    :returns: a DataFrame containing the MolMeDB output and dictionary of the MolMeDB metadata.
    """
    # Record the start time
    start_time = datetime.datetime.now()

    data_df = get_identifier_of_interest(bridgedb_df, "Uniprot-TrEMBL")
    molmedb_transporter_list = data_df["target"].tolist()

    molmedb_transporter_list = list(set(molmedb_transporter_list))

    query_transporter_list = []

    if len(molmedb_transporter_list) > 25:
        for i in range(0, len(molmedb_transporter_list), 25):
            tmp_list = molmedb_transporter_list[i : i + 25]
            query_transporter_list.append(" ".join(f'"{g}"' for g in tmp_list))

    else:
        query_transporter_list.append(" ".join(f'"{g}"' for g in molmedb_transporter_list))

    with open(
        os.path.dirname(__file__) + "/queries/molmedb-transporters-inhibitors.rq", "r"
    ) as fin:
        sparql_query = fin.read()

    sparql = SPARQLWrapper("https://idsm.elixir-czech.cz/sparql/endpoint/molmedb")
    sparql.setReturnFormat(JSON)
    sparql.setOnlyConneg(True)

    query_count = 0

    results_df_list = list()

    for transporter_list_str in query_transporter_list:
        query_count += 1

        sparql_query_template = Template(sparql_query)
        substit_dict = dict(transporter_list=transporter_list_str)
        sparql_query_template_sub = sparql_query_template.substitute(substit_dict)

        sparql.setQuery(sparql_query_template_sub)

        res = sparql.queryAndConvert()

        df = pd.DataFrame(res["results"]["bindings"])
        df = df.applymap(lambda x: x["value"], na_action="ignore")

        results_df_list.append(df)

    # Record the end time
    end_time = datetime.datetime.now()

    # Organize the annotation results as an array of dictionaries
    intermediate_df = pd.concat(results_df_list)

    intermediate_df.rename(columns={"transporterID": "target"}, inplace=True)
    intermediate_df["source_doi"] = intermediate_df["source_doi"].map(
        lambda x: "doi:" + x, na_action="ignore"
    )

    target_columns = list(intermediate_df.columns)
    target_columns.remove("target")

    # Merge the two DataFrames on the target column
    merged_df = collapse_data_sources(
        data_df=data_df,
        source_namespace="Uniprot-TrEMBL",
        target_df=intermediate_df,
        common_cols=["target"],
        target_specific_cols=target_columns,
        col_name="transporter_inhibitor",
    )

    # Metdata details
    # Get the current date and time
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Calculate the time elapsed
    time_elapsed = str(end_time - start_time)

    # Add the datasource, query, query time, and the date to metadata
    molmedb_metadata = {
        "datasource": "MolMeDB",
        "query": {
            "size": len(molmedb_transporter_list),
            "time": time_elapsed,
            "date": current_date,
            "url": "https://idsm.elixir-czech.cz/sparql/endpoint/molmedb",
        },
    }

    return merged_df, molmedb_metadata


def get_transporter_inhibited(bridgedb_df: pd.DataFrame):
    """Query MolMeDB for transporters inhibited by molecule.

    :param bridgedb_df: BridgeDb output for creating the list of gene ids to query
    :returns: a DataFrame containing the MolMeDB output and dictionary of the MolMeDB metadata.
    """
    # Record the start time
    start_time = datetime.datetime.now()

    data_df = get_identifier_of_interest(bridgedb_df, "InChIKey")
    inhibitor_list_str = data_df["target"].tolist()

    inhibitor_list_str = list(set(inhibitor_list_str))

    query_inhibitor_list = []

    if len(inhibitor_list_str) > 25:
        for i in range(0, len(inhibitor_list_str), 25):
            tmp_list = inhibitor_list_str[i : i + 25]
            query_inhibitor_list.append(" ".join(f'"{g}"' for g in tmp_list))

    else:
        query_inhibitor_list.append(" ".join(f'"{g}"' for g in inhibitor_list_str))

    with open(
        os.path.dirname(__file__) + "/queries/molmedb-transporters-inhibited-by-molecule.rq", "r"
    ) as fin:
        sparql_query = fin.read()

    sparql = SPARQLWrapper("https://idsm.elixir-czech.cz/sparql/endpoint/molmedb")
    sparql.setReturnFormat(JSON)
    sparql.setOnlyConneg(True)

    query_count = 0

    results_df_list = list()

    for inhibitor_list_str in query_inhibitor_list:
        query_count += 1

        sparql_query_template = Template(sparql_query)
        substit_dict = dict(inhibitor_list=inhibitor_list_str)
        sparql_query_template_sub = sparql_query_template.substitute(substit_dict)

        sparql.setQuery(sparql_query_template_sub)

        res = sparql.queryAndConvert()

        df = pd.DataFrame(res["results"]["bindings"])
        df = df.applymap(lambda x: x["value"], na_action="ignore")

        results_df_list.append(df)

    # Record the end time
    end_time = datetime.datetime.now()

    # Organize the annotation results as an array of dictionaries
    intermediate_df = pd.concat(results_df_list)

    intermediate_df.rename(columns={"inhibitorInChIKey": "target"}, inplace=True)
    intermediate_df["source_doi"] = intermediate_df["source_doi"].map(
        lambda x: "doi:" + x, na_action="ignore"
    )

    target_columns = list(intermediate_df.columns)
    target_columns.remove("target")

    # Merge the two DataFrames on the target column
    merged_df = collapse_data_sources(
        data_df=data_df,
        source_namespace="InChIKey",
        target_df=intermediate_df,
        common_cols=["target"],
        target_specific_cols=target_columns,
        col_name="transporter_inhibited",
    )

    # Metdata details
    # Get the current date and time
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Calculate the time elapsed
    time_elapsed = str(end_time - start_time)

    # Add the datasource, query, query time, and the date to metadata
    molmedb_metadata = {
        "datasource": "MolMeDB",
        "query": {
            "size": len(inhibitor_list_str),
            "time": time_elapsed,
            "date": current_date,
            "url": "https://idsm.elixir-czech.cz/sparql/endpoint/molmedb",
        },
    }

    return merged_df, molmedb_metadata
