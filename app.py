import streamlit as st
import requests
import pandas as pd
import io

# --- 页面配置 ---
st.set_page_config(page_title="小红书AI (V23 最终智能版)", page_icon="🍒", layout="wide")

# 强制官方地址
BASE_URL = "https://generativelanguage.googleapis.com"

# --- 核心：自动挑选“会说话”的模型 ---
def get_best_model(api_key):
    # 1. 问 Google：我有那些模型？
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None, f"获取模型失败: {resp.status_code}"
            
        data = resp.json()
        models = data.get('models', [])
        
        # 2. 筛选：只找支持 'generateContent' 的模型
        chat_models = []
        for m in models:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                name = m['name'].replace('models/', '')
                chat_models.append(name)
        
        if not chat_models:
            return None, "您的 Key 有效，但没找到支持对话的模型。"
            
        # 3. 优选：优先找 flash 或 pro，找不到就用第一个
        best_model = chat_models[0] # 默认第一个
        for m in chat_models:
            if "flash" in m: 
                best_model = m; break
            elif "pro" in m and "vision" not in m: # 避开纯视觉模型
                best_model = m
                
        return best_model, None

    except Exception as e:
        return None, f"网络错误: {e}"

# --- AI 调用 ---
def call_gemini(prompt, api_key, model_name):
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return True, response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return False, f"API报错: {response.text}"
    except Exception as e:
        return False, f"网络错误: {e}"

# --- 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V23.0 智能过滤版 | 已解决 embedding 模型报错问题")

# 初始化 Session State
if 'working_model' not in st.session_state:
    st.session_state.working_model = None

with st.sidebar:
    st.header("🔑 设置")
    api_key = st.text_input("输入 API Key", type="password")
    
    # 自动初始化模型
    if api_key and not st.session_state.working_model:
        model, err = get_best_model(api_key)
        if model:
            st.session_state.working_model = model
            st.success(f"✅ 已锁定模型: {model}")
        else:
            if err: st.error(err)
    
    # 如果已经锁定了模型，显示出来
    if st.session_state.working_model:
        st.info(f"当前使用: {st.session_state.working_model}")

    uploaded_file = st.file_uploader("📂 上传 Excel", type=['xlsx', 'csv'])

# 主工作区
col1, col2 = st.columns([1, 2])
with col1:
    txt = st.text_area("文案输入", height=300)
    
    can_run = api_key and st.session_state.working_model
    
    if st.button("✨ 开始执行", type="primary", use_container_width=True, disabled=not can_run):
        if not txt and not uploaded_file: st.warning("请输入内容"); st.stop()
        
        tasks = []
        if txt: tasks.extend([t.strip() for t in txt.split('\n\n') if len(t.strip())>5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:,0].dropna().astype(str).tolist())
            except: pass
            
        bar = st.progress(0); log = st.empty(); res = []
        model_used = st.session_state.working_model
        
        for i, t in enumerate(tasks):
            log.text(f"处理第 {i+1} 条...")
            
            # 1. 分析
            p1 = f"分析文案:'{t[:500]}'.提取:原标题|||人设|||选题|||公式"
            ok, r1 = call_gemini(p1, api_key, model_used)
            item = {"原文": t[:15], "结果": ""}
            
            if ok and "|||" in r1:
                parts = r1.split("|||")
                if len(parts)>=4:
                    # 2. 生成
                    p2 = f"我是{parts[1]},写5个关于{parts[2]}的标题"
                    ok2, r2 = call_gemini(p2, api_key, model_used)
                    item["结果"] = r2 if ok2 else r2
                else: item["结果"] = r1
            else: item["结果"] = r1
            
            res.append(item)
            bar.progress((i+1)/len(tasks))
            
        st.session_state.results = res
        log.success("完成！")

with col2:
    if 'results' in st.session_state and st.session_state.results:
        st.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)
