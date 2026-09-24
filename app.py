import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf

# ==========================================
# 1. 頁面與全域設定
# ==========================================
st.set_page_config(page_title="法人級量化防護網", layout="wide", page_icon="🛡️")
st.title("🛡️ 法人級動態量化儀表板")

# ==========================================
# 2. 資料抓取引擎 (加入偽裝與快取)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_twse_data():
    try:
        # 加上 User-Agent，偽裝成正常的 Chrome 瀏覽器，避免被證交所防火牆阻擋
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        
        # 抓取報價與成交量
        price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        price_res = requests.get(price_url, headers=headers )
        
        if price_res.status_code != 200:
            st.error(f"證交所行情 API 拒絕連線 (狀態碼: {price_res.status_code})，請稍後再試。")
            return pd.DataFrame()
            
        df_price = pd.DataFrame(price_res.json())
        df_price['TradeVolume'] = pd.to_numeric(df_price['TradeVolume'], errors='coerce') / 1000
        df_price['ClosingPrice'] = pd.to_numeric(df_price['ClosingPrice'], errors='coerce')
        df_price['Change'] = pd.to_numeric(df_price['Change'], errors='coerce')
        df_price = df_price[~df_price['Code'].str.startswith('0')]
        df_price = df_price[df_price['Code'].str.len() == 4]

        # 抓取三大法人
        fund_url = "https://openapi.twse.com.tw/v1/fund/T86_ALL"
        fund_res = requests.get(fund_url, headers=headers )
        
        df_fund = pd.DataFrame(columns=['Code', 'ForeignInvestor', 'InvestmentTrust'])
        if fund_res.status_code == 200:
            fund_data = fund_res.json()
            if len(fund_data) > 0 and 'ForeignInvestorBuySell' in fund_data[0]:
                df_fund = pd.DataFrame(fund_data)
                df_fund['ForeignInvestor'] = pd.to_numeric(df_fund['ForeignInvestorBuySell'], errors='coerce') / 1000
                df_fund['InvestmentTrust'] = pd.to_numeric(df_fund['InvestmentTrustBuySell'], errors='coerce') / 1000

        # 合併資料
        if not df_fund.empty:
            df_merge = pd.merge(df_price, df_fund[['Code', 'ForeignInvestor', 'InvestmentTrust']], on='Code', how='left')
            df_merge.fillna(0, inplace=True)
        else:
            df_merge = df_price.copy()
            df_merge['ForeignInvestor'] = 0
            df_merge['InvestmentTrust'] = 0
            
        return df_merge
    except Exception as e:
        st.error(f"資料解碼失敗 (證交所可能正在更新資料): {e}")
        return pd.DataFrame()

# ==========================================
# 3. 左側邊欄：戰略參數控制台
# ==========================================
st.sidebar.header("⚙️ 防護網底線設定")
min_volume = st.sidebar.slider("最低日均量要求 (張)", min_value=500, max_value=10000, value=2000, step=500)
min_trust_buy = st.sidebar.slider("投信最低買超 (張)", min_value=0, max_value=3000, value=100, step=100)

st.sidebar.markdown("---")
st.sidebar.header("🎯 波段因子模型選擇")
strategy = st.sidebar.radio("策略邏輯", ["短波段 (動能爆發)", "長波段 (籌碼沉澱)"])

# 讀取基礎資料
raw_df = fetch_twse_data()

# ==========================================
# 4. 核心邏輯：雙重防護網過濾
# ==========================================
if not raw_df.empty:
    mask_volume = raw_df['TradeVolume'] >= min_volume
    mask_trust = raw_df['InvestmentTrust'] >= min_trust_buy
    
    filtered_df = raw_df[mask_volume & mask_trust].copy()
    filtered_df = filtered_df.sort_values(by='InvestmentTrust', ascending=False)
    
    display_df = filtered_df[['Code', 'Name', 'TradeVolume', 'ClosingPrice', 'Change', 'ForeignInvestor', 'InvestmentTrust']].copy()
    display_df.columns = ['代號', '名稱', '成交量(張)', '收盤價', '漲跌', '外資買賣超(張)', '投信買賣超(張)']
    
    col1, col2, col3 = st.columns(3)
    col1.metric("今日掃描總檔數", f"{len(raw_df)} 檔")
    col2.metric("符合防護網標的", f"{len(display_df)} 檔")
    if not display_df.empty:
        col3.metric("最強投信認養", f"{display_df.iloc[0]['名稱']} ({display_df.iloc[0]['投信買賣超(張)']:.0f}張)")
    else:
        col3.metric("最強投信認養", "無")
    
    st.markdown("### 📋 實戰選股清單 (可點擊欄位排序)")
    st.dataframe(display_df.style.format({
        '成交量(張)': "{:,.0f}",
        '外資買賣超(張)': "{:,.0f}",
        '投信買賣超(張)': "{:,.0f}"
    }), use_container_width=True)

    # ==========================================
    # 5. 微觀診斷：動態 K 線與技術分析
    # ==========================================
    st.markdown("---")
    st.markdown("### 📈 微觀結構與技術診斷")
    
    if not display_df.empty:
        selected_stock = st.selectbox("請選擇要診斷的標的：", display_df['代號'] + " " + display_df['名稱'])
        stock_code = selected_stock.split(" ")[0]
        
        with st.spinner(f'正在抓取 {selected_stock} 的歷史資料與計算指標...'):
            hist = yf.download(f"{stock_code}.TW", period="6mo", progress=False)
            
            if not hist.empty:
                hist['5MA'] = hist['Close'].rolling(window=5).mean()
                hist['20MA'] = hist['Close'].rolling(window=20).mean()
                hist['60MA'] = hist['Close'].rolling(window=60).mean()
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.03, subplot_titles=(f'{selected_stock} 價格與均線', '成交量'), 
                                    row_width=[0.2, 0.7])

                fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'].squeeze(), high=hist['High'].squeeze(),
                                             low=hist['Low'].squeeze(), close=hist['Close'].squeeze(), name='K線'), row=1, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['5MA'].squeeze(), line=dict(color='blue', width=1), name='5MA'), row=1, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['20MA'].squeeze(), line=dict(color='orange', width=1), name='20MA'), row=1, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['60MA'].squeeze(), line=dict(color='green', width=1), name='60MA'), row=1, col=1)
                
                colors = ['red' if close >= open_ else 'green' for close, open_ in zip(hist['Close'].squeeze(), hist['Open'].squeeze())]
                fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'].squeeze(), marker_color=colors, name='成交量'), row=2, col=1)

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, template='plotly_white')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("無法抓取該標的的歷史 K 線資料。")
else:
    st.warning("⚠️ 查無資料，請確認 API 連線狀態或稍後再試。")
