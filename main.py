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

def plot_network_performance_report(
    df_dict: Dict[str, pd.DataFrame],
    city: str,
    timezone: int,
    output_path: str = "network_performance_report.png",
):
    """輸入多個 df (以 dict 傳入名稱)，將各時段內所有日期的資料加總平均，

    並繪製三聯子圖（Speed, Latency, Packet Loss），X 軸採自訂時段順序。
    
    - 子圖 1 (Speed): <10Mbps 的資料佔比
    - 子圖 2 (Latency): 高於 85% 門檻的資料佔比
    - 子圖 3 (Loss): 高於 85% 門檻的資料佔比
    """
    all_groups = []

    for name, df in df_dict.items():
        filtered_df = _preprocess_df(df, city)
        if filtered_df.empty:
            print(f"警告：資料集 '{name}' 中找不到城市 '{city}' 的相關資料。")
            continue

        # 標記低速
        filtered_df["IsLowSpeed"] = filtered_df["Speed"] < 10

        # 一次性聚合所有需要的統計量
        grouped = (
            filtered_df.groupby("HourRange", observed=False)
            .agg(
                Speed_Count=("IsLowSpeed", "count"),
                Speed_Sum=("IsLowSpeed", "sum"),
                Latency=("Latency", lambda x: x[x >= x.quantile(0.85)].mean() if not x.empty else 0),
                Loss=("LossRate", lambda x: x[x >= x.quantile(0.85)].mean() if not x.empty else 0),
                Network_Count=("Latency", "count"),
            )
            .reset_index()
        )
        
        # 計算低速比例與標籤文字
        grouped["LowSpeedPercentage"] = (grouped["Speed_Sum"] / grouped["Speed_Count"]) * 100
        grouped["SpeedLabelText"] = grouped["Speed_Sum"].astype(str) + "/" + grouped["Speed_Count"].astype(str) # type: ignore
        grouped["Dataset"] = name
        
        all_groups.append(grouped)

    if not all_groups:
        print("錯誤：沒有任何有效的繪圖數據。")
        return

    # 合併多組資料
    combined = pd.concat(all_groups, ignore_index=True)

    # =========================================================================
    # ✨ 核心修改：定義自訂的 X 軸時段順序
    # =========================================================================
    # 請確保這裡的字串與你資料中 'HourRange' 的實際字串格式完全一致（例如 "12" 或 "12:00" 等）
    custom_order = ["12", "15", "18", "21", "22", "23", "0", "1", "2", "3", "6", "9"]
    
    # 將 HourRange 轉為帶有指定順序的 Categorical 型態
    combined["HourRange"] = pd.Categorical(
        combined["HourRange"], 
        categories=custom_order, 
        ordered=True
    )
    
    # 根據剛剛設定的自訂順序進行排序，確保 pivot 出來的欄位順序正確
    combined = combined.sort_values("HourRange")
    # =========================================================================

    # 轉置各指標資料成繪圖矩陣 (此時 Index 會自動依照 custom_order 排列)
    pivot_speed = combined.pivot(index="HourRange", columns="Dataset", values="LowSpeedPercentage").fillna(0)
    pivot_speed_labels = combined.pivot(index="HourRange", columns="Dataset", values="SpeedLabelText").fillna("0/0")
    
    pivot_latency = combined.pivot(index="HourRange", columns="Dataset", values="Latency").fillna(0)
    pivot_loss = combined.pivot(index="HourRange", columns="Dataset", values="Loss").fillna(0)

    # 建立 3x1 的畫布，並共用 X 軸
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 18), sharex=True)
    colors = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948"]
    color_slice = colors[:len(pivot_speed.columns)]

    # --- 子圖 1: 低速比率 (Speed) ---
    pivot_speed.plot(kind="bar", ax=ax1, color=color_slice, width=0.8)
    ax1.set_title(f"{city}: Low Speed (<10Mbps) Ratio Comparison by Intervals", fontsize=14)
    ax1.set_ylabel("Low Speed Percentage (%)", fontsize=12)
    ax1.set_ylim(0, 115)
    ax1.grid(axis="y", linestyle="--", alpha=0.3)
    ax1.legend(title="Dataset")

    # 子圖 1 標註
    for i, dataset_name in enumerate(pivot_speed.columns):
        labels_to_show = pivot_speed_labels[dataset_name].values
        rects = ax1.containers[i]
        for j, rect in enumerate(rects):
            h = rect.get_height()
            label = labels_to_show[j]
            ax1.annotate(
                label,
                xy=(rect.get_x() + rect.get_width() / 2, h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
            )

    # --- 子圖 2: 延遲 (Latency) ---
    pivot_latency.plot(kind="bar", ax=ax2, color=color_slice, width=0.8)
    ax2.set_title(f"{city}: Average of the top 15% Highest Latency (MinRTT) Comparison by Intervals", fontsize=14)
    ax2.set_ylabel("Latency (ms)", fontsize=12)
    ax2.grid(axis="y", linestyle="--", alpha=0.3)
    ax2.legend(title="Dataset")
    if not pivot_latency.empty:
        ax2.set_ylim(0, pivot_latency.max().max() * 1.15)

    # --- 子圖 3: 丟包率 (Packet Loss) ---
    pivot_loss.plot(kind="bar", ax=ax3, color=color_slice, width=0.8)
    ax3.set_title(f"{city}: Average of the top 15% Highest Loss Rate Comparison by Intervals", fontsize=14)
    ax3.set_ylabel("Loss Rate (Decimal)", fontsize=12)
    ax3.set_xlabel(f"Time Range (UTC{timezone:+d})", fontsize=12)
    ax3.grid(axis="y", linestyle="--", alpha=0.3)
    ax3.legend(title="Dataset")
    ax3.set_xticklabels(pivot_loss.index, rotation=0) # X 軸會完美呈現自訂順序
    if not pivot_loss.empty:
        ax3.set_ylim(0, max(0.01, pivot_loss.max().max() * 1.15))

    # 子圖 2 & 子圖 3 的資料點標註邏輯 (帶有 n 樣本數)
    for ax, pivot_data in zip([ax2, ax3], [pivot_latency, pivot_loss]):
        for i, dataset_name in enumerate(pivot_data.columns):
            rects = ax.containers[i]
            for j, rect in enumerate(rects):
                h = rect.get_height()
                hr = pivot_data.index[j]

                match_row = combined[
                    (combined["Dataset"] == dataset_name) & (combined["HourRange"] == hr)
                ]
                n_val = match_row["Network_Count"].values[0] if not match_row.empty else 0
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
    print(f"成功：網路效能三聯綜合圖已排序並儲存至 {output_path}")

def plot_network_performance_report_2(
    df_dict: Dict[str, pd.DataFrame],
    city: str,
    timezone: int,
    output_path: str = "network_performance_report.png",
):
    """輸入多個 df (以 dict 傳入名稱)，將各時段內所有日期的資料加總平均，
    並繪製三聯子圖。
    
    指標調整：
    - 子圖 1 (Speed): 低於 15% 門檻的資料佔比
    - 子圖 2 (Latency): 高於 85% 門檻的資料佔比
    - 子圖 3 (Loss): 高於 85% 門檻的資料佔比
    """
    
    # -------------------------------------------------------------------------
    # ✨ 核心修改 1：全域門檻計算
    # 為了讓「高於 85% 占比」有比較意義，我們需要先算出全體（或某一基準）的 85 百分位數作為固定門檻
    # -------------------------------------------------------------------------
    all_processed_dfs = []
    for name, df in df_dict.items():
        filtered_df = _preprocess_df(df, city).copy()
        if not filtered_df.empty:
            filtered_df["Dataset"] = name
            all_processed_dfs.append(filtered_df)
            
    if not all_processed_dfs:
        print("錯誤：沒有任何有效的繪圖數據。")
        return

    # 合併所有未聚合的原始資料，用來計算全局的第 85 百分位數門檻
    # (你也可以手動指定固定數值，例如 latency_threshold = 100)
    global_df = pd.concat(all_processed_dfs, ignore_index=True)
    speed_threshold = global_df["Latency"].quantile(0.15)
    latency_threshold = global_df["Latency"].quantile(0.85)
    loss_threshold = global_df["LossRate"].quantile(0.85)

    print(f"依據全體數據計算之 85% 門檻 -> 延遲: {latency_threshold:.2f} ms, 丟包率: {loss_threshold:.4f}")

    all_groups = []
    for filtered_df in all_processed_dfs:
        name = filtered_df["Dataset"].iloc[0]

        # 標記是否超過門檻
        filtered_df["IsLowSpeed"] = filtered_df["Speed"] < speed_threshold
        filtered_df["IsHighLatency"] = filtered_df["Latency"] > latency_threshold
        filtered_df["IsHighLoss"] = filtered_df["LossRate"] > loss_threshold

        # 一次性聚合所有需要的統計量（數量與分子）
        grouped = (
            filtered_df.groupby("HourRange", observed=False)
            .agg(
                Speed_Count=("IsLowSpeed", "count"),
                Speed_Sum=("IsLowSpeed", "sum"),
                
                Latency_Count=("IsHighLatency", "count"),
                Latency_Sum=("IsHighLatency", "sum"),
                
                Loss_Count=("IsHighLoss", "count"),
                Loss_Sum=("IsHighLoss", "sum"),
            )
            .reset_index()
        )
        
        # 計算各指標的「超標百分比」與「標籤文字 (分子/分母)」
        grouped["LowSpeedPercentage"] = (grouped["Speed_Sum"] / grouped["Speed_Count"]) * 100
        grouped["SpeedLabelText"] = grouped["Speed_Sum"].astype(str) + "/" + grouped["Speed_Count"].astype(str)
        
        grouped["HighLatencyPercentage"] = (grouped["Latency_Sum"] / grouped["Latency_Count"]) * 100
        grouped["LatencyLabelText"] = grouped["Latency_Sum"].astype(str) + "/" + grouped["Latency_Count"].astype(str)
        
        grouped["HighLossPercentage"] = (grouped["Loss_Sum"] / grouped["Loss_Count"]) * 100
        grouped["LossLabelText"] = grouped["Loss_Sum"].astype(str) + "/" + grouped["Loss_Count"].astype(str)
        
        grouped["Dataset"] = name
        all_groups.append(grouped)

    # 合併多組資料
    combined = pd.concat(all_groups, ignore_index=True)

    # 定義自訂的 X 軸時段順序
    custom_order = ["12", "15", "18", "21", "22", "23", "0", "1", "2", "3", "6", "9"]
    combined["HourRange"] = pd.Categorical(combined["HourRange"], categories=custom_order, ordered=True)
    combined = combined.sort_values("HourRange")

    # 轉置各指標資料成繪圖矩陣
    pivot_speed = combined.pivot(index="HourRange", columns="Dataset", values="LowSpeedPercentage").fillna(0)
    pivot_speed_labels = combined.pivot(index="HourRange", columns="Dataset", values="SpeedLabelText").fillna("0/0")
    
    pivot_latency = combined.pivot(index="HourRange", columns="Dataset", values="HighLatencyPercentage").fillna(0)
    pivot_latency_labels = combined.pivot(index="HourRange", columns="Dataset", values="LatencyLabelText").fillna("0/0")
    
    pivot_loss = combined.pivot(index="HourRange", columns="Dataset", values="HighLossPercentage").fillna(0)
    pivot_loss_labels = combined.pivot(index="HourRange", columns="Dataset", values="LossLabelText").fillna("0/0")

    # 建立 3x1 的畫布
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 18), sharex=True)
    colors = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948"]
    color_slice = colors[:len(pivot_speed.columns)]

    # --- 子圖 1: 低速比率 (Speed) - 保持不變 ---
    pivot_speed.plot(kind="bar", ax=ax1, color=color_slice, width=0.8)
    ax1.set_title(f"{city}: Low Speed (<{speed_threshold:.1f}Mbps) Ratio Comparison by Intervals", fontsize=14)
    ax1.set_ylabel("Low Speed Percentage (%)", fontsize=12)
    ax1.set_ylim(0, 115)
    ax1.grid(axis="y", linestyle="--", alpha=0.3)
    ax1.legend(title="Dataset")

    # --- ✨ 核心修改 2：子圖 2 延遲與子圖 3 丟包率的繪圖與標註更新 ---
    # 子圖 2: 高延遲比率 (Latency)
    pivot_latency.plot(kind="bar", ax=ax2, color=color_slice, width=0.8)
    ax2.set_title(f"{city}: High Latency (>{latency_threshold:.1f}ms) Ratio Comparison by Intervals", fontsize=14)
    ax2.set_ylabel("High Latency Percentage (%)", fontsize=12)
    ax2.set_ylim(0, 115)
    ax2.grid(axis="y", linestyle="--", alpha=0.3)
    ax2.legend(title="Dataset")

    # 子圖 3: 高丟包比率 (Packet Loss)
    pivot_loss.plot(kind="bar", ax=ax3, color=color_slice, width=0.8)
    ax3.set_title(f"{city}: High Loss Rate (>{loss_threshold:.4f}) Ratio Comparison by Intervals", fontsize=14)
    ax3.set_ylabel("High Loss Percentage (%)", fontsize=12)
    ax3.set_xlabel(f"Time Range (UTC{timezone:+d})", fontsize=12)
    ax3.set_ylim(0, 115)
    ax3.grid(axis="y", linestyle="--", alpha=0.3)
    ax3.legend(title="Dataset")
    ax3.set_xticklabels(pivot_loss.index, rotation=0)

    # 統一三個子圖的文字標註邏輯 (因為現在全部都是百分比與「分子/分母」格式)
    axes_and_labels = [
        (ax1, pivot_speed, pivot_speed_labels),
        (ax2, pivot_latency, pivot_latency_labels),
        (ax3, pivot_loss, pivot_loss_labels)
    ]

    for ax, pivot_data, pivot_lbls in axes_and_labels:
        for i, dataset_name in enumerate(pivot_data.columns):
            labels_to_show = pivot_lbls[dataset_name].values
            rects = ax.containers[i]
            for j, rect in enumerate(rects):
                h = rect.get_height()
                label_text = labels_to_show[j]
                
                # 同時顯示百分比數值與樣本數狀況 (例如: "15.3%\n(45/294)")
                display_str = f"{h:.1f}%\n({label_text})" if h > 0 else f"0%\n({label_text})"
                
                ax.annotate(
                    display_str,
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold" if h > 0 else "normal",
                )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"成功：網路效能三聯綜合圖已排序並儲存至 {output_path}")

def plot_ny_network_report(
    df_dict: Dict[str, pd.DataFrame],
    city: str,
    timezone: int,
    output_path: str = "ny_network_report.png",
    baseline_name: str = "baseline",
):
    """根據 df_dict 的鍵值（name）指定基線，計算其他資料集相較於基線的網路惡化指標（X1, X2, X3）。

    Args:
        df_dict (dict): 格式為 {"資料集名稱": DataFrame}，例如 {"Baseline": df1, "NYE_2026": df2}
        baseline_name (str): 作為基準線的鍵值名稱，例如 "Baseline"
        city (str): 要篩選的城市名稱。
        timezone (int): 時區調整時數。
        output_path (str): 圖片儲存路徑。
    """
    # 檢查防錯：確保指定的基線名稱確實存在
    if baseline_name not in df_dict:
        print(f"錯誤：在傳入的 dict 中找不到指定的基線名稱 '{baseline_name}'。")
        return

    # 1. 優先處理並計算基線（Baseline）在各時段（HourRange）的百分位數門檻
    base_df = _preprocess_df(df_dict[baseline_name], city)
    if base_df.empty:
        print(f"錯誤：基線資料集 '{baseline_name}' 中找不到城市 '{city}' 的相關資料，無法建立基準。")
        return

    baseline_thresholds = (
        base_df.groupby("HourRange", observed=False)
        .agg(
            speed_p15=("Speed", lambda x: x.quantile(0.15)),
            latency_p85=("Latency", lambda x: x.quantile(0.85))
        )
        .reset_index()
    )

    # 2. 開始巡覽所有資料集，與基線進行比對（跳過基線自己）
    all_groups = []

    for name, df in df_dict.items():
        if name == baseline_name:
            continue  # 基準線不需要自己算崩潰率，直接跳過

        filtered_df = _preprocess_df(df, city)
        if filtered_df.empty:
            print(f"警告：資料集 '{name}' 中找不到城市 '{city}' 的相關資料。")
            continue

        # 將基線門檻 merge 進當前的觀測資料集
        merged = filtered_df.merge(baseline_thresholds, on="HourRange", how="left")

        # 根據定義標記是否觸發異常（$X_1, X_2, X_3$）
        merged["Is_X1"] = merged["Speed"] < merged["speed_p15"]
        merged["Is_X2"] = merged["Latency"] > merged["latency_p85"]
        merged["Is_X3"] = merged["LossRate"] > 0.01

        # 聚合各時段的觸發比例
        grouped = (
            merged.groupby("HourRange", observed=False)
            .agg(
                X1_sum=("Is_X1", "sum"),
                X1_count=("Is_X1", "count"),
                X2_sum=("Is_X2", "sum"),
                X2_count=("Is_X2", "count"),
                X3_sum=("Is_X3", "sum"),
                X3_count=("Is_X3", "count"),
            )
            .reset_index()
        )
        
        # 計算比例 (%) 與標註文字
        grouped["X1_Rate"] = (grouped["X1_sum"] / grouped["X1_count"]) * 100
        grouped["X2_Rate"] = (grouped["X2_sum"] / grouped["X2_count"]) * 100
        grouped["X3_Rate"] = (grouped["X3_sum"] / grouped["X3_count"]) * 100
        
        grouped["X1_Label"] = grouped["X1_sum"].astype(str) + "/" + grouped["X1_count"].astype(str) # type: ignore
        grouped["X2_Label"] = grouped["X2_sum"].astype(str) + "/" + grouped["X2_count"].astype(str) # type: ignore
        grouped["X3_Label"] = grouped["X3_sum"].astype(str) + "/" + grouped["X3_count"].astype(str) # type: ignore
        
        grouped["Dataset"] = name
        all_groups.append(grouped)

    if not all_groups:
        print("錯誤：沒有任何可與基線對比的有效觀測數據。")
        return

    # 合併多組觀測資料
    combined = pd.concat(all_groups, ignore_index=True)

    # 套用自訂的 X 軸時段順序
    custom_order = ["12", "15", "18", "21", "22", "23", "0", "1", "2", "3", "6", "9"]
    combined["HourRange"] = pd.Categorical(
        combined["HourRange"], 
        categories=custom_order, 
        ordered=True
    )
    combined = combined.sort_values("HourRange")

    # 轉置各指標資料成繪圖矩陣
    pivot_x1 = combined.pivot(index="HourRange", columns="Dataset", values="X1_Rate").fillna(0)
    pivot_x1_labels = combined.pivot(index="HourRange", columns="Dataset", values="X1_Label").fillna("0/0")
    
    pivot_x2 = combined.pivot(index="HourRange", columns="Dataset", values="X2_Rate").fillna(0)
    pivot_x2_labels = combined.pivot(index="HourRange", columns="Dataset", values="X2_Label").fillna("0/0")
    
    pivot_x3 = combined.pivot(index="HourRange", columns="Dataset", values="X3_Rate").fillna(0)
    pivot_x3_labels = combined.pivot(index="HourRange", columns="Dataset", values="X3_Label").fillna("0/0")

    # 建立 3x1 畫布
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 20), sharex=True)
    colors = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948"]
    color_slice = colors[:len(pivot_x1.columns)]

    # 迴圈繪製三個子圖
    axes = [ax1, ax2, ax3]
    pivots = [pivot_x1, pivot_x2, pivot_x3]
    labels = [pivot_x1_labels, pivot_x2_labels, pivot_x3_labels]
    titles = [
        f"{city}: Network Collapse Rate (X1) - Speed < 15th% of {baseline_name}",
        f"{city}: Latency Spike Rate (X2) - Latency > 85th% of {baseline_name}",
        f"{city}: Loss Prevalence Rate (X3) - Loss Rate > 0.01"
    ]
    ylabels = ["Collapse Rate (%)", "Spike Rate (%)", "Prevalence Rate (%)"]

    for ax, pv, lb, title, ylabel in zip(axes, pivots, labels, titles, ylabels):
        pv.plot(kind="bar", ax=ax, color=color_slice, width=0.8)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_ylim(0, 115)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.legend(title="Dataset")
        
        # 加上分子/分母標註
        for i, dataset_name in enumerate(pv.columns):
            labels_to_show = lb[dataset_name].values
            rects = ax.containers[i]
            for j, rect in enumerate(rects):
                h = rect.get_height()
                lbl = labels_to_show[j]
                ax.annotate(
                    lbl,
                    xy=(rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold",
                )

    # 僅針對最下方子圖設定 X 軸
    ax3.set_xlabel(f"Time Range (UTC{timezone:+d})", fontsize=12)
    ax3.set_xticklabels(pivot_x3.index, rotation=0)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"成功：以 '{baseline_name}' 為基準的三聯網路報告圖已儲存至 {output_path}")



if __name__ == "__main__":

    for s in (2023,2024,2025):

        baseline_df = load_csv([f"in/{s}-baseline.csv", f"in/{s}-baseline-1.csv"], TIMEZONE)

        df = load_json([f"in/taipeicity-{s}1231-{s+1}0102.json"], TIMEZONE)
        # 擷取 12-31 12:00 到隔年 01-01 12:00 區間的數據
        df = df[((df["TestTime"].dt.month == 12) & (df["TestTime"].dt.day == 31) & (df["TestTime"] >= df["TestTime"].dt.normalize() + pd.Timedelta(hours=12))) | 
                ((df["TestTime"].dt.month == 1) & (df["TestTime"].dt.day == 1) & (df["TestTime"] <= df["TestTime"].dt.normalize() + pd.Timedelta(hours=12)))]
        
        # plot_low_speed_ratio({
        #     "baseline": baseline_df, 
        #     f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        # }, CITY, TIMEZONE, f"out/taipeicity-lsr-{s}.png")

        # plot_latency_loss_report({
        #     "baseline": baseline_df, 
        #     f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        # }, CITY, TIMEZONE, f"out/taipeicity-llr-{s}.png")

        # plot_network_performance_report({
        #     "baseline": baseline_df, 
        #     f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        # }, CITY, TIMEZONE, f"out/taipeicity-{s}.png")
        
        plot_network_performance_report_2({
            "baseline": baseline_df, 
            f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        }, CITY, TIMEZONE, f"out/taipeicity-ratio-{s}.png")

        # plot_ny_network_report({
        #     "baseline": baseline_df, 
        #     f"{s}-12-31 12:00 - {s+1}-01-01 12:00": df
        # }, CITY, TIMEZONE, f"out/taipeicity-3X-{s}.png")

