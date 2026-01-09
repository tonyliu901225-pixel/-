import streamlit as st
import requests
import pandas as pd
import io

# --- 页面设置 ---
st.set_page_config(page_title="小红书AI (V21 最终版)", page_icon="🍒", layout="wide")

# --- 核心设置 ---
# 既然用了 gen-lang-client 的 Key，必须用官方地址，绝对通！
BASE_URL = "https://generativelanguage.googleapis.com"

def call_gemini(prompt, api_key):
    # 优先使用 Flash 模型，速度快且免费
    url = f"{BASE_URL}/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return True, response.json()['candidates'][0]['content']['parts'][0]['text']
        elif response.status_code == 404:
            return False, "❌ 404错误：请确认您使用的是 'REd book' 项目里申请的 Key！"
        else:
            return False, f"❌ 报错: {response.text}"
    except Exception as e:
        return False, f"❌ 网络错误: {e}"

# --- 界面 ---
st.title("🍒 小红书 AI 选题中台")
st.success("✅ 云端环境已就绪。请填入 'REd book' 项目的 Key。")

with st.sidebar:
    st.header("🔑 关键一步")
    api_key = st.text_input("在此粘贴 Key", type="password")
    uploaded_file = st.file_uploader("上传表格", type=['xlsx', 'csv'])

col1, col2 = st.columns([1, 2])
with col1:
    txt = st.text_area("输入文案", height=300)
    if st.button("✨ 开始执行", type="primary", use_container_width=True):
        if not api_key: st.error("缺 Key"); st.stop()
        
        tasks = []
        if txt: tasks.extend([t.strip() for t in txt.split('\n\n') if len(t.strip())>5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:,0].dropna().astype(str).tolist())
            except: pass
            
        if not tasks: st.warning("没内容"); st.stop()
        
        bar = st.progress(0); st_log = st.empty(); res = []
        for i, t in enumerate(tasks):
            st_log.text(f"处理第 {i+1} 条...")
            # 1. 分析
            ok, r1 = call_gemini(f"分析文案:'{t[:500]}'.提取:原标题|||人设|||选题|||公式", api_key)
            item = {"原文": t[:15], "结果": ""}
            if ok and "|||" in r1:
                p = r1.split("|||")
                if len(p)>=4:
                    # 2. 生成
                    ok2, r2 = call_gemini(f"我是{p[1]},写5个关于{p[2]}的标题", api_key)
                    item["结果"] = r2 if ok2 else r2
                else: item["结果"] = r1
            else: item["结果"] = r1
            res.append(item)
            bar.progress((i+1)/len(tasks))
            
        st.session_state.results = res
        st_log.success("完成！")

with col2:
    if 'results' in st.session_state and st.session_state.results:
        st.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)
