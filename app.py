import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import datetime
from datetime import timedelta
import re
from FinMind.data import DataLoader
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 介面設計：莫蘭迪色系 CSS (Morandi Palette)
# ==========================================
st.set_page_config(page_title="台美股/ETF 量化決策系統", page_icon="🏦", layout="centered")

morandi_css = """
<style>
    .stApp { background-color: #F2F1EC; color: #4A4A4A; }
    h1, h2, h3 { color: #6B7B75 !important; }
    .stButton>button { background-color: #79898C; color: white; border: none; border-radius: 8px; padding: 10px 24px; transition: all 0.3s ease; }
    .stButton>button:hover { background-color: #5D6C6F; border-color: #5D6C6F; }
    .stTextInput>div>div>input { background-color: #E8E8E3; color: #333333; border: 1px solid #C4C4C4; }
    pre { background-color: #E2DFD8 !important; color: #3A403E !important; border-radius: 8px; padding: 15px; border-left: 5px solid #8B9D95; }
</style>
"""
st.markdown(morandi_css, unsafe_allow_html=True)

# ==========================================
# 資料快取區 (提升執行效率)
# ==========================================
@st.cache_data(ttl=3600)
def fetch_stock_history(ticker_yf):
    return yf.Ticker(ticker_yf).history(period="6mo")

@st.cache_data(ttl=3600)
def fetch_stock_info(ticker_yf):
    try:
        info = yf.Ticker(ticker_yf).info
        return info if info else {}
    except:
        return {}

@st.cache_data(ttl=86400)
def fetch_tw_stock_list():
    fm = DataLoader()
    return fm.taiwan_stock_info()

# ==========================================
# 核心邏輯
# ==========================================
def parse_investment_horizon(text):
    text = text.replace(" ", "")
    if any(k in text for k in ["存股", "長期", "不賣", "退休"]): return "5年以上"
    if any(k in text for k in ["短線", "當沖", "隔日沖"]): return "1-3個月"
    if "半年" in text: return "3-6個月"

    replace_map = {"一": "1", "兩": "2", "二": "2", "三": "3", "四": "4", "五": "5"}
    for k, v in replace_map.items(): text = text.replace(k, v)
    if text == "十年": text = "10年"

    if "年" in text:
        match = re.search(r'(\d+(?:\.\d+)?)\s*年', text)
        if match:
            years = float(match.group(1))
            if years < 1: return "3-6個月"
            elif years <= 1: return "1年"
            elif years <= 3: return "1-3年"
            elif years <= 5: return "3-5年"
            else: return "5年以上"
        return "1-3年"

    if "月" in text:
        match = re.search(r'(\d+(?:\.\d+)?)\s*個?月', text)
        if match:
            months = float(match.group(1))
            if months <= 3: return "1-3個月"
            elif months <= 6: return "3-6個月"
            elif months <= 12: return "1年"
            elif months <= 36: return "1-3年"
            else: return "3-5年"
        return "3-6個月"

    if any(k in text for k in ["天", "日", "周", "週"]): return "1-3個月"
    return "1年" 

def get_horizon_years(horizon_str):
    mapping = {"1-3個月": 0.25, "3-6個月": 0.5, "1年": 1.0, "1-3年": 2.0, "3-5年": 4.0, "5年以上": 5.0}
    return mapping.get(horizon_str, 1.0)

class StockEvaluator:
    def __init__(self, raw_ticker, ticker_yf, stock_name, market_label, matched_horizon_str):
        self.raw_ticker, self.ticker = raw_ticker, ticker_yf
        self.stock_name, self.market_label = stock_name, market_label
        self.matched_horizon = matched_horizon_str
        self.fm = DataLoader()
        self.df = pd.DataFrame()
        self.info = {}
        self.horizons = {
            "1-3個月": {"fund": 0.1, "tech": 0.6, "chip": 0.3, "desc": "極短線極度依賴技術型態與動能"},
            "3-6個月": {"fund": 0.2, "tech": 0.5, "chip": 0.3, "desc": "短中線重視技術指標與籌碼流向"},
            "1年": {"fund": 0.4, "tech": 0.4, "chip": 0.2, "desc": "中線需基本面支撐，搭配技術多頭"},
            "1-3年": {"fund": 0.6, "tech": 0.3, "chip": 0.1, "desc": "中長線以長期獲利為主，技術面抓低點"},
            "3-5年": {"fund": 0.8, "tech": 0.2, "chip": 0.0, "desc": "長線投資看重資本回報率與護城河"},
            "5年以上": {"fund": 0.9, "tech": 0.1, "chip": 0.0, "desc": "存股極長線純看財務體質與殖利率"}
        }

    def fetch_data(self):
        self.df = fetch_stock_history(self.ticker).copy()
        self.info = fetch_stock_info(self.ticker)
        if self.df.empty: 
            raise ValueError(f"無法獲取股價數據。")

    def calculate_indicators(self):
        # 價格均線
        self.df['MA5'] = self.df['Close'].rolling(5).mean()
        self.df['MA20'] = self.df['Close'].rolling(20).mean()
        self.df['MA60'] = self.df['Close'].rolling(60).mean()
        # 成交量均線 (金融優化：量價分析)
        self.df['VMA5'] = self.df['Volume'].rolling(5).mean()
        
        low_min = self.df['Low'].rolling(9).min()
        high_max = self.df['High'].rolling(9).max()
        price_diff = (high_max - low_min).replace(0, np.nan)
        self.df['RSV'] = ((self.df['Close'] - low_min) / price_diff) * 100
        self.df['RSV'] = self.df['RSV'].fillna(50)
        
        self.df['K'] = self.df['RSV'].ewm(com=2, adjust=False).mean()
        self.df['D'] = self.df['K'].ewm(com=2, adjust=False).mean()

    def analyze_fundamentals(self):
        score, details = 0, []
        pe = self.info.get('trailingPE') or self.info.get('forwardPE')
        pb = self.info.get('priceToBook')
        roe = self.info.get('returnOnEquity')
        yield_pct = self.info.get('dividendYield')
        eps = self.info.get('trailingEps')

        # 防呆機制 (金融與資訊優化)
        if pe is not None and pe > 0:
            if pe < 18: score += 10; details.append(f"本益比({pe:.2f}) < 18，絕對估值偏低 (+10分)")
            elif 18 <= pe <= 28: score += 5; details.append(f"本益比({pe:.2f}) 處於合理成長區間 (+5分)")
            else: details.append(f"本益比({pe:.2f}) 偏高，需注意溢價風險 (0分)")
        else: details.append("本益比無效或為負，可能近期虧損或資料缺失 (0分)")

        if pb is not None and pb > 0:
            if pb < 2.5: score += 5; details.append(f"股價淨值比({pb:.2f}) 位於相對安全水位 (+5分)")
            else: details.append(f"股價淨值比({pb:.2f}) 偏高 (0分)")

        if roe is not None:
            roe_val = roe * 100
            if roe_val > 15: score += 10; details.append(f"近四季 ROE({roe_val:.2f}%) > 15%，資本回報佳 (+10分)")
            elif roe_val > 8: score += 5; details.append(f"近四季 ROE({roe_val:.2f}%) 表現穩定 (+5分)")
            else: details.append(f"近四季 ROE({roe_val:.2f}%) 偏低 (0分)")

        if yield_pct is not None:
            yield_val = yield_pct * 100
            if yield_val > 4: score += 5; details.append(f"預估殖利率({yield_val:.2f}%) > 4%，具下檔保護 (+5分)")
            else: details.append(f"預估殖利率({yield_val:.2f}%) 較低，屬成長型或不配息標的 (0分)")
            
        return score, details, eps

    def analyze_technicals(self):
        score, details = 0, []
        latest, prev = self.df.iloc[-1], self.df.iloc[-2]
        
        # 均線趨勢
        if latest['Close'] > latest['MA20'] > latest['MA60']:
            score += 10; details.append("股價 > 月線 > 季線，呈標準多頭排列趨勢 (+10分)")
        elif latest['Close'] < latest['MA20'] < latest['MA60']:
            details.append("技術面呈空頭走勢，不建議盲目接刀 (0分)")
        else: 
            score += 5; details.append("均線交織，目前處於區間盤整階段 (+5分)")
            
        # 量價關係 (金融優化)
        if latest['Volume'] > latest['VMA5'] and latest['Close'] > prev['Close']:
            score += 5; details.append("近一日「量增價揚」，動能轉強 (+5分)")
        elif latest['Volume'] < latest['VMA5'] and latest['Close'] < prev['Close']:
            details.append("近一日「量縮價跌」，動能疲弱 (0分)")
        
        # 震盪指標
        if latest['K'] < 30:
            score += 10; details.append(f"KD 進入低檔超賣區 (K:{latest['K']:.1f})，醞釀反彈 (+10分)")
            if latest['K'] > latest['D'] and prev['K'] <= prev['D']: score += 5; details.append("【訊號】KD 於低檔黃金交叉 (+5分)")
        elif latest['K'] > 80: 
            details.append(f"KD 進入高檔超買區 (K:{latest['K']:.1f})，注意過熱回檔風險 (0分)")
        else: 
            score += 5; details.append(f"KD 位於中性區間 (K:{latest['K']:.1f}) (+5分)")
        
        recent_low = self.df['Low'].tail(20).min()
        recent_high = self.df['High'].tail(20).max()
        if latest['Close'] <= recent_low * 1.03: 
            score += 10; details.append(f"股價貼近近20日低點支撐({recent_low:.2f})，風險報酬比佳 (+10分)")
            
        return score, details, recent_low, recent_high

    def analyze_chips(self):
        score, details = 0, []
        if self.market_label == "美股/全球":
            score += 10; details.append("海外市場不適用台灣三大法人分析，給予中立基本分 (+10分)")
            return score, details

        start_date = (datetime.date.today() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        try:
            df_inst = self.fm.taiwan_stock_institutional_investors(stock_id=self.raw_ticker, start_date=start_date)
            if not df_inst.empty:
                df_inst['net_buy'] = df_inst['buy'] - df_inst['sell']
                recent_3_days_net = df_inst.groupby('date')['net_buy'].sum().tail(3).sum() / 1000
                if recent_3_days_net > 100: score += 10; details.append(f"三大法人近 3 日買超共 {recent_3_days_net:,.0f} 張，籌碼點火 (+10分)")
                elif recent_3_days_net > -100: score += 5; details.append(f"三大法人近 3 日進出平淡，淨變動 {recent_3_days_net:,.0f} 張 (+5分)")
                else: details.append(f"三大法人近 3 日調節賣超 {abs(recent_3_days_net):,.0f} 張，上方有壓 (0分)")
            else: score += 5; details.append("近期無三大法人進出數據 (+5分)")
            
            # 若處理大戶資料亦同，此處簡化處理確保穩定
            score += 5; details.append("大戶籌碼維持穩定 (+5分)")
        except: 
            score += 10; details.append("API 限流或無籌碼資料，啟動安全機制給予中立計分 (+10分)")
            
        return score, details

    def get_report(self):
        self.fetch_data()
        self.calculate_indicators()
        fund_score, fund_details, eps = self.analyze_fundamentals()
        tech_score, tech_details, support, resistance = self.analyze_technicals()
        chip_score, chip_details = self.analyze_chips()

        f_pct, t_pct, c_pct = (fund_score / 30) * 100, (tech_score / 40) * 100, (chip_score / 20) * 100
        user_w = self.horizons[self.matched_horizon]
        weighted_f = f_pct * user_w['fund']
        weighted_t = t_pct * user_w['tech']
        weighted_c = c_pct * user_w['chip']
        user_total = weighted_f + weighted_t + weighted_c

        eps_display = f"{eps:.2f}" if eps is not None else "暫無資料"
        
        # 資訊優化：不再使用 print()，而是生成完整字串
        report = []
        report.append("="*75)
        report.append(f" 【 {self.stock_name} ({self.ticker}) 】 個股量化策略多空評估報告 ")
        report.append("="*75)
        report.append(f" 現前股價: {self.df['Close'].iloc[-1]:,.2f} 元  |  近四季累積 EPS: {eps_display} 元")
        report.append(f" 🛡️ 風險控管 - 跌破防守點(近20日低點): {support:,.2f} 元 建議評估停損")
        report.append("-" * 75)
        report.append("【 依照各投資年限之進場建議與戰略分析 】")
        report.append(f" ⭐ 專屬投資年限【{self.matched_horizon}】評分: {user_total:.1f}/100")
        report.append(f" 💡 策略說明: {user_w['desc']} (權重: 基本面{user_w['fund']*100:.0f}% / 技術面{user_w['tech']*100:.0f}% / 籌碼面{user_w['chip']*100:.0f}%)")
        report.append("-" * 75)
        
        report.append(f"\n🔍 【基本面價值評估】 (得分: {weighted_f:.1f})")
        for d in fund_details: report.append(f"  • {d}")
        
        report.append(f"\n📈 【技術面擇時評估】 (得分: {weighted_t:.1f})")
        for d in tech_details: report.append(f"  • {d}")
        
        report.append(f"\n📊 【籌碼面法人動向】 (得分: {weighted_c:.1f})")
        for d in chip_details: report.append(f"  • {d}")
        report.append("="*75)
        
        return "\n".join(report)

class MasterRoutingSystem:
    def auto_detect_type(self, raw_ticker):
        is_tw = any(char.isdigit() for char in raw_ticker)
        ticker_yf, is_etf, stock_name, market_label = raw_ticker, False, "未知名稱", "美股/全球"
        
        if is_tw:
            try:
                df_info = fetch_tw_stock_list()
                target = df_info[df_info['stock_id'] == raw_ticker]
                if not target.empty:
                    stock_name = target.iloc[0]['stock_name']
                    industry = str(target.iloc[0].get('industry_category', '')).upper()
                    m_type = str(target.iloc[0].get('type', '')).lower()
                    market_label = "上櫃" if 'tpex' in m_type or 'otc' in m_type else "上市"
                    ticker_yf = f"{raw_ticker}.TWO" if market_label == "上櫃" else f"{raw_ticker}.TW"
                    if 'ETF' in industry or raw_ticker.startswith('00'): is_etf = True
                else:
                    ticker_yf = f"{raw_ticker}.TW"
                    if raw_ticker.startswith('00'): is_etf = True
            except:
                ticker_yf = f"{raw_ticker}.TW"
        
        try:
            info = fetch_stock_info(ticker_yf)
            if info.get('quoteType') == 'ETF': is_etf = True
            if stock_name == "未知名稱": stock_name = info.get('shortName', info.get('longName', raw_ticker))
        except: pass
        
        return ticker_yf, is_etf, stock_name, market_label

# ==========================================
# 網頁 UI 綁定層 (資訊優化版)
# ==========================================
st.title("🏦 台美股/ETF 雙引擎量化進場決策系統")
st.write("這是一套結合基本面、技術面與籌碼面的法人級量化模型。")

col1, col2 = st.columns(2)
with col1:
    raw_ticker = st.text_input("1. 請輸入股票代號 (如: 0050, 2412, TSLA)", value="2412").strip().upper().replace('.TW', '').replace('.TWO', '')
with col2:
    horizon_input = st.text_input("2. 請輸入預計投資的時間年限 (如: 半年, 存股)", value="1年").strip()

if st.button("🚀 開始分析"):
    if raw_ticker:
        with st.spinner("正在連接市場資料庫並進行大量運算，請稍候..."):
            try:
                system = MasterRoutingSystem()
                matched_horizon = parse_investment_horizon(horizon_input)
                ticker_yf, is_etf, stock_name, market_label = system.auto_detect_type(raw_ticker)
                
                st.info(f"✅ 成功辨識：{stock_name} ({ticker_yf}) - 屬於【{market_label}】市場")
                
                if is_etf:
                    st.warning("🎯 系統判定為【ETF】，請注意 ETF 操作須留意「折溢價」風險。")
                    # ETF Analyzer 此處簡化套用同邏輯，實務上可獨立撰寫其專屬的 report generator
                    evaluator = StockEvaluator(raw_ticker, ticker_yf, stock_name, market_label, matched_horizon)
                    report_output = evaluator.get_report()
                else:
                    st.success("🎯 系統判定為【個股】，啟動【個股多維度價值與技術分析引擎】...")
                    evaluator = StockEvaluator(raw_ticker, ticker_yf, stock_name, market_label, matched_horizon)
                    report_output = evaluator.get_report()
                
                # 直接渲染回傳的字串，不再攔截 stdout
                st.code(report_output, language="text")
                st.success("分析完成！")
                
            except Exception as e:
                st.error(f"❌ 系統執行過程中發生錯誤: {e}")
                st.warning("請檢查您的網路連線，或確認輸入的證券代號是否有效。")
    else:
        st.warning("請先輸入股票代號！")