"""A collection of common utility functions.

* save_mpl_fig (I/O) 
* split_dataframe
* split_dataframe2
* save_excelsheet (I/O)
* pandas_to_tex (I/O)
* pprint_dict
* save_json (I/O)
* save_jsongz (I/O)
* read_json (I/O)
* read_jsons (I/O)
* read_jsongz (I/O)
* read_jsongzs (I/O)
* get_datestr_list
* normalize_strc
* unix2datetime
* read_yaml (I/O)
* save_dict_to_yaml (I/O)
* save_svg_as_png (I/O)
* change_barwidth (mpl)
* text_to_list (I/O
* format_tiny_pval_expoential
"""

import json
import os
import re
from typing import Any, Iterable, List, Optional

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def extract_emails(text: Optional[str]) -> List[str]:
    """
    Extract all email addresses from a text string.

    Args:
        text: String that may contain email addresses

    Returns:
        List of extracted email addresses
    """
    if pd.isna(text):
        return []

    # Regular expression for matching email addresses
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    # Find all matches
    emails = re.findall(email_pattern, text)

    # Remove duplicates while preserving order
    seen = set()
    unique_emails = [x for x in emails if not (x in seen or seen.add(x))]

    return unique_emails


def clean_contact_column(
    df: pd.DataFrame, contact_col: str = "contact"
) -> pd.DataFrame:
    """
    Clean contact column and create long format DataFrame with one email per row.

    Args:
        df: Input DataFrame
        contact_col: Name of the column containing contact information

    Returns:
        DataFrame in long format with one email per row
    """
    # Extract emails into lists
    df["email"] = df[contact_col].apply(extract_emails)

    # Explode the emails column to create one row per email
    df_long = df.explode("email").reset_index(drop=True)

    return df_long


def save_mpl_fig(
    savepath: str, formats: Optional[Iterable[str]] = None, dpi: Optional[int] = None
) -> None:
    """Save matplotlib figures to ../output.

    Will handle saving in png and in pdf automatically using the same file stem.

    Parameters
    ----------
    savepath: str
        Name of file to save to. No extensions.
    formats: Array-like
        List containing formats to save in. (By default 'png' and 'pdf' are saved).
        Do a:
            plt.gcf().canvas.get_supported_filetypes()
        or:
            plt.gcf().canvas.get_supported_filetypes_grouped()
        To see the Matplotlib-supported file formats to save in.
        (Source: https://stackoverflow.com/a/15007393)
    dpi: int
        DPI for saving in png.

    Returns
    -------
    None
    """
    # Save pdf
    plt.savefig(f"{savepath}.pdf", dpi=None, bbox_inches="tight", pad_inches=0)

    # save png
    plt.savefig(f"{savepath}.png", dpi=dpi, bbox_inches="tight", pad_inches=0)

    # Save additional file formats, if specified
    if formats:
        for format in formats:
            plt.savefig(
                f"{savepath}.{format}",
                dpi=None,
                bbox_inches="tight",
                pad_inches=0,
            )
    return None


def pandas_to_tex(
    df: pd.DataFrame, texfile: str, index: bool = False, escape=False, **kwargs: Any
) -> None:
    """Save a Pandas dataframe to a LaTeX table fragment.

    Uses the built-in .to_latex() function. Only saves table fragments
    (equivalent to saving with "fragment" option in estout).

    Parameters
    ----------
    df: Pandas DataFrame
        Table to save to tex.
    texfile: str
        Name of .tex file to save to.
    index: bool
        Save index (Default = False).
    kwargs: any
        Additional options to pass to .to_latex().

    Returns
    -------
    None
    """
    if texfile.split(".")[-1] != "tex":
        texfile += ".tex"

    tex_table = df.to_latex(index=index, header=False, escape=escape, **kwargs)
    tex_table_fragment = "\n".join(tex_table.split("\n")[2:-3])
    # Remove the last \\ in the tex fragment to prevent the annoying
    # "Misplaced \noalign" LaTeX error when I use \bottomrule
    # tex_table_fragment = tex_table_fragment[:-2]

    with open(texfile, "w") as tf:
        tf.write(tex_table_fragment)
    return None


def process_json_files_to_matrix(json_folder):
    """
    Process JSON files and create a matrix of filenames vs names present in files.

    Args:
        json_folder (str): Path to folder containing JSON files

    Returns:
        pd.DataFrame: Matrix with filenames as rows and all unique names as columns.
                     Values are boolean indicating if name is present in file.
    """

    all_names = set()
    file_list = [f for f in os.listdir(json_folder) if f.endswith(".json")]

    for filename in file_list:
        file_path = os.path.join(json_folder, filename)
        with open(file_path, "r") as file:
            try:
                data = json.load(file)

                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    data = []

                # Extract names
                all_names.update(
                    entry["Name"]
                    for entry in data
                    if isinstance(entry, dict) and "Name" in entry
                )
            except (json.JSONDecodeError, TypeError):
                pass

    all_names = sorted(all_names)

    df = pd.DataFrame(columns=["Filename"] + all_names)

    for filename in file_list:
        file_path = os.path.join(json_folder, filename)
        with open(file_path, "r") as file:
            try:
                data = json.load(file)

                # Ensure data is a list
                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    data = []

                present_names = {
                    entry["Name"]
                    for entry in data
                    if isinstance(entry, dict) and "Name" in entry
                }
            except (json.JSONDecodeError, TypeError):
                present_names = set()

        row = {"Filename": filename.replace(".json", "")}
        row.update({name: name in present_names for name in all_names})
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    return df


def calculate_summary_statistics(
    data_df,
    groupby_column,
    value_column,
    percentiles=None,
    sort_order="count",
    custom_order=None,
    category_names=None,
):
    """
    Calculate summary statistics for a given DataFrame, including percentage of the total sample size.

    Parameters:
        data_df (DataFrame): The DataFrame containing the data.
        groupby_column (str): The column to group by.
        value_column (str): The column for which to calculate statistics.
        percentiles (list, optional): List of percentiles to calculate. Default is None.
        sort_order (str, optional): "count" to sort by count (highest first), "custom" for a user-defined order. Default is "count".
        custom_order (list, optional): Custom order of categories if sort_order is "custom". Default is None.
        category_names (dict, optional): Dictionary to map original category names to new display names. Default is None.

    Returns:
        DataFrame: A DataFrame with the summary statistics, including count and percentage of total.
    """
    if percentiles is None:
        percentiles = [25, 50, 75]

    # Calculate summary statistics
    summary_stats = data_df.groupby(groupby_column)[value_column].agg(
        count="size", mean="mean", std="std", min="min", max="max"
    )

    # Ensure count is an integer
    summary_stats["count"] = summary_stats["count"].astype(int)

    # Round mean and std to one decimal place
    summary_stats["mean"] = summary_stats["mean"].round(1)
    summary_stats["std"] = summary_stats["std"].round(1)
    summary_stats["min"] = summary_stats["min"].round(1)
    summary_stats["max"] = summary_stats["max"].round(1)

    # Calculate the percentage of the total sample size for each group
    total_count = len(data_df)
    summary_stats["percent"] = (summary_stats["count"] / total_count * 100).round(1)

    # Format the count and percentage together in the desired format
    summary_stats["count"] = summary_stats.apply(
        lambda row: f"{int(row['count'])} ({row['percent']}\%)", axis=1
    )
    summary_stats = summary_stats.drop(
        columns="percent"
    )  # Drop the intermediate percent column

    # Calculate percentile values
    percentile_values = (
        data_df.groupby(groupby_column)[value_column]
        .apply(lambda x: pd.Series(np.nanpercentile(x, percentiles), index=percentiles))
        .unstack()
        .round(1)
    )

    # Merge summary statistics and percentile values
    summary_with_percentiles = pd.merge(
        summary_stats, percentile_values, left_index=True, right_index=True
    )

    # Reorder columns
    desired_columns = ["count", "mean", "std", "min"] + percentiles + ["max"]
    summary_with_percentiles = summary_with_percentiles.reindex(
        columns=desired_columns
    ).reset_index()

    # Sort the DataFrame based on the selected sort_order
    if sort_order == "count":
        # Extract numeric part from count, convert to int, and sort by it
        summary_with_percentiles["count_value"] = summary_with_percentiles[
            "count"
        ].apply(lambda x: int(x.split()[0]))
        summary_with_percentiles = summary_with_percentiles.sort_values(
            by="count_value", ascending=False
        ).reset_index(drop=True)
        summary_with_percentiles = summary_with_percentiles.drop(
            columns="count_value"
        )  # Drop the helper column after sorting
    elif sort_order == "custom" and custom_order is not None:
        # Sort by the custom order provided by the user
        summary_with_percentiles[groupby_column] = pd.Categorical(
            summary_with_percentiles[groupby_column],
            categories=custom_order,
            ordered=True,
        )
        summary_with_percentiles = summary_with_percentiles.sort_values(
            by=groupby_column
        ).reset_index(drop=True)

    # Apply custom category names if provided
    if category_names:
        summary_with_percentiles[groupby_column] = summary_with_percentiles[
            groupby_column
        ].replace(category_names)

    return summary_with_percentiles        