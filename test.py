import pandas as pd
from main import load_csv, load_json, plot_network_performance_report_2

CITY = "New York"
TIMEZONE = -5

if __name__ == "__main__":

    for s in (2025, ):

        baseline_df = load_csv([f"test-in/{s}-baseline.csv", f"test-in/{s}-baseline-1.csv"], TIMEZONE)

        df = load_json([f"test-in/newyork-{s}1231-{s+1}0102.json"], TIMEZONE)
        # 擷取 12-31 12:00 到隔年 01-01 12:00 區間的數據
        df = df[((df["TestTime"].dt.month == 12) & (df["TestTime"].dt.day == 31) & (df["TestTime"] >= df["TestTime"].dt.normalize() + pd.Timedelta(hours=12))) | 
                ((df["TestTime"].dt.month == 1) & (df["TestTime"].dt.day == 1) & (df["TestTime"] <= df["TestTime"].dt.normalize() + pd.Timedelta(hours=12)))]
        
        plot_network_performance_report_2({
            "baseline": baseline_df, 
            f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        }, CITY, TIMEZONE, f"out/newyork-ratio-{s}.png")
