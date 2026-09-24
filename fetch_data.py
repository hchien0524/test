import requests
import pandas as pd
import json
from datetime import datetime

print("開始抓取台股行情與法人籌碼資料...")

try:
    # 1. 抓取行情資料
    price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    df_price = pd.DataFrame(requests.get(price_url ).json())
    
    # 清洗行情資料
    df_price['TradeVolume'] = pd.to_numeric(df_price['TradeVolume'], errors='coerce') / 1000
    df_price['ClosingPrice'] = pd.to_numeric(df_price['ClosingPrice'], errors='coerce')
    df_price['Change'] = pd.to_numeric(df_price['Change'], errors='coerce')
    df_price = df_price[~df_price['Code'].str.startswith('0')]
    df_price = df_price[df_price['Code'].str.len() == 4]
    
    # 2. 嘗試抓取法人資料
    fund_url = "https://openapi.twse.com.tw/v1/fund/T86_ALL"
    fund_data = requests.get(fund_url ).json()
    
    if len(fund_data) > 0 and 'ForeignInvestorBuySell' in fund_data[0]:
        df_fund = pd.DataFrame(fund_data)
        df_fund['ForeignInvestor'] = pd.to_numeric(df_fund['ForeignInvestorBuySell'], errors='coerce') / 1000
        df_fund['InvestmentTrust'] = pd.to_numeric(df_fund['InvestmentTrustBuySell'], errors='coerce') / 1000
        
        # 合併與雙重防護網過濾
        df_merge = pd.merge(df_price, df_fund[['Code', 'ForeignInvestor', 'InvestmentTrust']], on='Code', how='inner')
        mask = (df_merge['TradeVolume'] >= 2000) & ((df_merge['InvestmentTrust'] > 0) | (df_merge['ForeignInvestor'] > 500))
        final_df = df_merge[mask].copy()
    else:
        print("⚠️ 籌碼資料尚未更新，僅過濾成交量...")
        final_df = df_price[df_price['TradeVolume'] >= 2000].copy()
        final_df['ForeignInvestor'] = 0
        final_df['InvestmentTrust'] = 0

    # 整理輸出
    final_df['TradeVolume'] = final_df['TradeVolume'].round(0).astype(int)
    final_df['ForeignInvestor'] = final_df['ForeignInvestor'].round(0).astype(int)
    final_df['InvestmentTrust'] = final_df['InvestmentTrust'].round(0).astype(int)
    
    final_df = final_df[['Code', 'Name', 'TradeVolume', 'ClosingPrice', 'Change', 'ForeignInvestor', 'InvestmentTrust']]
    final_df.columns = ['代號', '名稱', '成交量(張)', '收盤價', '漲跌', '外資買賣超(張)', '投信買賣超(張)']
    final_df = final_df.sort_values(by='投信買賣超(張)', ascending=False)

    output_data = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": final_df.to_dict(orient='records')
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ 執行成功！共篩選出 {len(final_df)} 檔標的。")

except Exception as e:
    print(f"❌ 發生錯誤: {e}")
