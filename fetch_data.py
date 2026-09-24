import requests
import pandas as pd
import json
from datetime import datetime

print("開始抓取台股行情與法人籌碼資料...")

# 1. 抓取行情資料
price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
price_res = requests.get(price_url ).json()
df_price = pd.DataFrame(price_res)

# 2. 抓取三大法人買賣超資料
fund_url = "https://openapi.twse.com.tw/v1/fund/T86_ALL"
fund_res = requests.get(fund_url ).json()
df_fund = pd.DataFrame(fund_res)

# 3. 資料清洗與轉換
df_price['TradeVolume'] = pd.to_numeric(df_price['TradeVolume'], errors='coerce') / 1000
df_price['ClosingPrice'] = pd.to_numeric(df_price['ClosingPrice'], errors='coerce')
df_price['Change'] = pd.to_numeric(df_price['Change'], errors='coerce')

# 排除 ETF 與權證 (過濾掉代號是 0 開頭，以及長度超過 4 碼的標的)
df_price = df_price[~df_price['Code'].str.startswith('0')]
df_price = df_price[df_price['Code'].str.len() == 4]

# 籌碼資料處理 (外資與投信買賣超)
df_fund['ForeignInvestor'] = pd.to_numeric(df_fund['ForeignInvestorBuySell'], errors='coerce') / 1000
df_fund['InvestmentTrust'] = pd.to_numeric(df_fund['InvestmentTrustBuySell'], errors='coerce') / 1000

# 4. 合併資料
df_merge = pd.merge(df_price, df_fund[['Code', 'ForeignInvestor', 'InvestmentTrust']], on='Code', how='inner')

# 5. 啟動雙重防護網：有量 ( > 2000張 ) 且有法人認養 (投信買超>0 或 外資買超>500)
mask_volume = df_merge['TradeVolume'] >= 2000
mask_chips = (df_merge['InvestmentTrust'] > 0) | (df_merge['ForeignInvestor'] > 500)
final_df = df_merge[mask_volume & mask_chips].copy()

# 整理與格式化輸出 (取整數方便閱讀)
final_df['TradeVolume'] = final_df['TradeVolume'].round(0).astype(int)
final_df['ForeignInvestor'] = final_df['ForeignInvestor'].round(0).astype(int)
final_df['InvestmentTrust'] = final_df['InvestmentTrust'].round(0).astype(int)

final_df = final_df[['Code', 'Name', 'TradeVolume', 'ClosingPrice', 'Change', 'ForeignInvestor', 'InvestmentTrust']]
final_df.columns = ['代號', '名稱', '成交量(張)', '收盤價', '漲跌', '外資買賣超(張)', '投信買賣超(張)']

# 依投信買超張數排序 (跟隨絕對的內資主力)
final_df = final_df.sort_values(by='投信買賣超(張)', ascending=False)

output_data = {
    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "stocks": final_df.to_dict(orient='records')
}

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=4)

print(f"✅ 雙重防護網過濾完成！精選出 {len(final_df)} 檔真金白銀認養標的。")
