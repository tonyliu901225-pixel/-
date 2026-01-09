import streamlit as st
import requests
import pandas as pd
import io
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="小红书AI中台 (V11 全兼容版)", page_icon="🍒", layout="wide")

# --- 2. 核心逻辑 ---
def call_gemini_requests(prompt, api_key, base_url, model_name):
    # 自动处理 URL 格式
    base_url = base_url.rstrip('/')
    # 拼接完整的 API 地址
    url = f"{base_url}/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP报错 {response.status_code}: {response.text[:100]}"}
            
        result = response.json()
        try:
            text = result['candidates'][0]['content']['parts'][0]['text']
            return {"success": True, "text": text}
        except:
            return {"success": False, "error": "AI返回结构异常"}
            
    except Exception as e:
        return {"success": False, "error": f"网络连通性错误: {str(e)[:50]}"}

# --- 3. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 核心设置")
    api_key = st.text_input("1. API Key", type="password")
    
    st.markdown("### 2. 模型与线路")
    # 增加模型选择，解决 404 问题
    model_name = st.selectbox("选择模型 (报错404请换这个)", ["gemini-pro", "gemini-1.5-flash"])
    
    # 增加线路选择，解决网络问题
    line_mode = st.radio("选择线路", ["官方直连 (需云端)", "国内中转 A", "国内中转 B", "自定义"], index=1)
    
    base_urls = {
        "官方直连 (需云端)": "https://generativelanguage.googleapis.com",
        "国内中转 A": "https://cf.aigc.mn",
        "国内中转 B": "https://gemini-api.iyuu.cn"
    }
    
    if line_mode == "自定义":
        current_base_url = st.text_input("输入自定义接口地址", "https://...")
    else:
        current_base_url = base_urls[line_mode]
    
    st.info(f"当前连接：{current_base_url}")
    st.info(f"当前模型：{model_name}")
    
    uploaded_file = st.file_uploader("📂 上传 Excel", type=['xlsx', 'csv'])

# --- 4. 主界面 ---
st.title("🍒 小红书 AI 选题中台 (V11)")
st.caption("🚀 修复 404 错误 | 修复网络连接")

if 'results' not in st.session_state:
    st.session_state.results = []

col1, col2 = st.columns([1, 2])

with col1:
    txt_input = st.text_area("在此粘贴文案", height=300)
    
    if st.button("✨ 开始执行", type="primary", use_container_width=True):
        if not api_key: st.error("缺 API Key"); st.stop()
            
        tasks = []
        if txt_input: tasks.extend([t.strip() for t in txt_input.split('\n\n') if len(t.strip()) > 5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:, 0].dropna().astype(str).tolist())
            except: pass
        
        if not tasks: st.warning("请输入内容"); st.stop()

        prog = st.progress(0); status = st.empty(); new_res = []
        
        for i, text in enumerate(tasks):
            status.text(f"正在处理 {i+1}/{len(tasks)}...")
            
            # 第一步：分析
            p1 = f"""分析文案:"{text[:500]}...".提取4项用|||隔开: 原标题|||人设(销售-老徐/总助-Fiona)|||细分选题|||标题公式|||爆款元素"""
            r1 = call_gemini_requests(p1, api_key, current_base_url, model_name)
            
            item = {"原文": text[:20]+"...", "状态": "✅ 成功", "诊断": ""}
            
            if r1['success']:
                if "|||" in r1['text']:
                    parts = r1['text'].replace('```','').strip().split('|||')
                    if len(parts) >= 4:
                        item.update({"人设":parts[1], "选题":parts[2], "公式":parts[3]})
                        # 第二步：写标题
                        p2 = f"""你叫{parts[1]},选题"{parts[2]}".写5个标题."""
                        r2 = call_gemini_requests(p2, api_key, current_base_url, model_name)
                        item["标题"] = r2['text'] if r2['success'] else f"标题生成失败: {r2['error']}"
                    else:
                        item["状态"] = "⚠️ 格式错"; item["诊断"] = r1['text']
                else:
                    item["状态"] = "⚠️ 格式错"; item["诊断"] = r1['text']
            else:
                item["状态"] = "❌ 失败"; item["诊断"] = r1['error']
            
            new_res.append(item)
            prog.progress((i+1)/len(tasks))
            
        st.session_state.results = new_res + st.session_state.results
        status.success("完成！")

with col2:
    if st.session_state.results:
        df = pd.DataFrame(st.session_state.results)
        st.dataframe(df, column_config={"诊断": st.column_config.TextColumn("错误诊断 (红字必看)", width="large")})
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
        st.download_button("📥 下载结果", out.getvalue(), "res.xlsx")
        if st.button("清空"): st.session_state.results = []; st.rerun()
