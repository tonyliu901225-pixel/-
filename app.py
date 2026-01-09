import streamlit as st
import google.generativeai as genai
import pandas as pd
import io
import time

# --- 页面配置 ---
st.set_page_config(
    page_title="小红书AI中台 (云端版)",
    page_icon="🍒",
    layout="wide"
)

# --- 侧边栏：配置 ---
with st.sidebar:
    st.header("⚙️ 系统配置")
    
    # 1. API Key 输入
    api_key = st.text_input("请输入 Gemini API Key", type="password")
    
    # 2. 线路选择 (云端其实不需要代理，但保留以防万一)
    st.info("☁️ 代码运行在云端服务器，通常无需中转即可直连 Google。")
    
    st.markdown("---")
    st.markdown("### 📥 批量导入")
    uploaded_file = st.file_uploader("上传 Excel/CSV", type=['xlsx', 'csv'])

# --- 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 Serverless 云端极速版 | 免本地环境 | 免梯子")

# 初始化 Session State
if 'results' not in st.session_state:
    st.session_state.results = []

# --- 核心逻辑 ---
def call_gemini(prompt, key):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# --- 输入区 ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 文本输入")
    txt_input = st.text_area("在此粘贴文案 (支持多篇，按空行分隔)", height=300)
    
    if st.button("✨ 开始 AI 拆解", type="primary", use_container_width=True):
        if not api_key:
            st.error("请先在左侧填入 API Key")
            st.stop()
            
        # 1. 处理文本输入
        tasks = []
        if txt_input:
            tasks.extend([t.strip() for t in txt_input.split('\n\n') if len(t.strip()) > 5])
            
        # 2. 处理文件输入
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                # 假设第一列是文案
                tasks.extend(df.iloc[:, 0].dropna().astype(str).tolist())
            except Exception as e:
                st.error(f"文件读取失败: {e}")

        if not tasks:
            st.warning("请输入文案或上传文件")
            st.stop()

        # 3. 开始处理
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        new_results = []
        
        for i, text in enumerate(tasks):
            status_text.text(f"正在分析第 {i+1}/{len(tasks)} 条...")
            
            # 第一步：拆解
            prompt_analyze = f"""分析文案:"{text[:500]}...".提取4项用|||隔开: 原标题|||人设(销售-老徐/总助-Fiona)|||细分选题|||标题公式|||爆款元素(逗号隔开)"""
            res_analyze = call_gemini(prompt_analyze, api_key)
            
            item = {
                "原文": text[:30]+"...",
                "人设": "未知",
                "选题": "解析失败",
                "公式": "",
                "元素": "",
                "生成标题": ""
            }
            
            if "|||" in res_analyze:
                parts = res_analyze.replace('```', '').strip().split('|||')
                if len(parts) >= 4:
                    item["原文标题"] = parts[0]
                    item["人设"] = parts[1]
                    item["选题"] = parts[2]
                    item["公式"] = parts[3]
                    item["元素"] = parts[4] if len(parts)>4 else ""
                    
                    # 第二步：生成标题
                    prompt_title = f"""你叫{item['人设']},选题"{item['选题']}",公式"{item['公式']}".写5个爆款标题,每行一个,无序号,20字内."""
                    res_title = call_gemini(prompt_title, api_key)
                    item["生成标题"] = res_title
            
            new_results.append(item)
            progress_bar.progress((i + 1) / len(tasks))
            
        st.session_state.results = new_results + st.session_state.results
        status_text.success("🎉 全部处理完成！")

# --- 结果展示区 ---
with col2:
    st.subheader(f"📚 资产库 ({len(st.session_state.results)})")
    
    if st.session_state.results:
        # 1. 转换为 DataFrame 方便展示
        df_res = pd.DataFrame(st.session_state.results)
        st.dataframe(df_res, use_container_width=True)
        
        # 2. 导出按钮
        # 将 DataFrame 转换为 Excel 字节流
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False, sheet_name='Sheet1')
        processed_data = output.getvalue()
        
        st.download_button(
            label="📥 下载 Excel 报表",
            data=processed_data,
            file_name=f"小红书选题_{int(time.time())}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        if st.button("🗑️ 清空列表"):
            st.session_state.results = []
            st.rerun()
            
    else:
        st.info("👈 请在左侧输入文案开始")
        st.markdown("""
        **使用说明：**
        1. 在左侧填入 API Key。
        2. 粘贴文案或上传 Excel。
        3. 点击“开始拆解”，AI 将在云端极速运行。
        """)