import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.api as sm

# 1. 讀取對齊資料
df = pd.read_csv("out_nye_multi_feature_data.csv") 
y = df['MRT_Accumulated_Crowd']

# 定義要分析的三個自變數
features = ['Net_Collapse_Rate', 'Latency_Spike_Rate', 'Loss_Prevalence_Rate']

# 設定美化風格
sns.set_theme(style="whitegrid")

# 迴圈跑三個指標並各自畫圖
for f_name in features:
    # 建立獨立模型以獲取統計量
    X = sm.add_constant(df[f_name])
    res = sm.OLS(y, X).fit()
    r_corr = df['MRT_Accumulated_Crowd'].corr(df[f_name])
    
    # 建立畫布與軸物件 (使用 subplots 確保佈局正確)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=120)
    
    # 繪製散佈圖與迴歸線（預設帶有 95% 信心區間陰影）
    sns.regplot(
        x=f_name, 
        y='MRT_Accumulated_Crowd', 
        data=df, 
        ax=ax, 
        scatter_kws={'color': '#1f77b4', 'alpha': 0.7, 's': 60}, # 藍色數據點
        line_kws={'color': '#d62728', 'linewidth': 2}          # 紅色迴歸線
    )
    
    # 整理要動態顯示在圖表上的統計資訊
    stats_text = (
        f"Pearson r: {r_corr:.4f}\n"
        f"R²: {res.rsquared:.4f}\n"
        f"Coef: {res.params[f_name]:.4f}\n"
        f"p-value: {res.pvalues[f_name]:.4f}"
    )
    
    # 將統計資訊以精美文字框（bbox）標註在圖表左上角
    ax.text(
        0.05, 0.95, stats_text, 
        transform=ax.transAxes, 
        fontsize=10,
        fontfamily='monospace',
        verticalalignment='top', 
        bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.85, edgecolor='#cccccc')
    )
    
    # 設定標題與坐標軸標籤
    ax.set_title(f"Regression Analysis: MRT_Accumulated_Crowd vs {f_name}", fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel(f_name, fontsize=11, labelpad=8)
    ax.set_ylabel("MRT Accumulated Crowd", fontsize=11, labelpad=8)
    
    # 自動調整版面以防標籤、文字被截斷或重疊
    plt.tight_layout()
    
    # 儲存圖片
    output_filename = f"out/regression_plot_{f_name}.png"
    plt.savefig(output_filename, bbox_inches='tight')
    plt.close()
    
    print(f"已成功生成並儲存圖表：{output_filename}")