import json
import os
import numpy as np
import pandas as pd
import statsmodels.api as sm
from typing import List

# ==========================================
# 1. 核心資料讀取函數
# ==========================================
def load_json(filenames: List[str], timezone: int) -> pd.DataFrame:
    """讀取多個 JSON 檔案，解析並合併為單一 DataFrame。"""
    all_parsed_list = []
    for filename in filenames:
        if not os.path.exists(filename):
            print(f"警告：找不到檔案 {filename}，跳過。")
            continue
        with open(filename, "r", encoding="utf-8") as fp:
            contents = json.loads(fp.read())
            for data in contents:
                all_parsed_list.append({
                    "TestTime": data["TestTime"],
                    "Speed": float(data["MeanThroughputMbps"]),
                    "City": data["Subdivision1Name"],
                    'Latency': float(data['MinRTT']),
                    'LossRate': float(data['LossRate']),
                })
    if not all_parsed_list:
        raise Exception("錯誤：未讀取到任何有效 JSON 資料。")
    df = pd.DataFrame(all_parsed_list)
    df["TestTime"] = pd.to_datetime(df["TestTime"]) + pd.Timedelta(hours=timezone)
    return df

def load_csv(filenames: List[str], timezone: int) -> pd.DataFrame:
    """讀取多個 CSV 檔案，解析並合併為單一 DataFrame。"""
    dfs = []
    for filename in filenames:
        if not os.path.exists(filename):
            print(f"警告：找不到檔案 {filename}，跳過。")
            continue
        df_temp = pd.read_csv(filename)
        df_temp = df_temp[[
            "TestTime",
            "MeanThroughputMbps",
            "Subdivision1Name",
            "MinRTT",
            "LossRate",
        ]].rename(columns={
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
        raise Exception("錯誤：未讀取到任何有效 CSV 資料。")
    df = pd.concat(dfs, ignore_index=True)
    df["TestTime"] = pd.to_datetime(df["TestTime"]) + pd.Timedelta(hours=timezone)
    return df

# ==========================================
# 2. 主要分析與統計管線 (Data Pipeline)
# ==========================================
def main_pipeline():
    years = [2023, 2024, 2025]
    timezone = 8  # 台北時區 UTC+8
    target_stations = ['市政府', '台北101/世貿', '國父紀念館', '象山'] # 一級戰區車站 
    
    # 定義標準牆上時間的 9 個小時觀測點 (用於 M-Lab 時間篩選)
    # 格式：(日期標籤, 小時) -> 'nye' 代表 12/31, 'nyd' 代表 1/1
    time_sequence = [
        ('nye', 18), ('nye', 19), ('nye', 20), ('nye', 21), ('nye', 22), ('nye', 23),
        ('nyd', 0), ('nyd', 1), ('nyd', 2)
    ]
    
    final_records = []
    
    for s in years:
        print(f"\n⏳ 正在處理 {s} -> {s+1} 跨年時段資料...")
        
        # ----------------------------------------------------
        # Part A: 讀取並整合北捷資料 (同時合併當年度與 -1 檔案)
        # ----------------------------------------------------
        metro_paths = [f"in/metro-{s}.csv", f"in/metro-{s}-1.csv"]
        metro_dfs = []
        for path in metro_paths:
            if os.path.exists(path):
                metro_dfs.append(pd.read_csv(path))
        
        if not metro_dfs:
            print(f"❌ 錯誤：找不到 {s} 年度的捷運資料，跳過。")
            continue
            
        df_metro_year = pd.concat(metro_dfs, ignore_index=True)
        df_metro_year['時段'] = df_metro_year['時段'].astype(int)
        
        # ----------------------------------------------------
        # Part B: 依照累積存量規則，依序計算每小時的「流量差額」
        # ----------------------------------------------------
        hourly_net_flows = []
        
        for day_type, wall_hour in time_sequence:
            # 由於已經加載了包含 1/1 資料的 -1.csv，直接對齊標準日曆時間即可
            if day_type == 'nye':
                mrt_date = f"{s}-12-31"
            else: # 1/1 凌晨
                mrt_date = f"{s+1}-01-01"
            
            mrt_hour = wall_hour
            
            # 篩選特定日期、時段與核心戰區車站 
            sub_mrt = df_metro_year[(df_metro_year['日期'] == mrt_date) & (df_metro_year['時段'] == mrt_hour)]

            # 出站代表湧入會場 (+)，進站代表離開會場 (-) 
            outbound_cnt = sub_mrt[sub_mrt['出站'].isin(target_stations)]['人次'].sum()
            inbound_cnt = sub_mrt[sub_mrt['進站'].isin(target_stations)]['人次'].sum()
            
            # 每小時淨流入量 (Flow)
            net_flow = outbound_cnt - inbound_cnt 
            hourly_net_flows.append(net_flow)
            
        # 使用 .cumsum() 將「流量」轉化為「動態累積淨存量」(Stock) 
        hourly_accumulated_crowd = np.cumsum(hourly_net_flows) 
        
        # ----------------------------------------------------
        # Part C: 讀取網路數據並進行多維度門檻建構 (Baseline)
        # ----------------------------------------------------
        nye_json_path = f"in/taipeicity-{s}1231-{s+1}0102.json" 
        base_csv_paths = [f"in/{s}-baseline.csv", f"in/{s}-baseline-1.csv"] 
        
        df_nye = load_json([nye_json_path], timezone)
        df_base = load_csv(base_csv_paths, timezone)
        
        df_base['Hour'] = df_base['TestTime'].dt.hour
        df_nye['Hour'] = df_nye['TestTime'].dt.hour
        df_nye['DateStr'] = df_nye['TestTime'].dt.strftime('%Y-%m-%d')
        
        num_baseline_days = df_base['TestTime'].dt.date.nunique()
        if num_baseline_days == 0: num_baseline_days = 6
        
        # 建立該年度 Baseline 的每小時動態門檻字典
        baseline_thresholds = {}
        for _, wall_hour in time_sequence:
            df_base_h = df_base[(df_base['Hour'] == wall_hour) & (df_base['City'] == 'Taipei City')]
            if len(df_base_h) > 0:
                thru_thresh = np.percentile(df_base_h['Speed'], 15)      # 網速平日低端門檻 (後15%)
                latency_thresh = np.percentile(df_base_h['Latency'], 85) # 延遲平日頂峰天花板 (前85%)
                n_base = len(df_base_h) / num_baseline_days
            else:
                thru_thresh = 15.0
                latency_thresh = 40.0
                n_base = 15.0
            baseline_thresholds[wall_hour] = {
                'thru_thresh': thru_thresh, 
                'latency_thresh': latency_thresh,
                'n_base': n_base
            }
            
        # ----------------------------------------------------
        # Part D: 多維度特徵工程與捷運「累積存量」合併 
        # ----------------------------------------------------
        for idx, (day_type, wall_hour) in enumerate(time_sequence):
            target_date = f"{s}-12-31" if day_type == 'nye' else f"{s+1}-01-01"
            
            # 網路當晚測資
            df_nye_h = df_nye[(df_nye['Hour'] == wall_hour) & (df_nye['DateStr'] == target_date)]
            n_nye = len(df_nye_h)
            
            # 讀取該小時對應的 Baseline 門檻
            thresh_stats = baseline_thresholds[wall_hour]
            thru_thresh = thresh_stats['thru_thresh']
            latency_thresh = thresh_stats['latency_thresh']
            n_base = thresh_stats['n_base']
            
            # 特徵一：網速門檻超越率 (Net_Collapse_Rate)
            net_collapse_rate = (df_nye_h['Speed'] < thru_thresh).sum() / n_nye if n_nye > 0 else 0.0 
            
            # 特徵二：黑洞編碼率 (Data_Deficit_Rate)
            data_deficit_rate = (n_base - n_nye) / n_base if n_base > 0 else 0.0 
            
            # 特徵三：延遲異動率 (Latency_Spike_Rate) -> 超越平日天花板比例
            latency_spike_rate = (df_nye_h['Latency'] > latency_thresh).sum() / n_nye if n_nye > 0 else 0.0
            
            # 特徵四：嚴重複雜丟包率 (Loss_Prevalence_Rate) -> 遭遇實體設備強制丟包 > 1% 比例
            loss_prevalence_rate = (df_nye_h['LossRate'] > 0.01).sum() / n_nye if n_nye > 0 else 0.0
            
            # 讀取該小時對應的「捷運累積滯留人數」
            mrt_stock_volume = hourly_accumulated_crowd[idx] 
            
            final_records.append({
                'Year': s,
                'Hour': wall_hour,
                'MRT_Accumulated_Crowd': mrt_stock_volume,
                'Net_Collapse_Rate': net_collapse_rate,
                'Data_Deficit_Rate': data_deficit_rate,
                'Latency_Spike_Rate': latency_spike_rate,
                'Loss_Prevalence_Rate': loss_prevalence_rate
            })

    # 建立最終 27 筆觀測樣本的完整數據集 
    df_model = pd.DataFrame(final_records)
    
    print("\n" + "="*60)
    print("📊 統計建模矩陣建構完畢 - 輸出全新多維度模型報告數據")
    print("="*60)
    print(f"有效觀測樣本總數: {len(df_model)}")
    
    # 1. 相關性矩陣分析 (包含新維度)
    corr_cols = ['MRT_Accumulated_Crowd', 'Net_Collapse_Rate', 'Data_Deficit_Rate', 'Latency_Spike_Rate', 'Loss_Prevalence_Rate']
    corr_matrix = df_model[corr_cols].corr(method='pearson')
    print("\n[1] 新模型：皮爾森相關係數矩陣 (Pearson Correlation Matrix):")
    print(corr_matrix.round(4))
    
    # 2. 多元線性迴歸 (OLS) 
    # features = ['Net_Collapse_Rate', 'Data_Deficit_Rate', 'Latency_Spike_Rate', 'Loss_Prevalence_Rate']
    features = ['Net_Collapse_Rate', 'Data_Deficit_Rate']
    X = df_model[features]
    X = sm.add_constant(X)
    y = df_model['MRT_Accumulated_Crowd']
    
    model = sm.OLS(y, X).fit()
    
    print("\n[2] 新模型：多元線性迴歸分析結果 (OLS Regression Summary):")
    print(model.summary())
    
    # 匯出資料
    df_model.to_csv("out_nye_multi_feature_data.csv", index=False)
    print("\n💾 數據已成功匯出至 'out_nye_multi_feature_data.csv'，請用此完整檔數據更新你的期末報告。")

if __name__ == "__main__":
    main_pipeline()