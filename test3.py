"""繪製折線圖"""

import pandas as pd
import matplotlib.pyplot as plt

# 1. 讀取 CSV 資料
df = pd.read_csv("out_nye_multi_feature_data.csv")

# 2. 定義要分析的年份
years = [2023, 2024, 2025]

# 3. 依年份分別繪製折線圖並儲存
for year in years:
    # 使用 subplots 建立畫布與主要座標軸 (ax1)
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 篩選特定年份資料
    df_year = df[df['Year'] == year].copy()
    
    # 將 Hour 轉換為字串，以保持從 18 點到凌晨 2 點的跨年時間先後順序
    df_year['Hour_Str'] = df_year['Hour'].astype(str)
    
    # ---- 繪製主要 Y 軸 (左邊)：三個網路指標 ----
    line1 = ax1.plot(df_year['Hour_Str'], df_year['Net_Collapse_Rate'], marker='o', linewidth=2, label='Net_Collapse_Rate', color='tab:blue')
    line2 = ax1.plot(df_year['Hour_Str'], df_year['Latency_Spike_Rate'], marker='s', linewidth=2, label='Latency_Spike_Rate', color='tab:orange')
    line3 = ax1.plot(df_year['Hour_Str'], df_year['Loss_Prevalence_Rate'], marker='^', linewidth=2, label='Loss_Prevalence_Rate', color='tab:green')
    
    # 設定主要 Y 軸的標籤與樣式
    ax1.set_xlabel('Hour (Time Sequence)', fontsize=12)
    ax1.set_ylabel('Network Metrics Rate', fontsize=12, color='black')
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.grid(True, linestyle='--', alpha=0.6)
    
    # ---- 繪製次要 Y 軸 (右邊)：捷運人流數 ----
    ax2 = ax1.twinx()  # 共享 X 軸，建立次要 Y 軸
    # 使用紅色 (tab:red) 與點線 (linestyle=':') 來與網路指標做視覺區隔
    line4 = ax2.plot(df_year['Hour_Str'], df_year['MRT_Accumulated_Crowd'], marker='d', linewidth=2, linestyle=':', label='MRT_Accumulated_Crowd', color='tab:red')
    
    # 設定次要 Y 軸的標籤與樣式
    ax2.set_ylabel('MRT Accumulated Crowd', fontsize=12, color='tab:red')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    
    # ---- 合併左、右兩邊的圖例 (Legend) ----
    lines = line1 + line2 + line3 + line4
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left') # type: ignore
    
    # 設定圖表標題
    plt.title(f'Network Performance vs MRT Crowd - Year {year}', fontsize=14)
    
    # 自動調整佈局防止標籤切到，並儲存圖表
    plt.tight_layout()
    plt.savefig(f'out/network_trends_{year}.png', dpi=150)
    plt.close()  # 關閉目前的圖表物件，釋放記憶體（比 clf() 在物件導向寫法中更乾淨）
    print(f"成功產生圖表: network_trends_{year}.png")