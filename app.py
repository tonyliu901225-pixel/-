import streamlit as st
import requests
import pandas as pd
import io
import time

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="小红书AI中台 (V13 官方纯净版)",
    page_icon="🍒",
    layout="wide"
)

# --- 2. 核心 AI 通信函数 (强制官方线路) ---
def call_gemini_official(prompt, api_key):
    # ⚠️ 强制使用 Google 官方地址，不再允许修改，确保 100% 兼容性
    # Streamlit 云端服务器在美国，连接此地址畅通无阻
    base_url = "https://generativelanguage.googleapis.com"
    model = "gemini-1.5-flash"
    
    url = f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        # 发送请求
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # 错误处理
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        
        # 解析结果
        result = response.json()
        if 'candidates' in result and result['candidates']:
            return {"success": True, "text": result['candidates'][0]['content']['parts'][0]['text']}
        else:
            return {"success": False, "error": "AI 返回了空内容 (可能是安全拦截)"}
            
    except Exception as e:
        return {"success": False, "error": f"网络连接错误: {str(e)}"}

# --- 3. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 系统设置")
    api_key = st.text_input("在此输入 API Key", type="password")
    
    st.success("✅ 网络状态：已直连 Google 官方")
    st.info("☁️ 此版本专为 Streamlit Cloud 设计，无需任何代理。")
    
    uploaded_file = st.file_uploader("📂 批量上传 Excel", type=['xlsx', 'csv'])

# --- 4. 主工作台 ---
st.title("🍒 小红书 AI 选题中台")
st.markdown("##### 🚀 V13.0 官方纯净版 | 极速 | 稳定")

# 初始化数据容器
if 'results' not in st.session_state:
    st.session_state.results = []

# 布局
col_input, col_output = st.columns([1, 2])

with col_input:
    input_text = st.text_area("✍️ 在此粘贴文案 (支持多篇，空行分隔)", height=300)
    
    run_btn = st.button("✨ 立即执行 AI 分析", type="primary", use_container_width=True)

    if run_btn:
        if not api_key:
            st.error("❌ 请先在左侧填入 API Key")
            st.stop()
        
        # 准备任务列表
        tasks = []
        if input_text:
            tasks.extend([t.strip() for t in input_text.split('\n\n') if len(t.strip()) > 5])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:, 0].dropna().astype(str).tolist())
            except:
                st.warning("文件读取失败，请检查格式")

        if not tasks:
            st.warning("⚠️ 没有检测到有效文案")
            st.stop()

        # 开始处理
        progress_bar = st.progress(0)
        status_box = st.empty()
        temp_results = []

        for i, text in enumerate(tasks):
            status_box.markdown(f"🔄 **正在处理第 {i+1}/{len(tasks)} 条...**")
            
            # 步骤 1: 深度拆解
            prompt_1 = f"""分析文案:"{text[:800]}".提取4项内容,严格用|||隔开:
            1.原标题
            2.人设(判断是:销售老徐/总助Fiona/其他)
            3.核心选题
            4.爆款公式
            如果不确定，请填“未知”"""
            
            res_1 = call_gemini_official(prompt_1, api_key)
            
            # 构建结果对象
            data_row = {
                "原文片段": text[:20] + "...",
                "状态": "✅ 完成",
                "AI反馈": ""
            }

            if res_1['success']:
                raw = res_1['text'].strip()
                if "|||" in raw:
                    parts = raw.split('|||')
                    if len(parts) >= 4:
                        persona = parts[1].strip()
                        topic = parts[2].strip()
                        formula = parts[3].strip()
                        
                        data_row["人设"] = persona
                        data_row["选题"] = topic
                        data_row["公式"] = formula
                        
                        # 步骤 2: 生成标题
                        prompt_2 = f"""你现在是{persona}，针对选题"{topic}"，利用公式"{formula}"。
                        请写 5 个极具吸引力的小红书标题。
                        要求：口语化、带情绪、无序号、每行一个。"""
                        
                        res_2 = call_gemini_official(prompt_2, api_key)
                        if res_2['success']:
                            data_row["生成的爆款标题"] = res_2['text']
                        else:
                            data_row["生成的爆款标题"] = "标题生成失败"
                    else:
                        data_row["状态"] = "⚠️ 格式解析失败"
                        data_row["AI反馈"] = raw
                else:
                     data_row["状态"] = "⚠️ 格式错误"
                     data_row["AI反馈"] = raw
            else:
                data_row["状态"] = "❌ 请求失败"
                data_row["AI反馈"] = res_1['error']

            temp_results.append(data_row)
            progress_bar.progress((i + 1) / len(tasks))

        # 更新结果
        st.session_state.results = temp_results + st.session_state.results
        status_box.success(f"🎉 全部完成！共处理 {len(tasks)} 条")

with col_output:
    if st.session_state.results:
        st.markdown(f"### 📊 结果列表 ({len(st.session_state.results)})")
        
        # 展示表格
        df_show = pd.DataFrame(st.session_state.results)
        st.dataframe(df_show, use_container_width=True)
        
        # 导出按钮
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_show.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 下载 Excel 报表",
            data=buffer.getvalue(),
            file_name=f"小红书AI分析_{int(time.time())}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        if st.button("🗑️ 清空所有记录"):
            st.session_state.results = []
            st.rerun()
    else:
        st.info("👈 请在左侧输入内容并开始")
