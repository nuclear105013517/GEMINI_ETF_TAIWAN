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
# 介面設定與 iOS CSS 
# ==========================================
st.set_page_config(page_title="台美股/ETF 量化決策系統", layout="wide", initial_sidebar_state="collapsed")

ios_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", sans-serif !important;
        letter-spacing: -0.015em;
    }

    .ios-large-title { font-size: 34px; font-weight: 800; margin-bottom: 4px; color: var(--text-color); letter-spacing: -0.03em; }
    .ios-sub-title { font-size: 16px; font-weight: 500; color: #8E8E93; margin-bottom: 32px; }

    .stTextInput>div>div>input { 
        background-color: var(--secondary-background-color) !important; 
        color: var(--text-color) !important; 
        border: none !important; border-radius: 14px !important;
        padding: 14px 16px !important; font-size: 16px !important;
        font-weight: 500 !important;
    }
    .stTextInput>div>div>input:focus { box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.3) !important; }

    .stButton>button {
        background-color: #007AFF !important; color: #FFFFFF !important;
        border: none !important; border-radius: 14px !important;
        padding: 12px 24px !important; font-weight: 600 !important; font-size: 17px !important;
        transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1) !important; width: 100%;
    }
    .stButton>button:hover { opacity: 0.85; transform: scale(0.98); }
    .stButton>button:active { transform: scale(0.95); }

    .ios-card {
        background-color: var(--secondary-background-color);
        border-radius: 22px; padding: 22px; margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.04);
        border: 1px solid rgba(150,150,150,0.1);
        display: flex; flex-direction: column; height: 100%;
    }
    .ios-card-header { display: flex; align-items: center; margin-bottom: 12px; gap: 8px; }
    .ios-icon {
        font-size: 18px; width: 32px; height: 32px;
        background: rgba(150,150,150,0.1); border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
    }
    .ios-card-title { font-size: 14px; font-weight: 600; color: #8E8E93; text-transform: uppercase; letter-spacing: 0.5px; }
    .ios-card-value { font-size: 34px; font-weight: 700; color: var(--text-color); margin-bottom: 4px; letter-spacing: -0.04em; }
    .ios-card-value-small { font-size: 22px; font-weight: 700; color: var(--text-color); margin-bottom: 4px; letter-spacing: -0.02em; }
    .ios-card-footer { font-size: 13px; color: #8E8E93; margin-top: auto; padding-top: 16px; font-weight: 500; }
    .ios-card-content { margin-top: 8px; }

    .ios-list {
        background: rgba(150,150,150,0.05); border-radius: 14px;
        padding: 0; margin: 12px 0 0 0; list-style: none; overflow: hidden;
    }
    .ios-list-item {
        padding: 12px 16px; border-bottom: 0.5px solid rgba(150,150,150,0.15);
        display: flex; flex-direction: column; gap: 8px;
    }
    .ios-list-item:last-child { border-bottom: none; }
    .ios-list-text { font-size: 15px; font-weight: 500; color: var(--text-color); line-height: 1.4; opacity: 0.9; }

    .ios-badge { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 20px; width: fit-content; }
    .badge-green { background: rgba(52, 199, 89, 0.15); color: #34C759; }
    .badge-red { background: rgba(255, 59, 48, 0.15); color: #FF3B30; }
    .badge-gray { background: rgba(142, 142, 147, 0.15); color: #8E8E93; }
    .badge-orange { background: rgba(255, 149, 0, 0.15); color: #FF9500; }
    .badge-blue { background: rgba(0, 122, 255, 0.15); color: #007AFF; }
    .badge-purple { background: rgba(175, 82, 222, 0.15); color: #AF52DE; }
    
    .ios-strategy-desc { font-size: 16px; font-weight: 500; line-height: 1.5; color: var(--text-color); opacity: 0.9; margin-top: 8px; }
</style>
"""
st.markdown(ios_css, unsafe_allow_html=True)

# ==========================================
# 工具函數區
# ==========================================
def format_list_item(item, force_blue=False):
    item = str(item).replace('⚠️', '').strip()
    match = re.match(r'\[(.*?)\](.*)', item)
    if match:
        tag = match.group(1).strip()
        content = match.group(2).strip()
        if force_blue: badge_class = "badge-blue"
        elif '回測' in tag: badge_class = "badge-purple"
        elif '+' in tag or '強烈' in content or '多頭' in content: badge_class = "badge-green"
        elif '-' in tag or '空頭' in content or '風險' in content or '跌' in content: badge_class = "badge-red"
        elif '0' in tag: badge_class = "badge-gray"
        elif '警告' in tag or '注意' in content or '壓力' in content: badge_class = "badge-orange"
        else: badge_class = "badge-blue"
        return f"<li class='ios-list-item'><div class='ios-badge {badge_class}'>{tag}</div><div class='ios-list-text'>{content}</div></li>"
    else:
        return f"<li class='ios-list-item'><div class='ios-list-text'>{item}</div></li>"

def create_card(title, value, custom_html="", list_items=None, use_small_value=False, icon="📊", footer="", force_blue_badge=False):
    val_class = "ios-card-value-small" if use_small_value else "ios-card-value"
    html_parts = [
        '<div class="ios-card">',
        f'<div class="ios-card-header"><div class="ios-icon">{icon}</div><div class="ios-card-title">{title}</div></div>',
        f'<div class="{val_class}">{value}</div>'
    ]
    if list_items:
        items_str = "".join([format_list_item(item, force_blue_badge) for item in list_items])
        html_parts.append(f"<ul class='ios-list'>{items_str}</ul>")
    if custom_html: html_parts.append(f'<div class="ios-card-content">{custom_html}</div>')
    if footer: html_parts.append(f'<div class="ios-card-footer">{footer}</div>')
    html_parts.append('</div>')
    return "".join(html_parts)

def parse_investment_horizon(text):
    text = text.replace(" ", "")
    if any(k in text for k in ["存股", "長期", "不賣", "退休"]): return "5年以上"
    if any(k in text for k in ["當沖", "日內", "Tick", "隔日沖", "極短線"]): return "1天"

    replace_map = {"一": "1", "兩": "2", "二": "2", "三": "3", "四": "4", "五": "5"}
    for k, v in replace_map.items(): text = text.replace(k, v)
    if text == "十年": text = "10年"

    if "天" in text or "日" in text:
        match = re.search(r'(\d+)\s*[天日]', text)
        if match:
            days = int(match.group(1))
            if days <= 1: return "1天"
            elif days <= 5: return "1-5天"
            elif days <= 20: return "1個月內"
        return "1-5天"

    if "周" in text or "週" in text:
        match = re.search(r'(\d+)\s*[周週]', text)
        if match:
            weeks = int(match.group(1))
            if weeks <= 1: return "1-5天"
            elif weeks <= 4: return "1個月內"
            else: return "1-3個月"
        return "1個月內"

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
            if months <= 1: return "1個月內"
            elif months <= 3: return "1-3個月"
            elif months <= 6: return "3-6個月"
            elif months <= 12: return "1年"
            elif months <= 36: return "1-3年"
            else: return "3-5年"
        return "3-6個月"

    return "1年"

def get_horizon_years(horizon_str):
    mapping = {"1天": 0.003, "1-5天": 0.01, "1個月內": 0.08, "1-3個月": 0.25, "3-6個月": 0.5, "1年": 1.0, "1-3年": 2.0, "3-5年": 4.0, "5年以上": 5.0}
    return mapping.get(horizon_str, 1.0)

# ==========================================
# 歷史回測引擎核心 (依投資時長動態匹配特徵)
# ==========================================
def run_historical_backtest(df, horizon_str, is_weekly_data=False):
    bar_mapping_daily = {"1天": 1, "1-5天": 3, "1個月內": 20, "1-3個月": 40, "3-6個月": 90, "1年": 252, "1-3年": 504, "3-5年": 756, "5年以上": 1260}
    bar_mapping_weekly = {"1年": 52, "1-3年": 104, "3-5年": 156, "5年以上": 260}
    
    forward_bars = bar_mapping_weekly.get(horizon_str, 52) if is_weekly_data else bar_mapping_daily.get(horizon_str, 20)
    
    backtest_df = df.copy()
    
    # 專家修正：嚴格的欄位防呆檢查，確保系統不中斷
    if not all(col in backtest_df.columns for col in ['MA20', 'MA60', 'RSI_14']):
        return None, 0

    backtest_df['Forward_Return'] = backtest_df['Close'].shift(-forward_bars) - backtest_df['Close']
    backtest_df['Is_Win'] = backtest_df['Forward_Return'] > 0
    
    if len(backtest_df) < forward_bars + 30:
        return None, 0
        
    latest = backtest_df.iloc[-1]
    is_long_term = get_horizon_years(horizon_str) >= 1.0
    
    if is_long_term:
        # 長線回測：重視長期均線位階與宏觀趨勢
        if 'MA200' in backtest_df.columns and not pd.isna(latest['MA200']):
            current_trend_up = latest['Close'] > latest['MA200']
            cond_trend = backtest_df['Close'] > backtest_df['MA200'] if current_trend_up else backtest_df['Close'] <= backtest_df['MA200']
        else:
            current_trend_up = latest['Close'] > latest['MA60']
            cond_trend = backtest_df['Close'] > backtest_df['MA60'] if current_trend_up else backtest_df['Close'] <= backtest_df['MA60']
        similar_df = backtest_df[cond_trend].dropna(subset=['Is_Win'])
    else:
        # 短線回測：依賴動能指標 MA20 與 RSI
        current_trend_up = latest['Close'] > latest['MA20']
        cond_trend = backtest_df['Close'] > backtest_df['MA20'] if current_trend_up else backtest_df['Close'] <= backtest_df['MA20']
        
        current_rsi = latest['RSI_14']
        if pd.isna(current_rsi): return None, 0

        if current_rsi < 40: cond_rsi = backtest_df['RSI_14'] < 40
        elif current_rsi > 60: cond_rsi = backtest_df['RSI_14'] > 60
        else: cond_rsi = (backtest_df['RSI_14'] >= 40) & (backtest_df['RSI_14'] <= 60)
        
        similar_df = backtest_df[cond_trend & cond_rsi].dropna(subset=['Is_Win'])
        
    sample_size = len(similar_df)
    if sample_size >= 8:
        win_rate = (similar_df['Is_Win'].sum() / sample_size) * 100
        return win_rate, sample_size
    else:
        return None, sample_size

# ==========================================
# ETF 評估器 (長短線邏輯動態分離)
# ==========================================
class ETFAnalyzer:
    def __init__(self, raw_ticker, ticker_yf, etf_name, user_years, horizon_str):
        self.raw_ticker, self.ticker_yf = raw_ticker, ticker_yf
        self.is_tw_stock = ticker_yf.endswith('.TW') or ticker_yf.endswith('.TWO')
        self.etf_name, self.user_years, self.horizon_str = etf_name, user_years, horizon_str
        self.data, self.score, self.evaluation_details, self.institutional_data = None, 50, [], None
        
        self.is_weekly = user_years > 3.0
        self.interval = "1wk" if self.is_weekly else "1d"
        self.period = "max"

    def fetch_data(self):
        etf = yf.Ticker(self.ticker_yf)
        self.data = etf.history(period=self.period, interval=self.interval, auto_adjust=True)
        if self.data is None or self.data.empty:
            if self.ticker_yf.endswith('.TW'):
                self.ticker_yf = self.ticker_yf.replace('.TW', '.TWO')
                etf = yf.Ticker(self.ticker_yf)
                self.data = etf.history(period=self.period, interval=self.interval, auto_adjust=True)
        if self.data is None or len(self.data) < 20: 
            raise ValueError(f"無法獲取 {self.ticker_yf} 足夠資料。")

    def fetch_institutional_data(self):
        if not self.is_tw_stock or self.is_weekly: return
        pure_ticker, headers = self.raw_ticker, {'User-Agent': 'Mozilla/5.0'}
        def to_shares(val):
            try: return int(str(val).replace(',', '').replace(' ', ''))
            except: return 0
        for days_back in range(5):
            target_date = self.data.index[-1]
            if target_date.tz is not None: target_date = target_date.tz_localize(None)
            target_date -= timedelta(days=days_back)
            try:
                if self.ticker_yf.endswith('.TW'):
                    date_str = target_date.strftime("%Y%m%d")
                    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
                    res = requests.get(url, headers=headers, timeout=5).json()
                    if res.get('stat') == 'OK' and 'data' in res:
                        fields = res['fields']
                        idx_id = fields.index("證券代號") if "證券代號" in fields else 0
                        idx_f = next((i for i, f in enumerate(fields) if "外" in f and "買賣超" in f), 4)
                        idx_s = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), 10)
                        idx_d = next((i for i, f in enumerate(fields) if "自營商" in f and "買賣超" in f), 11)
                        for row in res['data']:
                            if row[idx_id].strip().replace('"', '') == pure_ticker:
                                self.institutional_data = {'foreign': to_shares(row[idx_f]), 'sitc': to_shares(row[idx_s]), 'dealer': to_shares(row[idx_d]), 'date': date_str}
                                return
            except: continue

    def calculate_indicators(self):
        df = self.data
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df['BIAS_20'] = ((df['Close'] - df['MA20']) / df['MA20']) * 100
        
        delta = df['Close'].diff()
        avg_gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        df['RSI_14'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
        
        low_9, high_9 = df['Low'].rolling(window=9).min(), df['High'].rolling(window=9).max()
        price_diff = (high_9 - low_9).replace(0, np.nan) 
        df['RSV'] = ((df['Close'] - low_9) / price_diff) * 100
        df['RSV'] = df['RSV'].fillna(50)
        df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['Volume_5MA'] = df['Volume'].rolling(window=5).mean()

    def analyze_score(self):
        if len(self.data) < 2: return
        latest, prev = self.data.iloc[-1], self.data.iloc[-2]
        is_long_term = self.user_years >= 1.0
        
        self.evaluation_details.append("[注意] 本分析採用『還原總報酬權值』，歷史股息已自動回填。")
        self.evaluation_details.append("[警告] 最終獲利受『折溢價率』影響極大，下單前請確認即時折溢價。")

        if self.institutional_data:
            total_net = (self.institutional_data['foreign'] + self.institutional_data['sitc'] + self.institutional_data['dealer']) / 1000
            if total_net > 500: self.score += 10; self.evaluation_details.append(f"[+10分] 法人單日買超 {total_net:,.0f} 張")
            elif total_net < -500: self.score -= 10; self.evaluation_details.append(f"[-10分] 法人單日賣超 {abs(total_net):,.0f} 張")

        if is_long_term:
            self.evaluation_details.append("[策略] 投資時長大於1年，屏蔽 KD/RSI 等短線震盪雜訊，著重均線護城河位階。")
            if pd.notna(latest['MA200']):
                if latest['Close'] > latest['MA200']:
                    self.score += 20; self.evaluation_details.append("[+20分] 價格站穩年線(200MA)之上，長線牛市結構確認。")
                else:
                    self.score -= 10; self.evaluation_details.append("[-10分] 價格跌破年線，長線趨勢轉弱，建議定期定額攤平。")
            
            bias60 = ((latest['Close'] - latest['MA60']) / latest['MA60']) * 100
            if pd.notna(bias60):
                if bias60 < -10: self.score += 15; self.evaluation_details.append(f"[+15分] 季線乖離率 {bias60:.2f}%，長線超跌買點浮現。")
                elif bias60 > 10: self.score -= 15; self.evaluation_details.append(f"[-15分] 季線乖離率 {bias60:.2f}%，長線溢價偏高。")
        else:
            bias = latest['BIAS_20']
            if pd.notna(bias):
                if bias < -5: self.score += 10; self.evaluation_details.append(f"[+10分] 20均線乖離 {bias:.2f}%，處低檔超跌。")
                elif bias > 5: self.score -= 10; self.evaluation_details.append(f"[-10分] 20均線乖離 {bias:.2f}%，偏離過高。")
                
            rsi, k, d = latest['RSI_14'], latest['K'], latest['D']
            if pd.notna(rsi):
                if rsi < 30: self.score += 15; self.evaluation_details.append(f"[+15分] RSI進入超賣區 ({rsi:.1f})。")
                elif rsi > 70: self.score -= 15; self.evaluation_details.append(f"[-15分] RSI進入超買區 ({rsi:.1f})。")
                
            if pd.notna(k) and pd.notna(d):
                if k < 30 and k > d and prev['K'] <= prev['D']: self.score += 15; self.evaluation_details.append("[+15分] KD低檔黃金交叉。")
                elif k > 80 and k < d and prev['K'] >= prev['D']: self.score -= 15; self.evaluation_details.append("[-15分] KD高檔死亡交叉。")
        
        self.score = max(0, min(self.score, 100))

    def get_time_based_advice(self, term_type):
        s = self.score
        if term_type in ["1天", "1-5天", "1個月內"]:
            if s >= 70: return "建議短多進場 (上漲動能較高)"
            elif s >= 45: return "中性觀望 (無明顯短線動能)"
            else: return "建議避開 (極短線具下殺風險)"
        elif term_type in ["1-3個月", "3-6個月"]:
            if s >= 65: return "強烈建議進場 (波段買點浮現)"
            elif s >= 50: return "建議分批進場 (波段趨勢尚可)"
            else: return "建議觀望 (波段仍有下探風險)"
        else:
            if s >= 65: return "強烈建議單筆大額投入 (長線位階相對便宜)"
            else: return "建議持續定期定額 (紀律投資抗波動)"

    def get_report_data(self):
        latest = self.data.iloc[-1]
        all_horizons = [f"[{term}] {self.get_time_based_advice(term)}" for term in ["1天", "1個月內", "3-6個月", "1年", "5年以上"]]
        
        win_rate, sample_size = run_historical_backtest(self.data, self.horizon_str, self.is_weekly)
        if win_rate is not None:
            win_rate_str, win_rate_footer = f"{win_rate:.1f}%", f"基於 {sample_size} 次相似歷史情境之總報酬回測"
        else:
            win_rate_str, win_rate_footer = "樣本不足", "歷史相似數據庫不足，無法計算可靠勝率"

        return {
            "type": "ETF", "name": self.etf_name, "ticker": self.ticker_yf,
            "price": latest['Close'], "latest_time": latest.name.strftime("%Y/%m/%d"),
            "score": self.score, "matched_tier": self.horizon_str,
            "advice": self.get_time_based_advice(self.horizon_str),
            "details": self.evaluation_details, "all_horizons": all_horizons,
            "win_rate": win_rate_str, "win_rate_footer": win_rate_footer, "is_weekly": self.is_weekly,
            "support": latest['Close'] * 0.98, "resistance": latest['Close'] * 1.02
        }

# ==========================================
# 股票評估器 (進階基本面與技術面修正)
# ==========================================
class StockEvaluator:
    def __init__(self, raw_ticker, ticker_yf, stock_name, market_label, matched_horizon_str, fm):
        self.raw_ticker, self.ticker = raw_ticker, ticker_yf
        self.stock_name, self.market_label = stock_name, market_label
        self.matched_horizon, self.user_horizon_text = matched_horizon_str, matched_horizon_str
        self.fm, self.stock, self.df, self.info = fm, yf.Ticker(self.ticker), pd.DataFrame(), {}
        self.is_us_stock = market_label == "美股/全球"
        
        self.user_years = get_horizon_years(matched_horizon_str)
        self.is_weekly = self.user_years > 3.0
        self.interval = "1wk" if self.is_weekly else "1d"
        self.period = "max"
        
        base_horizons = {
            "1天": {"fund": 0.0, "tech": 0.8, "chip": 0.2, "desc": "預測次日漲跌，極度依賴短線動能。"},
            "1-5天": {"fund": 0.0, "tech": 0.7, "chip": 0.3, "desc": "極短線/隔日預測，看重技術型態與籌碼突擊"},
            "1個月內": {"fund": 0.1, "tech": 0.6, "chip": 0.3, "desc": "短線波段，技術面與籌碼面為主"},
            "1-3個月": {"fund": 0.2, "tech": 0.5, "chip": 0.3, "desc": "短中線，依賴技術型態與基本面發酵"},
            "3-6個月": {"fund": 0.3, "tech": 0.4, "chip": 0.3, "desc": "短中線重視技術與大戶流向"},
            "1年": {"fund": 0.5, "tech": 0.4, "chip": 0.1, "desc": "中線需基本面支撐，搭配技術多頭"},
            "1-3年": {"fund": 0.7, "tech": 0.2, "chip": 0.1, "desc": "中長線看重動態估值(PEG)，技術面抓低點"},
            "3-5年": {"fund": 0.85, "tech": 0.15, "chip": 0.0, "desc": "長線高度看重 ROE、盈餘動態成長力與護城河"},
            "5年以上": {"fund": 0.95, "tech": 0.05, "chip": 0.0, "desc": "極長線複利思維，完全取決於財務內在價值趨勢"}
        }
        
        self.horizons = {}
        for k, v in base_horizons.items():
            if self.is_us_stock and v['chip'] > 0:
                total_ft = v['fund'] + v['tech']
                new_fund = v['fund'] + (v['chip'] * (v['fund'] / total_ft))
                new_tech = v['tech'] + (v['chip'] * (v['tech'] / total_ft))
                self.horizons[k] = {"fund": new_fund, "tech": new_tech, "chip": 0.0, "desc": v['desc'] + " (美股免計籌碼權重)"}
            else:
                self.horizons[k] = v

    def fetch_data(self):
        self.df = self.stock.history(period=self.period, interval=self.interval, auto_adjust=True)
        try: self.info = self.stock.info or {}
        except: self.info = {}
        if self.df.empty: raise ValueError(f"無法獲取股價數據。")

    def calculate_indicators(self):
        self.df['MA20'], self.df['MA60'] = self.df['Close'].rolling(20).mean(), self.df['Close'].rolling(60).mean()
        self.df['MA200'] = self.df['Close'].rolling(200).mean() # 加入年線
        
        # 專家修正：加回短線動能必備的 RSI 運算，以利於歷史引擎調取
        delta = self.df['Close'].diff()
        avg_gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        avg_loss = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        self.df['RSI_14'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
        
        low_min, high_max = self.df['Low'].rolling(9).min(), self.df['High'].rolling(9).max()
        price_diff = (high_max - low_min).replace(0, np.nan)
        self.df['RSV'] = ((self.df['Close'] - low_min) / price_diff) * 100
        self.df['RSV'] = self.df['RSV'].fillna(50)
        self.df['K'] = self.df['RSV'].ewm(com=2, adjust=False).mean()
        self.df['D'] = self.df['K'].ewm(com=2, adjust=False).mean()
        self.df['Volume_5MA'] = self.df['Volume'].rolling(window=5).mean()

    def analyze_fundamentals(self):
        score, details = 50, []
        pe = self.info.get('trailingPE', self.info.get('forwardPE'))
        pb = self.info.get('priceToBook')
        roe = self.info.get('returnOnEquity')
        yield_pct = self.info.get('dividendYield')
        eps = self.info.get('trailingEps')
        peg = self.info.get('pegRatio') 

        pe_threshold = 28 if self.is_us_stock else 20
        if pe is not None:
            if 0 < pe <= pe_threshold: 
                score += 15
                details.append(f"[+15分] 本益比({pe:.1f}) 處於相對合理區間。")
            elif pe > pe_threshold:
                if peg is not None and 0 < peg <= 1.2:
                    score += 5
                    details.append(f"[+5分] 本益比({pe:.1f}) 雖高，但 PEG ({peg:.1f}) 顯示成長強勁，估值健康。")
                elif roe is not None and roe > 0.2:
                    score += 0
                    details.append(f"[ 0分] 本益比({pe:.1f}) 偏高，但受惠於高 ROE，享有市場溢價。")
                else:
                    score -= 15
                    details.append(f"[-15分] 本益比({pe:.1f}) 偏高溢價，缺乏動態成長率支撐。")
            elif pe <= 0: 
                score -= 15; details.append(f"[-15分] 本益比為負，目前企業處於虧損狀態。")
        else: 
            details.append("[ 0分] 本益比資料未提供")

        if pb is not None:
            pb_threshold = 8.0 if self.is_us_stock else 3.5
            if 0 < pb < pb_threshold: score += 10; details.append(f"[+10分] 股價淨值比({pb:.1f}) 尚屬安全區間。")
            else: score -= 10; details.append(f"[-10分] 股價淨值比({pb:.1f}) 資產溢價偏高。")

        if roe is not None:
            roe_val = roe * 100
            if roe_val > 15: score += 15; details.append(f"[+15分] 高資本回報率 ROE ({roe_val:.1f}%)，具備護城河效益。")
            elif roe_val > 8: score += 5; details.append(f"[+5分] ROE ({roe_val:.1f}%) 表現穩健。")
            else: score -= 15; details.append(f"[-15分] ROE ({roe_val:.1f}%) 偏低，資金效率不佳。")

        if yield_pct is not None:
            yield_val = yield_pct * 100
            if yield_val > 4: score += 10; details.append(f"[+10分] 殖利率({yield_val:.1f}%) > 4%，中長線具備防禦性。")
            else: details.append(f"[ 0分] 殖利率({yield_val:.1f}%) (高成長型企業常態)")

        return max(0, min(score, 100)), details, eps

    def analyze_technicals(self):
        score, details = 50, []
        latest, prev = self.df.iloc[-1], self.df.iloc[-2]
        is_long_term = self.user_years >= 1.0
        
        if self.is_weekly: details.append("[注意] 系統已切換為『週 K 線』進行長線平滑分析。")

        if is_long_term:
            if pd.notna(latest['MA200']):
                if latest['Close'] > latest['MA60'] > latest['MA200']:
                    score += 25; details.append("[+25分] 股價 > 季線 > 年線，長線大多頭排列，續抱。")
                elif latest['Close'] > latest['MA200']:
                    score += 10; details.append("[+10分] 股價穩居年線之上。")
                else:
                    score -= 20; details.append("[-20分] 股價跌破年線，長線空頭成型，逢彈減碼。")
        else:
            if latest['Close'] > latest['MA20'] > latest['MA60']: 
                score += 20; details.append("[+20分] 短期均線呈多頭排列。")
            elif latest['Close'] < latest['MA20'] and latest['Close'] < latest['MA60']:
                score -= 20; details.append("[-20分] 股價跌破月季線，短線空頭顯著。")
            else:
                score -= 5; details.append("[-5分] 均線交織糾結，處於震盪洗盤。")

        if not is_long_term:
            if latest['K'] < 30:
                score += 10; details.append(f"[+10分] KD進入低檔超賣 ({latest['K']:.1f})")
                if latest['K'] > latest['D'] and prev['K'] <= prev['D']: 
                    score += 10; details.append("[+10分] KD低檔出現黃金交叉")
            elif latest['K'] > 80:
                score -= 10; details.append(f"[-10分] KD進入高檔超買 ({latest['K']:.1f})")
                if latest['K'] < latest['D'] and prev['K'] >= prev['D']:
                    score -= 10; details.append("[-10分] KD高檔出現死亡交叉")

        recent_low = self.df['Low'].tail(20).min()
        recent_high = self.df['High'].tail(20).max()
        return max(0, min(score, 100)), details, recent_low, recent_high

    def analyze_chips(self):
        score, details = 50, [] 
        if self.is_us_stock or self.is_weekly:
            details.append("[0分] 系統已自動將籌碼權重平滑轉移至基本面與長線趨勢。")
            return 50, details

        start_date = (datetime.date.today() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        try:
            df_inst = self.fm.taiwan_stock_institutional_investors(stock_id=self.raw_ticker, start_date=start_date)
            if df_inst is not None and not df_inst.empty:
                df_inst['net_buy'] = df_inst['buy'] - df_inst['sell']
                recent_3_days_net = df_inst.groupby('date')['net_buy'].sum().tail(3).sum() / 1000
                if recent_3_days_net > 500: score += 20; details.append(f"[+20分] 法人近3日累計買超 {recent_3_days_net:,.0f} 張")
                elif recent_3_days_net > -100: score += 5; details.append(f"[+5分] 法人近3日維持中立 ({recent_3_days_net:,.0f}張)")
                else: score -= 20; details.append(f"[-20分] 法人近3日集中調節 {abs(recent_3_days_net):,.0f} 張")
            else: details.append("[ 0分] 近期無法人進出數據")
        except: details.append("[ 0分] 籌碼面 API 調取受限")
        return max(0, min(score, 100)), details

    def _get_advice_level(self, total_score):
        if total_score >= 80: return "強烈建議買進 (多維度共振，勝率極高)"
        elif total_score >= 61: return "建議買進 (綜合訊號佔優)"
        elif total_score >= 46: return "中性觀望 (多空力道均衡)"
        elif total_score >= 31: return "不建議買進 (風險大於期望報酬)"
        else: return "強烈避開 / 具備戰略做空條件"

    def get_report_data(self):
        self.fetch_data()
        self.calculate_indicators()
        fund_score, fund_details, eps = self.analyze_fundamentals() 
        tech_score, tech_details, support, resistance = self.analyze_technicals() 
        chip_score, chip_details = self.analyze_chips() 

        user_w = self.horizons[self.matched_horizon]
        weighted_f = fund_score * user_w['fund']
        weighted_t = tech_score * user_w['tech']
        weighted_c = chip_score * user_w['chip']
        
        user_total = weighted_f + weighted_t + weighted_c
        
        all_horizons = []
        for horizon, w in self.horizons.items():
            h_total = (fund_score * w['fund']) + (tech_score * w['tech']) + (chip_score * w['chip'])
            all_horizons.append(f"[{horizon}] {self._get_advice_level(h_total)}")

        latest = self.df.iloc[-1]
        win_rate, sample_size = run_historical_backtest(self.df, self.matched_horizon, self.is_weekly)
        
        if win_rate is not None:
            win_rate_str = f"{win_rate:.1f}%"
            win_rate_footer = f"回測基礎: 基於近 {len(self.df)} 根K線中 {sample_size} 次高度相似技術特徵之總報酬反饋統計"
        else:
            win_rate_str, win_rate_footer = "樣本不足", "無足夠相似歷史環境，不予輸出失真反饋"

        return {
            "type": "Stock", "name": self.stock_name, "ticker": self.ticker,
            "price": latest['Close'], "latest_time": latest.name.strftime("%Y/%m/%d"), "eps": eps,
            "support": support, "resistance": resistance,
            "user_horizon": self.user_horizon_text, "matched_horizon": self.matched_horizon,
            "user_total": user_total, "advice": self._get_advice_level(user_total),
            "strategy": user_w['desc'],
            "weights": {"fund": user_w['fund']*100, "tech": user_w['tech']*100, "chip": user_w['chip']*100},
            "details_fund": fund_details, "details_tech": tech_details, "details_chip": chip_details,
            "all_horizons": all_horizons,
            "win_rate": win_rate_str, "win_rate_footer": win_rate_footer, "is_weekly": self.is_weekly
        }

# ==========================================
# 核心大腦路由與主程式
# ==========================================
class MasterRoutingSystem:
    def __init__(self):
        self.fm = DataLoader()
        self._stock_info_cache = None
        
    def auto_detect_type(self, raw_ticker):
        raw_ticker = raw_ticker.strip().upper()
        is_tw = any(char.isdigit() for char in raw_ticker)
        ticker_yf, is_etf = raw_ticker, False
        stock_name, market_label = "未知標的", "美股/全球"
        
        if is_tw:
            try:
                if self._stock_info_cache is None: 
                    self._stock_info_cache = self.fm.taiwan_stock_info()
                target = self._stock_info_cache[self._stock_info_cache['stock_id'] == raw_ticker]
                if not target.empty:
                    stock_name = target.iloc[0]['stock_name']
                    industry = str(target.iloc[0].get('industry_category', '')).upper()
                    market_type = str(target.iloc[0].get('type', '')).lower()
                    market_label = "上櫃" if 'tpex' in market_type or 'otc' in market_type else "上市"
                    if 'ETF' in industry or 'EPR' in industry or len(raw_ticker) >= 5: is_etf = True
                    ticker_yf = f"{raw_ticker}.TW"
                else:
                    if len(raw_ticker) >= 5: is_etf = True
                    ticker_yf = f"{raw_ticker}.TW"
            except: ticker_yf = f"{raw_ticker}.TW"
        else:
            if raw_ticker in ["SPY", "VOO", "QQQ", "IWM", "VT", "VTI", "GLD", "TLT", "BND"]:
                is_etf, stock_name = True, f"{raw_ticker} 全球型/主題型 ETF"
            else:
                stock_name = f"{raw_ticker} 國際企業"
        return ticker_yf, is_etf, stock_name, market_label

def main():
    st.markdown('<div class="ios-large-title">台美股/ETF 量化決策系統</div>', unsafe_allow_html=True)
    st.markdown('<div class="ios-sub-title">基於動態權重對齊與還原總報酬歷史回測架構</div>', unsafe_allow_html=True)

    col_input1, col_input2 = st.columns([2, 2])
    with col_input1: user_ticker = st.text_input("輸入股票或 ETF 代號", value="2330", placeholder="例如：2330, 0050, AAPL, QQQ")
    with col_input2: user_horizon_raw = st.text_input("輸入預期投資時長", value="1天", placeholder="例如：當沖、3個月、5年、定期定額")

    if st.button("啟動量化多因子評估"):
        if not user_ticker:
            st.error("請輸入正確的金融資產代號")
            return
            
        with st.spinner("深度調取底層歷史資料、動態基本面與大戶籌碼中..."):
            router = MasterRoutingSystem()
            ticker_yf, is_etf, asset_name, market_label = router.auto_detect_type(user_ticker)
            horizon_str = parse_investment_horizon(user_horizon_raw)
            user_years = get_horizon_years(horizon_str)
            
            try:
                if is_etf:
                    analyzer = ETFAnalyzer(user_ticker, ticker_yf, asset_name, user_years, horizon_str)
                    analyzer.fetch_data()
                    analyzer.fetch_institutional_data()
                    analyzer.calculate_indicators()
                    analyzer.analyze_score()
                    report = analyzer.get_report_data()
                else:
                    evaluator = StockEvaluator(user_ticker, ticker_yf, asset_name, market_label, horizon_str, router.fm)
                    report = evaluator.get_report_data()
                
                col_m1, col_m2 = st.columns([1, 1])
                with col_m1:
                    card_title = f"{report['name']} ({report['ticker']})"
                    card_value = f"{report['price']:.2f}"
                    score_html = f"""
                    <div class='ios-strategy-desc'><b>評估時長：</b>{report.get('matched_horizon', horizon_str)}</div>
                    <div class='ios-strategy-desc'><b>量化綜合評分：</b>{report.get('user_total', report.get('score', 50)):.1f} / 100 分</div>
                    <div class='ios-strategy-desc'><b>核心戰略部署：</b>{report.get('strategy', '多因子量化評估')}</div>
                    """
                    st.markdown(create_card(card_title, card_value, custom_html=score_html, icon="📈", footer=f"最後數據獲取時間: {report['latest_time']}"), unsafe_allow_html=True)
                    st.markdown(create_card("歷史相似技術特徵回測預測勝率", report['win_rate'], icon="🎯", footer=report['win_rate_footer']), unsafe_allow_html=True)
                
                with col_m2:
                    advice_items = [f"[決策反饋] {report['advice']}"]
                    if not is_etf:
                        advice_items.append(f"[關鍵支撐] 近期價格下檔防禦位：{report['support']:.2f}")
                        advice_items.append(f"[關鍵壓力] 近期價格上檔壓力位：{report['resistance']:.2f}")
                    st.markdown(create_card("戰略決策與結果反饋建議", "ACTIONABLE ADVICE", list_items=advice_items, use_small_value=True, icon="⚖️"), unsafe_allow_html=True)
                    st.markdown(create_card("跨時間時長前瞻預測全景", "TIME HORIZONS", list_items=report['all_horizons'], use_small_value=True, icon="⏳", force_blue_badge=True), unsafe_allow_html=True)
                
                st.markdown("<br><h3 style='font-size:20px; font-weight:700;'>💡 多因子底層量化評分診斷清單</h3>", unsafe_allow_html=True)
                
                if report['type'] == "ETF":
                    st.markdown(create_card("ETF 多空結構明細", "Details", list_items=report['details'], use_small_value=True, icon="📋"), unsafe_allow_html=True)
                else:
                    col_d1, col_d2, col_d3 = st.columns([1, 1, 1])
                    with col_d1: st.markdown(create_card("動態財務與基本面估值", f"{report['weights']['fund']:.0f}% 權重", list_items=report['details_fund'], use_small_value=True, icon="🏢"), unsafe_allow_html=True)
                    with col_d2: st.markdown(create_card("多頭排布與技術面指標", f"{report['weights']['tech']:.0f}% 權重", list_items=report['details_tech'], use_small_value=True, icon="📊"), unsafe_allow_html=True)
                    with col_d3: st.markdown(create_card("主力結構與大戶籌碼面", f"{report['weights']['chip']:.0f}% 權重", list_items=report['details_chip'], use_small_value=True, icon="👥"), unsafe_allow_html=True)
                        
            except Exception as e:
                st.error(f"量化引擎核心發生金融資料調取中斷錯誤: {str(e)}")

if __name__ == "__main__":
    main()