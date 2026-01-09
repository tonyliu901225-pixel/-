import streamlit as st
import requests
import pandas as pd
import io
import time

st.set_page_config(page_title="小红书AI (V18 动态适配版)", page_icon="🍒", layout="wide")

# 强制官方地址
BASE_URL = "https://generativelanguage.googleapis.com"

# --- 1. 获取您的 Key 到底支持哪些模型 ---
def fetch_models(api_key):
    # 这一步是为了解决 404 问题：不瞎猜，直接问官方
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 提取所有支持 generateContent 的模型
            valid_models = []
            if 'models' in data:
                for m in data['models']:
                    if 'generateContent' in m.get('supportedGenerationMethods', []):
                        # 获取纯净的模型名，如 "gemini-1.5-flash"
                        name = m['name'].replace('models/', '')
                        valid_models.append(name)
            return True, valid_models
        else:
            return False, [f"获取失败: {response.status_code} - {response.text}"]
    except Exception as e:
        return False, [f"网络错误: {e}"]

# --- 2. 调用 AI ---
def call_gemini_dynamic(prompt, api_key, model_name):
    # 使用用户选中的、真实存在的模型名
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            if 'candidates' in res_json:
                return True, res_json['candidates'][0]['content']['parts'][0]['text']
            return False, "AI生成了空内容"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

# --- 3. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("输入 API Key", type="password").strip() # 自动去除空格
    
    selected_model = None
    
    if api_key:
        st.markdown("---")
        st.write("🔄 **正在读取您的可用模型...**")
        success, models = fetch_models(api_key)
        
        if success and models:
            st.success("✅ 读取成功！")
            # 让用户选择一个 Google 确认存在的模型
            # 优先默认选中 flash 或 pro
            default_idx = 0
            for i, m in enumerate(models):
                if "flash" in m: default_idx = i; break
            
            selected_model = st.selectbox("请选择一个模型 (推荐 1.5-flash)", models, index=default_idx)
            st.info(f"当前锁定模型: {selected_model}")
        else:
            st.error("❌ 无法获取模型列表")
            st.code(models[0])
            st.warning("如果这里报错，说明 Key 可能还是有权限问题 (IP限制/服务未开通)")

    uploaded_file = st.file_uploader("📂 上传 Excel", type=['xlsx', 'csv'])

# --- 4. 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V18.0 动态适配版 | 专治 404")

if 'results' not in st.session_state: st.session_state.results = []

col1, col2 = st.columns([1, 2])
with col1:
    txt = st.text_area("文案输入", height=300)
    
    # 只有选好了模型才能运行
    can_run = api_key and selected_model
    
    if st.button("✨ 开始执行", type="primary", use_container_width=True, disabled=not can_run):
        if not txt and not uploaded_file: st.warning("请输入内容"); st.stop()
        
        tasks = []
        if txt: tasks.extend([t.strip() for t in txt.split('\n\n') if len(t.strip())>5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:,0].dropna().astype(str).tolist())
            except: pass
            
        bar = st.progress(0); log = st.empty(); tmp = []
        
        for i, t in enumerate(tasks):
            log.text(f"处理中 {i+1}/{len(tasks)}...")
            
            # 1. 分析
            p1 = f"分析文案:'{t[:500]}'.提取:原标题|||人设|||选题|||公式"
            ok, r1 = call_gemini_dynamic(p1, api_key, selected_model)
            
            item = {"原文": t[:20], "状态": "✅" if ok else "❌", "结果": ""}
            
            if ok and "|||" in r1:
                parts = r1.split("|||")
                if len(parts)>=4:
                    # 2. 生成
                    p2 = f"我是{parts[1]},写5个关于{parts[2]}的标题"
                    ok2, r2 = call_gemini_dynamic(p2, api_key, selected_model)
                    item["结果"] = r2 if ok2 else r2
                else: item["结果"] = "格式错: "+r1
            else: item["结果"] = r1
            
            tmp.append(item)
            bar.progress((i+1)/len(tasks))
            
        st.session_state.results = tmp + st.session_state.results
        log.success("完成")

with col2:
    if st.session_state.results:
        st.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)
        if st.button("清空"): st.session_state.results=[]; st.rerun()
