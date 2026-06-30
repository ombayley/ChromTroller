#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: **Add Desc**.
"""
import pandas as pd
from pathlib import Path

def assign_name(peaks_df: pd.DataFrame) -> None:
    prod_rt = 5.0
    istd_rt = 5.9
    tol = 0.2

    # default
    peaks_df["name"] = "unknown"

    # ensure numeric
    peaks_df["peak_rt"] = pd.to_numeric(peaks_df["peak_rt"])

    # choose closest peak per id for product & istd
    for _, group in peaks_df.groupby("id"):
        # --- product ---
        prod_idx = (group["peak_rt"] - prod_rt).abs().idxmin()
        prod_dist = abs(peaks_df.loc[prod_idx, "peak_rt"] - prod_rt)
        if prod_dist <= tol:
            peaks_df.loc[prod_idx, "name"] = "product"

        # --- istd ---
        # optional: avoid reusing the same peak for both
        istd_group = group.drop(index=prod_idx)

        if not istd_group.empty:
            istd_idx = (istd_group["peak_rt"] - istd_rt).abs().idxmin()
            istd_dist = abs(peaks_df.loc[istd_idx, "peak_rt"] - istd_rt)
            if istd_dist <= tol:
                peaks_df.loc[istd_idx, "name"] = "istd"

def assign_conditions(df):
    df["id"] = df["id"].astype(int)

    reps_per_cond = 3
    n_conds = 5
    block_size = reps_per_cond * n_conds  # 15 samples per full loop

    # condition: 1..5 repeating every 3 ids
    df["condition"] = ((df["id"] - 1) // reps_per_cond) % n_conds + 1

    # cycle (time block): 1..5, each is 15 samples
    df["cycle"] = ((df["id"] - 1) // block_size) + 1



def calculate_metrics(df):
    df_peaks = df[df["name"].isin(["product", "istd"])]

    samples = (
        df_peaks
        .pivot_table(
            index=["id", "file", "condition", "cycle"],
            columns="name",
            values="integral",
            aggfunc="first",
        )
        .reset_index()
    )

    samples["ratio"] = samples["product"] / samples["istd"]

    summary = (
        samples
        .groupby(["condition", "cycle"])[["product", "istd", "ratio"]]
        .agg(["mean", "var"])
        .reset_index()
    )

    summary.columns = [
        "condition", "cycle",
        "product_mean", "product_var",
        "istd_mean", "istd_var",
        "ratio_mean", "ratio_var",
    ]

    return samples, summary



def main():
    dirpath: Path = Path(r"Z:\personal_file_transfer\olly_file_transfer\RbC_eChem\oxidative_extracted")
    csv_path = dirpath / "peaks.csv"
    peaks_df = pd.read_csv(csv_path)
    assign_name(peaks_df)
    assign_conditions(peaks_df)
    samples, summary = calculate_metrics(peaks_df)


    peaks_df.to_csv(csv_path, index=False)
    samples.to_csv(dirpath / "samples.csv", index=False)
    summary.to_csv(dirpath / "summary.csv", index=False)


if __name__ == "__main__":
    main()
