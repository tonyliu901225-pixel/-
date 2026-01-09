import streamlit as st
import requests
import pandas as pd
import io
import socket

# --- 1. 页面配置 ---
st.set_page_config(page_title="小红书AI (V16 验尸官版)", page_icon="🕵️", layout="wide")

# --- 2. 核心诊断工具 ---
def get_system_info():
    try:
        hostname = socket.gethostname()
        # 简单判断环境
        if "localhost" in hostname or "local" in hostname:
            return "🏠 本地环境 (Localhost)", "可能受限 ❌"
        return "☁️ 云端环境 (Streamlit Cloud)", "畅通 ✅"
    except:
        return "未知环境", "未知"

def check_api_key_health(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            names = [m['name'] for m in models]
            return True, f"✅ Key 有效！检测到 {len(models)} 个模型", names
        else:
            return False, f"❌ Key 无效 (HTTP {response.status_code})", [response.text]
    except Exception as e:
        return False, f"❌ 网络连不上 Google ({str(e)})", []

# --- 3. 侧边栏 (诊断区) ---
with st.sidebar:
    st.header("🕵️ 环境与 Key 诊断")
    
    # 1. 环境检测
    env_name, env_status = get_system_info()
    st.info(f"当前位置: {env_name}")
    if "本地" in env_name:
        st.error("⚠️ 警告：您还在本地！请去 share.streamlit.io 打开云端网页！")
    else:
        st.success("✅ 环境正确：已连接美国服务器")

    # 2. Key 检测
    api_key = st.text_input("输入 API Key", type="password")
    
    if api_key:
        if st.button("🏥 给 Key 做个体检"):
            is_valid, msg, details = check_api_key_health(api_key)
            if is_valid:
                st.success(msg)
                with st.expander("查看支持的模型"):
                    st.write(details)
            else:
                st.error(msg)
                st.code(details[0]) # 打印报错详情

    st.markdown("---")
    uploaded_file = st.file_uploader("📂 上传 Excel", type=['xlsx', 'csv'])

# --- 4. 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V16.0 验尸官版 | 专治各种疑难杂症")

# 核心 AI 调用 (最简版)
def call_ai(prompt, key):
    # 强制指定最稳的模型
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    try:
        resp = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]}, headers={'Content-Type': 'application/json'}, timeout=30)
        if resp.status_code == 200:
            return True, resp.json()['candidates'][0]['content']['parts'][0]['text']
        return False, f"API报错 {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"网络报错: {e}"

if 'results' not in st.session_state: st.session_state.results = []

col1, col2 = st.columns([1, 2])
with col1:
    txt = st.text_area("输入文案", height=300)
    if st.button("✨ 开始执行", type="primary", use_container_width=True, disabled=not api_key):
        if not txt and not uploaded_file: st.warning("没内容啊"); st.stop()
        
        # 准备数据
        tasks = []
        if txt: tasks.extend([t.strip() for t in txt.split('\n\n') if len(t.strip())>5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:,0].dropna().astype(str).tolist())
            except: pass
            
        bar = st.progress(0); st_log = st.empty(); temp_res = []
        
        for i, t in enumerate(tasks):
            st_log.text(f"处理中 {i+1}/{len(tasks)}...")
            
            # 1. 分析
            ok, res1 = call_ai(f"分析文案:'{t[:500]}'.提取:原标题|||人设|||选题|||公式", api_key)
            row = {"原文": t[:15], "状态": "✅" if ok else "❌", "结果": ""}
            
            if ok and "|||" in res1:
                # 2. 生成
                p = res1.split("|||")
                if len(p)>=4:
                    ok2, res2 = call_ai(f"我是{p[1]},写5个关于{p[2]}的标题", api_key)
                    row["结果"] = res2 if ok2 else "生成失败"
                else: row["结果"] = "分析格式错"
            else:
                row["结果"] = res1 # 打印错误信息
            
            temp_res.append(row)
            bar.progress((i+1)/len(tasks))
        
        st.session_state.results = temp_res + st.session_state.results
        st_log.success("完成")

with col2:
    if st.session_state.results:
        st.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)
        if st.button("清空"): st.session_state.results=[]; st.rerun()
