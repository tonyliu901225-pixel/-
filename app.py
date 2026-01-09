import streamlit as st
import requests
import pandas as pd
import io
import time

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="小红书AI中台 (V15 终极侦探版)",
    page_icon="🍒",
    layout="wide"
)

# 强制官方地址 (Streamlit Cloud 专用)
BASE_URL = "https://generativelanguage.googleapis.com"

# --- 2. 核心功能：侦测可用模型 ---
def get_available_models(api_key):
    if not api_key: return []
    
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 筛选出支持生成内容的模型
            models = []
            if 'models' in data:
                for m in data['models']:
                    if 'generateContent' in m.get('supportedGenerationMethods', []):
                        # 只取模型名字，例如 models/gemini-pro -> gemini-pro
                        m_name = m['name'].replace('models/', '')
                        models.append(m_name)
            return models
        else:
            st.error(f"获取模型列表失败: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        st.error(f"网络连接失败: {str(e)}")
        return []

# --- 3. 核心功能：调用 AI ---
def call_gemini(prompt, api_key, model_name):
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                return {"success": True, "text": result['candidates'][0]['content']['parts'][0]['text']}
            else:
                return {"success": False, "error": "AI返回空内容 (可能被安全拦截)"}
        elif response.status_code == 404:
            return {"success": False, "error": f"模型 {model_name} 不存在 (404)"}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"success": False, "error": f"网络错误: {str(e)}"}

# --- 4. 侧边栏设置 ---
with st.sidebar:
    st.header("⚙️ 系统设置")
    
    # 1. 输入 Key
    api_key = st.text_input("第一步：输入 API Key", type="password")
    
    # 2. 自动获取模型 (核心修复)
    available_models = []
    if api_key:
        if st.button("🔄 点击检测可用模型"):
            available_models = get_available_models(api_key)
            if available_models:
                st.success(f"检测到 {len(available_models)} 个可用模型！")
            else:
                st.error("未检测到任何模型，请检查 Key 是否有效。")
    
    # 如果检测到了，用检测的；没检测到，用默认兜底
    model_options = available_models if available_models else ["gemini-1.5-flash", "gemini-pro", "gemini-1.0-pro"]
    
    selected_model = st.selectbox(
        "第二步：选择模型 (请选列表里的第一个)", 
        model_options
    )
    
    st.info(f"当前使用模型: {selected_model}")
    uploaded_file = st.file_uploader("📂 上传 Excel", type=['xlsx', 'csv'])

# --- 5. 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V15.0 终极侦探版 | 自动适配模型")

if 'results' not in st.session_state: st.session_state.results = []

col1, col2 = st.columns([1, 2])

with col1:
    txt_input = st.text_area("在此粘贴文案", height=300)
    
    # 只有填了 Key 才能点运行
    if st.button("✨ 开始执行", type="primary", use_container_width=True, disabled=not api_key):
        if not txt_input and not uploaded_file:
            st.warning("请输入内容")
            st.stop()
            
        tasks = []
        if txt_input: tasks.extend([t.strip() for t in txt_input.split('\n\n') if len(t.strip()) > 5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:, 0].dropna().astype(str).tolist())
            except: pass

        prog = st.progress(0); status = st.empty(); new_res = []
        
        for i, text in enumerate(tasks):
            status.markdown(f"🔄 **正在处理第 {i+1}/{len(tasks)} 条...**")
            
            # 1. 分析
            p1 = f"""分析文案:"{text[:500]}...".提取4项用|||隔开: 原标题|||人设(销售-老徐/总助-Fiona)|||细分选题|||标题公式|||爆款元素"""
            r1 = call_gemini(p1, api_key, selected_model)
            
            item = {"原文": text[:20]+"...", "状态": "✅ 成功", "结果": ""}
            
            if r1['success']:
                if "|||" in r1['text']:
                    parts = r1['text'].replace('```','').strip().split('|||')
                    if len(parts) >= 4:
                        # 2. 写标题
                        p2 = f"""你叫{parts[1]},选题"{parts[2]}".写5个标题."""
                        r2 = call_gemini(p2, api_key, selected_model)
                        item["结果"] = r2['text'] if r2['success'] else r2['error']
                    else: item["状态"] = "格式错"; item["结果"] = r1['text']
                else: item["状态"] = "格式错"; item["结果"] = r1['text']
            else: item["状态"] = "❌ 失败"; item["结果"] = r1['error']
            
            new_res.append(item)
            prog.progress((i+1)/len(tasks))
            
        st.session_state.results = new_res + st.session_state.results
        status.success("完成！")

with col2:
    if st.session_state.results:
        df = pd.DataFrame(st.session_state.results)
        st.dataframe(df, use_container_width=True)
        if st.button("清空"): st.session_state.results = []; st.rerun()
