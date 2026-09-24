import requests
import pandas as pd
import json
import os
from datetime import datetime

# 1. 抓取證交所每日收盤行情 (Open API)
url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
response = requests.get(url )
data = response.json()

# 2. 轉換為 Pandas DataFrame 方便進行量化過濾
df = pd.DataFrame(data)

# 3. 資料清洗與型態轉換
# 證交所的 TradeVolume 是「股數」，除以 1000 轉換為「張數」
df['TradeVolume'] = pd.to_numeric(df['TradeVolume'], errors='coerce') / 1000
df['ClosingPrice'] = pd.to_numeric(df['ClosingPrice'], errors='coerce')
df['Change'] = pd.to_numeric(df['Change'], errors='coerce')

# 4. 強制寫入防護網：過濾日均量 < 2000張 的股票
filtered_df = df[df['TradeVolume'] >= 2000].copy()

# 整理輸出欄位
filtered_df = filtered_df[['Code', 'Name', 'TradeVolume', 'ClosingPrice', 'Change']]
filtered_df.columns = ['代號', '名稱', '成交量(張)', '收盤價', '漲跌']

# 5. 依成交量排序 (由大到小)
filtered_df = filtered_df.sort_values(by='成交量(張)', ascending=False)

# 6. 輸出為 JSON 供前端網頁讀取
output_data = {
    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "stocks": filtered_df.to_dict(orient='records')
}

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=4)

print(f"✅ 資料抓取完成！共篩選出 {len(filtered_df)} 檔大於 2000 張的標的。")
