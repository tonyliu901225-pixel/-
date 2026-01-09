import streamlit as st
import requests
import pandas as pd
import io
import time

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="小红书AI中台 (V14 自动巡航版)",
    page_icon="🍒",
    layout="wide"
)

# --- 2. 核心：智能模型回退机制 ---
def call_gemini_smart(prompt, api_key):
    # 定义尝试顺序：新模型 -> 老模型
    # 这样可以确保如果新模型 404，会自动降级使用老模型
    candidate_models = [
        "gemini-1.5-flash", 
        "gemini-1.5-pro", 
        "gemini-pro", 
        "gemini-1.0-pro"
    ]
    
    # 强制官方地址 (Streamlit Cloud 专用)
    base_url = "https://generativelanguage.googleapis.com"
    
    last_error = ""
    
    # 循环尝试每个模型
    for model in candidate_models:
        url = f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        try:
            # 发起请求
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            # 如果成功 (200 OK)
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    return {
                        "success": True, 
                        "text": result['candidates'][0]['content']['parts'][0]['text'],
                        "used_model": model # 告诉用户最终用的是哪个模型
                    }
            
            # 如果是 404 (模型未找到)，记录错误并继续尝试下一个模型
            if response.status_code == 404:
                last_error = f"模型 {model} 报错 404，正在尝试下一个..."
                continue
                
            # 如果是其他错误 (如 400 Key 错误)，直接停止，不再尝试
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
            
        except Exception as e:
            return {"success": False, "error": f"网络错误: {str(e)}"}
            
    # 如果所有模型都试完了还在报错
    return {"success": False, "error": f"所有模型均尝试失败。最后一次报错: {last_error}"}

# --- 3. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 系统设置")
    api_key = st.text_input("输入 API Key", type="password")
    
    st.info("🤖 V14 逻辑：自动检测可用模型，解决 404 问题。")
    uploaded_file = st.file_uploader("📂 上传 Excel", type=['xlsx', 'csv'])

# --- 4. 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V14.0 自动巡航版 | 智能容错")

if 'results' not in st.session_state: st.session_state.results = []

col1, col2 = st.columns([1, 2])

with col1:
    txt_input = st.text_area("在此粘贴文案", height=300)
    if st.button("✨ 开始执行", type="primary", use_container_width=True):
        if not api_key: st.error("请填入 Key"); st.stop()
        
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
            status.markdown(f"🔄 **正在处理第 {i+1}/{len(tasks)} 条...**")
            
            # 1. 分析
            p1 = f"""分析文案:"{text[:500]}...".提取4项用|||隔开: 原标题|||人设(销售-老徐/总助-Fiona)|||细分选题|||标题公式|||爆款元素"""
            r1 = call_gemini_smart(p1, api_key)
            
            item = {"原文": text[:20]+"...", "状态": "✅ 成功", "结果": "", "使用模型": r1.get('used_model', '未知')}
            
            if r1['success']:
                if "|||" in r1['text']:
                    parts = r1['text'].replace('```','').strip().split('|||')
                    if len(parts) >= 4:
                        # 2. 写标题
                        p2 = f"""你叫{parts[1]},选题"{parts[2]}".写5个标题."""
                        r2 = call_gemini_smart(p2, api_key)
                        item["结果"] = r2['text'] if r2['success'] else r2['error']
                    else: item["状态"] = "格式错"; item["结果"] = r1['text']
                else: item["状态"] = "格式错"; item["结果"] = r1['text']
            else: item["状态"] = "❌ 失败"; item["结果"] = r1['error']
            
            new_res.append(item)
            prog.progress((i+1)/len(tasks))
            
        st.session_state.results = new_res + st.session_state.results
        status.success(f"完成！最终使用的模型是: {new_res[0].get('使用模型')}")

with col2:
    if st.session_state.results:
        df = pd.DataFrame(st.session_state.results)
        st.dataframe(df, use_container_width=True)
        if st.button("清空"): st.session_state.results = []; st.rerun()
