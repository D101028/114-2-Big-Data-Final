import json
from typing import List, Dict
import pandas as pd
import matplotlib.pyplot as plt

CITY = "Taipei City"
TIMEZONE = 8

def load_json(filenames: List[str], timezone: int) -> pd.DataFrame:
    """讀取多個 JSON 檔案，解析並合併為單一 DataFrame。"""
    all_parsed_list = []

    for filename in filenames:
        with open(filename, "r", encoding="utf-8") as fp:
            contents = json.loads(fp.read())
            for data in contents:
                all_parsed_list.append(
                    {
                        "TestTime": data["TestTime"],
                        "Speed": float(data["MeanThroughputMbps"]),
                        "City": data["Subdivision1Name"],
                        'Latency': float(data['MinRTT']),
                        'LossRate': float(data['LossRate']),
                    }
                )

    if not all_parsed_list:
        raise Exception("錯誤：未讀取到任何有效資料。")

    df = pd.DataFrame(all_parsed_list)
    df["TestTime"] = pd.to_datetime(df["TestTime"]) + pd.Timedelta(hours=timezone)

    return df

def load_csv(filenames: List[str], timezone: int) -> pd.DataFrame:
    """讀取多個 CSV 檔案，解析並合併為單一 DataFrame。"""
    dfs = []

    for filename in filenames:
        df_temp = pd.read_csv(filename)
        df_temp = df_temp[[
            "TestTime",
            "MeanThroughputMbps",
            "Subdivision1Name",
            "MinRTT",
            "LossRate",
        ]].rename(columns={
            "TestTime": "TestTime",
            "MeanThroughputMbps": "Speed",
            "Subdivision1Name": "City",
            "MinRTT": "Latency",
            "LossRate": "LossRate",
        })
        df_temp["Speed"] = df_temp["Speed"].astype(float)
        df_temp["Latency"] = df_temp["Latency"].astype(float)
        df_temp["LossRate"] = df_temp["LossRate"].astype(float)
        dfs.append(df_temp)

    if not dfs:
        raise Exception("錯誤：未讀取到任何有效資料。")

    df = pd.concat(dfs, ignore_index=True)
    df["TestTime"] = pd.to_datetime(df["TestTime"]) + pd.Timedelta(hours=timezone)

    return df

def _preprocess_df(df: pd.DataFrame, city: str) -> pd.DataFrame:
    """內部輔助函數：篩選城市並建立 3 小時時段標籤。"""
    filtered_df = df[df["City"] == city].copy()
    if filtered_df.empty:
        return pd.DataFrame()

    # bins = [0, 3, 6, 9, 12, 15, 18, 21, 24]
    # labels = ["00-03", "03-06", "06-09", "09-12", "12-15", "15-18", "18-21", "21-24"]
    
    bins = [0,1,2,3,6,9,12,15,18,21,22,23,24]
    labels = [str(b) for b in bins[:-1]]
    
    filtered_df["HourRange"] = pd.cut(
        filtered_df["TestTime"].dt.hour, bins=bins, labels=labels, right=False
    )
    return filtered_df

def plot_low_speed_ratio(
    df_dict: Dict[str, pd.DataFrame],
    city: str,
    timezone: int,
    output_path: str = "output.png",
):
    """輸入多個 df (以 dict 傳入名稱)，將各時段內所有日期的資料加總平均，並畫出對比長條圖。

    Args:
        df_dict (dict): 格式為 {"資料集名稱": DataFrame}
        city (str): 要篩選的城市名稱。
        timezone (int): 時區調整時數。
        output_path (str): 圖片儲存路徑。
    """
    all_groups = []

    for name, df in df_dict.items():
        filtered_df = _preprocess_df(df, city)
        if filtered_df.empty:
            print(f"警告：資料集 '{name}' 中找不到城市 '{city}' 的相關資料。")
            continue

        # 標記低速
        filtered_df["IsLowSpeed"] = filtered_df["Speed"] < 10

        # 直接對 HourRange 聚合（不分日期，把該時段所有日期的資料算在一起）
        grouped = (
            filtered_df.groupby("HourRange", observed=False)["IsLowSpeed"]
            .agg(["count", "sum"])
            .reset_index()
        )
        grouped["LowSpeedPercentage"] = (grouped["sum"] / grouped["count"]) * 100
        grouped["Dataset"] = name
        grouped["LabelText"] = grouped["sum"].astype(str) + "/" + grouped["count"].astype(str) # type: ignore
        all_groups.append(grouped)

    if not all_groups:
        print("錯誤：沒有任何有效的繪圖數據。")
        return

    # 合併多組資料
    combined = pd.concat(all_groups, ignore_index=True)

    # 轉置成繪圖矩陣 (Index 為時段，Columns 為不同的資料集名稱)
    pivot_df = combined.pivot(index="HourRange", columns="Dataset", values="LowSpeedPercentage").fillna(0)
    pivot_labels = combined.pivot(index="HourRange", columns="Dataset", values="LabelText").fillna("0/0")

    # 繪圖
    plt.figure(figsize=(14, 7))
    colors = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948"]
    ax = pivot_df.plot(
        kind="bar",
        figsize=(14, 7),
        width=0.8,
        color=colors[:len(pivot_df.columns)],
    )

    plt.title(f"{city}: Low Speed (<10Mbps) Ratio Comparison by 3-Hour Intervals", fontsize=14)
    plt.xlabel(f"Time Range (UTC{timezone:+d})", fontsize=12)
    plt.ylabel("Low Speed Percentage (%)", fontsize=12)
    plt.xticks(rotation=0)
    plt.ylim(0, 115)
    plt.grid(axis="y", linestyle="--", alpha=0.3)
    plt.legend(title="Dataset")

    # 標註邏輯 (改用 Dataset 對齊)
    for i, dataset_name in enumerate(pivot_df.columns):
        labels_to_show = pivot_labels[dataset_name].values
        rects = ax.containers[i]

        for j, rect in enumerate(rects):
            height = rect.get_height()
            label = labels_to_show[j]

            ax.annotate(
                label,
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"成功：低速比率對比圖已儲存至 {output_path}")

def plot_latency_loss_report(
    df_dict: Dict[str, pd.DataFrame],
    city: str,
    timezone: int,
    output_path: str = "network_report.png",
):
    """輸入多個 df (以 dict 傳入名稱)，計算各時段總體延遲與丟包率，並繪製雙子圖。"""
    all_groups = []

    for name, df in df_dict.items():
        filtered_df = _preprocess_df(df, city)
        if filtered_df.empty:
            print(f"警告：資料集 '{name}' 中找不到城市 '{city}' 的相關資料。")
            continue

        # 不分日期，直接計算該時段內所有資料的統計量與總樣本數
        grouped = (
            filtered_df.groupby("HourRange", observed=False)
            .agg(
                Latency=("Latency", lambda x: x[x >= x.quantile(0.75)].mean()),
                Loss=("LossRate", lambda x: x[x >= x.quantile(0.75)].mean()),
                Count=("Latency", "count"),
            )
            .reset_index()
        )
        grouped["Dataset"] = name
        all_groups.append(grouped)

    if not all_groups:
        print("錯誤：沒有任何有效的繪圖數據。")
        return

    combined = pd.concat(all_groups, ignore_index=True)

    # 轉置資料
    pivot_latency = combined.pivot(index="HourRange", columns="Dataset", values="Latency").fillna(0)
    pivot_loss = combined.pivot(index="HourRange", columns="Dataset", values="Loss").fillna(0)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), sharex=True)
    colors = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948"]

    # --- 圖表 1: 延遲 ---
    pivot_latency.plot(kind="bar", ax=ax1, color=colors[:len(pivot_latency.columns)], width=0.8)
    ax1.set_title(f"{city}: Latency (MinRTT) Comparison by 3-Hour Intervals", fontsize=14)
    ax1.set_ylabel("Latency (ms)", fontsize=12)
    ax1.grid(axis="y", linestyle="--", alpha=0.3)
    ax1.legend(title="Dataset")
    if not pivot_latency.empty:
        ax1.set_ylim(0, pivot_latency.max().max() * 1.15)

    # --- 圖表 2: 丟包率 ---
    pivot_loss.plot(kind="bar", ax=ax2, color=colors[:len(pivot_loss.columns)], width=0.8)
    ax2.set_title(f"{city}: Loss Rate Comparison by 3-Hour Intervals", fontsize=14)
    ax2.set_ylabel("Loss Rate (Decimal)", fontsize=12)
    ax2.set_xlabel(f"Time Range (UTC{timezone:+d})", fontsize=12)
    ax2.grid(axis="y", linestyle="--", alpha=0.3)
    ax2.legend(title="Dataset")
    ax2.set_xticklabels(pivot_loss.index, rotation=0)
    if not pivot_loss.empty:
        ax2.set_ylim(0, max(0.01, pivot_loss.max().max() * 1.15))

    # 標註邏輯
    for ax, pivot_data in zip([ax1, ax2], [pivot_latency, pivot_loss]):
        for i, dataset_name in enumerate(pivot_data.columns):
            rects = ax.containers[i]

            for j, rect in enumerate(rects):
                h = rect.get_height()
                hr = pivot_data.index[j]

                # 從 combined 中找對應 Dataset 和 HourRange 的樣本數
                match_row = combined[
                    (combined["Dataset"] == dataset_name) & (combined["HourRange"] == hr)
                ]
                n_val = match_row["Count"].values[0] if not match_row.empty else 0
                n_str = f"n={n_val}"

                ax.annotate(
                    f"{h:.2f}\n({n_str})",
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"成功：網路品質雙子圖已儲存至 {output_path}")

if __name__ == "__main__":

    for s in (2023,2024,2025):

        baseline_df = load_csv([f"in/{s}-baseline.csv", f"in/{s}-baseline-1.csv"], TIMEZONE)

        df = load_json([f"in/taipeicity-{s}1231-{s+1}0102.json"], TIMEZONE)
        # 擷取 12-31 12:00 到隔年 01-01 12:00 區間的數據
        df = df[((df["TestTime"].dt.month == 12) & (df["TestTime"].dt.day == 31) & (df["TestTime"] >= df["TestTime"].dt.normalize() + pd.Timedelta(hours=12))) | 
                ((df["TestTime"].dt.month == 1) & (df["TestTime"].dt.day == 1) & (df["TestTime"] <= df["TestTime"].dt.normalize() + pd.Timedelta(hours=12)))]
        
        plot_low_speed_ratio({
            "baseline": baseline_df, 
            f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        }, CITY, TIMEZONE, f"out/taipeicity-lsr-{s}.png")

        plot_latency_loss_report({
            "baseline": baseline_df, 
            f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        }, CITY, TIMEZONE, f"out/taipeicity-llr-{s}.png")

