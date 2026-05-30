"""獨立模型分析"""

import pandas as pd
import statsmodels.api as sm

# 讀取你上一步匯出的對齊資料
df = pd.read_csv("out_nye_multi_feature_data.csv") 
y = df['MRT_Accumulated_Crowd']

def run_independent_model(f_name):
    X = sm.add_constant(df[f_name])
    res = sm.OLS(y, X).fit()
    print(f"\n=========================================")
    print(f" 獨立模型分析： Y vs {f_name}")
    print(f"=========================================")
    print(f"皮爾森相關係數 r: {df['MRT_Accumulated_Crowd'].corr(df[f_name]):.4f}")
    print(f"模型解釋力 R2:   {res.rsquared:.4f}")
    print(f"變數係數 Coef:    {res.params[f_name]:.4f}")
    print(f"變數 p-value:    {res.pvalues[f_name]:.4f}")

# 分開跑三個指標的獨立迴歸
run_independent_model('Net_Collapse_Rate')
run_independent_model('Latency_Spike_Rate')
run_independent_model('Loss_Prevalence_Rate')