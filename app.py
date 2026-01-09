import streamlit as st
import requests
import pandas as pd
import io
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="小红书AI (V19 暴力适配版)", page_icon="🥊", layout="wide")

# 强制官方地址
BASE_URL = "https://generativelanguage.googleapis.com"

# --- 2. 核心：暴力寻找可用模型 ---
def find_working_model(api_key):
    # 备选名单：从最新到最老，挨个试
    candidate_models = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
        "gemini-pro"
    ]
    
    placeholder = st.empty()
    
    for model in candidate_models:
        placeholder.info(f"🥊 正在尝试连接模型: {model} ...")
        
        # 发送一个极简的测试请求
        url = f"{BASE_URL}/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": "Hello"}]}]}
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                placeholder.success(f"✅ 成功锁定模型: {model}")
                time.sleep(1) # 让用户看一眼
                placeholder.empty()
                return model # 找到了！返回模型名
            
            elif response.status_code == 404:
                # 404 说明 Key 不支持这个模型，继续试下一个
                continue
                
            else:
                # 其他错误（如 Key 无效），直接报错停止
                placeholder.error(f"❌ Key 错误: {response.status_code}")
                return None
                
        except Exception as e:
            placeholder.error(f"网络错误: {e}")
            return None
            
    # 如果循环跑完了还没找到
    placeholder.error("❌ 所有模型均尝试失败。请检查您的 API Key 是否已失效。")
    return None

# --- 3. AI 调用函数 ---
def call_gemini_final(prompt, api_key, model_name):
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            res = response.json()
            if 'candidates' in res:
                return True, res['candidates'][0]['content']['parts'][0]['text']
        return False, f"API报错: {response.text}"
    except Exception as e:
        return False, str(e)

# --- 4. 界面逻辑 ---
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("输入 API Key", type="password")
    
    # 自动寻找模型逻辑
    if 'current_model' not in st.session_state:
        st.session_state.current_model = None
        
    if api_key:
        if st.button("🔄 点击自动匹配模型"):
            found_model = find_working_model(api_key)
            if found_model:
                st.session_state.current_model = found_model
                st.rerun() # 刷新页面更新状态
    
    # 显示当前锁定的模型
    if st.session_state.current_model:
        st.success(f"当前使用: {st.session_state.current_model}")
    else:
        st.info("👈 请填入 Key 并点击匹配")

    uploaded_file = st.file_uploader("📂 上传 Excel", type=['xlsx', 'csv'])

# --- 5. 主工作台 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V19.0 暴力适配版 | 自动回退机制")

if 'results' not in st.session_state: st.session_state.results = []

col1, col2 = st.columns([1, 2])
with col1:
    txt = st.text_area("文案输入", height=300)
    
    # 只有找到了模型才能开始
    can_run = api_key and st.session_state.current_model
    
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
        model_used = st.session_state.current_model
        
        for i, t in enumerate(tasks):
            log.text(f"处理中 {i+1}/{len(tasks)} (Model: {model_used})...")
            
            # 1. 分析
            ok, r1 = call_gemini_final(f"分析文案:'{t[:500]}'.提取:原标题|||人设|||选题|||公式", api_key, model_used)
            item = {"原文": t[:20], "状态": "✅" if ok else "❌", "结果": ""}
            
            if ok and "|||" in r1:
                parts = r1.split("|||")
                if len(parts)>=4:
                    # 2. 生成
                    ok2, r2 = call_gemini_final(f"我是{parts[1]},写5个关于{parts[2]}的标题", api_key, model_used)
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
