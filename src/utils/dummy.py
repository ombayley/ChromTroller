import json
import math
import pandas as pd


def main():
    path = r"C:\Users\OllyBayley\Documents\GitHub_Repositries\ChromTroller\run_logs\RunLog_2025_12_04-16_19_58.json"
    with open(path) as f:
        data: list[dict] = json.load(f)
    prod_rt = 5.0
    istd_rt = 5.9
    tol = 0.05
    raw_integrals: list[dict] = []
    for item in data:
        run_dict = {"id": item.get("run_conditions").get("run_id"), "prod": 0, "istd": 0}
        peaks = item.get("analysis").get("peak_rt")
        if peaks is not None:
            for key, value in peaks.items():
                if math.isclose(value, prod_rt, abs_tol=tol):
                    run_dict["prod"] = item.get("analysis").get("integral")[key]
                if math.isclose(value, istd_rt, abs_tol=tol):
                    run_dict["istd"] = item.get("analysis").get("integral")[key]
            raw_integrals.append(run_dict)

    integral_df = pd.DataFrame.from_dict(raw_integrals)
    integral_df.sort_values(by="id", ascending=True, inplace=True)
    integral_df.reset_index(drop=True, inplace=True)

    path = r"C:\Users\OllyBayley\Documents\GitHub_Repositries\ChromTroller\run_logs\RunLog_2025_12_04-16_19_58.csv"
    integral_df.to_csv(path)

if __name__ == "__main__":
    main()
