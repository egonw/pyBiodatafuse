# coding: utf-8

"""Python file for queriying DisGeNet database (https://www.disgenet.org/home/)."""

import datetime
import json
import logging
import os
import time
import warnings
from string import Template
from typing import Tuple

import pandas as pd
from SPARQLWrapper import JSON, SPARQLWrapper
from SPARQLWrapper.SPARQLExceptions import SPARQLWrapperException
import requests

from pyBiodatafuse.constants import (
    DISGENET,
    DISGENET_ENDPOINT,
    DISGENET_INPUT_ID,
    DISGENET_OUTPUT_DICT,
)
from pyBiodatafuse.utils import (
    check_columns_against_constants,
    collapse_data_sources,
    get_identifier_of_interest,
)

logger = logging.getLogger("disgenet")


def check_endpoint_disgenet(api_key: str) -> bool:
    """Check the availability of the DisGeNET API.

    :returns: True if the endpoint is available, False otherwise.
    """
    #Set HTTP headers
    HTTPheadersDict = {}
    HTTPheadersDict['Authorization'] = api_key
    HTTPheadersDict['accept'] = 'application/json'
    #Set the DisGeNET API
    s = requests.Session()
    #Get version
    response = s.get("https://api.disgenet.com/api/v1/public/version", headers=HTTPheadersDict)
    # Check if API is down
    if response.json()["status"] == "OK":
        return True
    else:
        return False


def get_version_disgenet(api_key: str) -> dict:
    """Get version of DisGeNET API.

    :returns: a dictionary containing the version information
    """
    #Set HTTP headers
    HTTPheadersDict = {}
    HTTPheadersDict['Authorization'] = api_key
    HTTPheadersDict['accept'] = 'application/json'
    #Set the DisGeNET API
    s = requests.Session()
    #Get version
    version_response = s.get("https://api.disgenet.com/api/v1/public/version", headers=HTTPheadersDict)
    disgenet_version = version_response.json()["payload"]

    return disgenet_version


def get_gene_disease(api_key: str, bridgedb_df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """Query gene-disease associations from DisGeNET.

    :param api_key: DisGeNET API key (more details can be found at https://disgenet.com/plans)
    :param bridgedb_df: BridgeDb output for creating the list of gene ids to query.
    :returns: a DataFrame containing the DisGeNET output and dictionary of the DisGeNET metadata.
    """
    # Check if the DisGeNET API is available
    api_available = check_endpoint_disgenet(api_key)

    if not api_available:
        warnings.warn(
            f"{DISGENET} endpoint is not available. Unable to retrieve data.", stacklevel=2
        )
        return pd.DataFrame(), {}
    
    
    # Add the API key to the requests headers
    HTTPheadersDict = {}
    HTTPheadersDict['Authorization'] = api_key
    HTTPheadersDict['accept'] = 'application/json'
    #Set the DisGeNET API
    s = requests.Session()

    # Extract the "target" values
    data_df = get_identifier_of_interest(bridgedb_df, DISGENET_INPUT_ID)

    disgenet_output = []

    # Specify query parameters by means of a dictionary 
    params = {}
    params["format"] = "json"
    params["source"] = "CURATED"
    params["page_number"] = 0

    # Record the start time
    disgenet_version = get_version_disgenet(api_key)
    start_time = datetime.datetime.now()

    for gene in data_df["target"]:
        # Retrieve disease associated to gene with NCBI ID
        params["gene_ncbi_id"] = gene
        params["page_number"] = 0
        # Get all the diseases associated with genes for the current chunk
        gda_response = s.get(DISGENET_ENDPOINT,\
                        params=params, headers=HTTPheadersDict, verify=False)
        
        # If the status code of gda_response is 429, it means you have reached one of your query limits 
        # You can retrieve the time you need to wait until doing a new query in the response headers 
        if not gda_response.ok:
            if gda_response.status_code == 429:
                while gda_response.ok is False:
                    print("You have reached a query limit for your user. Please wait {} seconds until next query".format(\
                    gda_response.headers['x-rate-limit-retry-after-seconds']))
                    time.sleep(int(gda_response.headers['x-rate-limit-retry-after-seconds']))
                    print("Your rate limit is now restored")

                    # Repeat your query
                    gda_response = requests.get(DISGENET_ENDPOINT,\
                                            params=params, headers=HTTPheadersDict, verify=False)
                    if gda_response.ok is True:
                        break
                    else:
                        continue

        # Parse response content in JSON format since we set 'accept:application/json' as HTTP header 
        response_parsed = json.loads(gda_response.text)
        disgenet_output.extend(response_parsed["payload"])

    # Record the end time
    end_time = datetime.datetime.now()

    # Organize the annotation results as an array of dictionaries
    intermediate_df = pd.DataFrame(disgenet_output)
    if "geneNcbiID" not in intermediate_df:
        return pd.DataFrame(), {"datasource": DISGENET, "metadata": disgenet_version}

    intermediate_df.drop_duplicates(inplace=True)
    intermediate_df["target"] = intermediate_df["geneNcbiID"].apply(lambda x: x.split("/")[-1])
    intermediate_df["disease_id"] = intermediate_df["description"].apply(
        lambda x: "umls:" + x.split("umls:")[1].split("]")[0].strip()
    )
    intermediate_df["disease_name"] = intermediate_df["description"].apply(
        lambda x: x.split("[umls:")[0].strip()
    )
    intermediate_df["score"] = intermediate_df["disease_score"].astype(float)
    intermediate_df["evidence_source"] = intermediate_df["evidence_source"].apply(
        lambda x: x.split("/")[-1]
    )

    intermediate_df["target"] = intermediate_df["target"].values.astype(str)

    selected_columns = [
        "geneDSI",
        "geneDPI",
        "genepLI",
        "geneNcbiType",
        "geneProteinClassIDs",
        "geneProteinClassNames",
        "diseaseVocabularies",
        "diseaseName",
        "diseaseType",
        "diseaseUMLSCUI",
        "score",
        "ei",
        "el"
    ]

    intermediate_df = intermediate_df[
        selected_columns
    ]

    # Check if all keys in df match the keys in OUTPUT_DICT
    check_columns_against_constants(
        data_df=intermediate_df,
        output_dict=DISGENET_OUTPUT_DICT,
        check_values_in=["disease_id"],
    )

    merged_df = collapse_data_sources(
        data_df=bridgedb_df,
        source_namespace=DISGENET_INPUT_ID,
        target_df=intermediate_df,
        common_cols=["target"],
        target_specific_cols=list(DISGENET_OUTPUT_DICT.keys()),
        col_name=DISGENET,
    )

    """Metdata details"""
    # Get the current date and time
    current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Calculate the time elapsed
    time_elapsed = str(end_time - start_time)
    # Add version, datasource, query, query time, and the date to metadata
    disgenet_metadata = {
        "datasource": DISGENET,
        "metadata": disgenet_version,
        "query": {
            "size": len(data_df["target"].drop_duplicates()),
            "input_type": DISGENET_INPUT_ID,
            "time": time_elapsed,
            "date": current_date,
            "url": DISGENET_ENDPOINT,
        },
    }

    return merged_df, disgenet_metadata
