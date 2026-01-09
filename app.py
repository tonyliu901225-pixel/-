import streamlit as st
import requests
import pandas as pd
import io
import time

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(
    page_title="小红书 AI 选题中台 (最终完整版)",
    page_icon="🍒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 强制使用 Google 官方 API 地址 (云端专用)
BASE_URL = "https://generativelanguage.googleapis.com"

# ==========================================
# 2. 核心函数
# ==========================================

def get_best_model(api_key):
    """
    智能模型筛选器：
    1. 获取 Key 支持的所有模型
    2. 剔除不支持 'generateContent' 的模型 (如 embedding-gecko)
    3. 优先返回 gemini-1.5-flash，其次是 pro
    """
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None, f"Key 验证失败 ({resp.status_code})"
            
        data = resp.json()
        models = data.get('models', [])
        
        # 筛选出支持对话的模型
        chat_models = []
        for m in models:
            if 'generateContent' in m.get('supportedGenerationMethods', []):
                name = m['name'].replace('models/', '')
                chat_models.append(name)
        
        if not chat_models:
            return None, "未找到支持对话的模型，请检查 Key 权限。"
            
        # 优选逻辑
        best_model = chat_models[0] # 默认兜底
        for m in chat_models:
            if "flash" in m: 
                best_model = m; break
            elif "pro" in m and "vision" not in m:
                best_model = m
                
        return best_model, None

    except Exception as e:
        return None, f"网络连接错误: {e}"

def call_gemini(prompt, api_key, model_name):
    """通用 AI 调用函数"""
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        # 设置 30秒 超时，防止卡死
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return True, response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return False, f"API报错 {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return False, f"网络错误: {str(e)}"

# ==========================================
# 3. 界面逻辑
# ==========================================

# 初始化 Session State
if 'results' not in st.session_state:
    st.session_state.results = []
if 'working_model' not in st.session_state:
    st.session_state.working_model = None

# --- 侧边栏 ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Xiaohongshu_logo.svg/1200px-Xiaohongshu_logo.svg.png", width=50)
    st.header("⚙️ 全局设置")
    
    api_key = st.text_input("请输入 API Key", type="password", help="请使用 'REd book' 项目的 Key")
    
    # 自动模型检测
    if api_key:
        if not st.session_state.working_model:
            with st.spinner("正在匹配最佳模型..."):
                model, err = get_best_model(api_key)
                if model:
                    st.session_state.working_model = model
                    st.success(f"✅ 已锁定: {model}")
                else:
                    st.error(f"❌ {err}")
    
    st.divider()
    uploaded_file = st.file_uploader("📂 批量上传 (Excel/CSV)", type=['xlsx', 'csv'])
    st.caption("支持上传含文案的表格，自动读取第一列。")

# --- 主界面 ---
st.title("🍒 小红书 AI 选题中台")
st.markdown("##### 🚀 爆款文案拆解 & 标题生成一站式工具")

col1, col2 = st.columns([1, 1.5])

# 左侧：输入区
with col1:
    st.subheader("📝 输入素材")
    txt_input = st.text_area("在此粘贴竞品文案 (多篇请按空行分隔)", height=400, placeholder="粘贴文案...")
    
    # 运行条件检查
    can_run = api_key and st.session_state.working_model
    
    if st.button("✨ 开始 AI 深度拆解", type="primary", use_container_width=True, disabled=not can_run):
        
        # 1. 汇总任务
        tasks = []
        if txt_input: 
            tasks.extend([t.strip() for t in txt_input.split('\n\n') if len(t.strip()) > 5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:, 0].dropna().astype(str).tolist())
            except Exception as e:
                st.error(f"文件读取失败: {e}")
        
        if not tasks:
            st.warning("⚠️ 请输入文案或上传文件")
            st.stop()
            
        # 2. 开始处理
        progress_bar = st.progress(0)
        status_text = st.empty()
        new_results = []
        model_used = st.session_state.working_model
        
        for i, text in enumerate(tasks):
            status_text.markdown(f"🔄 **正在处理第 {i+1}/{len(tasks)} 条...**")
            
            # --- Step 1: 拆解 ---
            prompt_analyze = f"""
            分析文案:"{text[:800]}..."
            请提取以下4项核心信息，严格用 '|||' 符号隔开，不要换行，不要加其他废话：
            1. 原标题
            2. 人设 (判断是: 销售老徐 / 总助Fiona / 其他)
            3. 细分选题
            4. 爆款公式
            """
            ok1, res1 = call_gemini(prompt_analyze, api_key, model_used)
            
            item = {
                "原文片段": text[:20]+"...",
                "人设": "未知",
                "选题": "解析失败",
                "公式": "",
                "生成标题": ""
            }
            
            if ok1 and "|||" in res1:
                parts = res1.replace('```', '').strip().split('|||')
                if len(parts) >= 4:
                    item["人设"] = parts[1].strip()
                    item["选题"] = parts[2].strip()
                    item["公式"] = parts[3].strip()
                    
                    # --- Step 2: 生成 ---
                    prompt_gen = f"""
                    你现在是小红书博主【{item['人设']}】。
                    核心选题："{item['选题']}"。
                    请参考爆款公式："{item['公式']}"。
                    
                    👉 请创作 5 个极其吸引眼球的小红书标题。
                    要求：
                    1. 口语化，带情绪，加入emoji。
                    2. 针对商务/职场/送礼场景。
                    3. 直接输出5行标题，不要序号。
                    """
                    ok2, res2 = call_gemini(prompt_gen, api_key, model_used)
                    item["生成标题"] = res2 if ok2 else "生成失败"
                else:
                    item["生成标题"] = f"格式解析错误: {res1}"
            else:
                item["生成标题"] = f"AI请求失败: {res1}"
            
            new_results.append(item)
            progress_bar.progress((i + 1) / len(tasks))
            
        # 3. 完成
        st.session_state.results = new_results + st.session_state.results
        status_text.success(f"🎉 全部完成！共处理 {len(tasks)} 条")

# 右侧：结果展示区
with col2:
    st.subheader(f"📊 结果资产库 ({len(st.session_state.results)})")
    
    if st.session_state.results:
        df_res = pd.DataFrame(st.session_state.results)
        
        # 交互式表格
        st.dataframe(
            df_res, 
            column_config={
                "生成标题": st.column_config.TextColumn("AI 爆款标题", width="large"),
                "原文片段": st.column_config.TextColumn("原文", width="small"),
            },
            use_container_width=True,
            height=500
        )
        
        # 导出按钮
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
            
        st.download_button(
            label="📥 下载 Excel 报表",
            data=output.getvalue(),
            file_name=f"小红书AI拆解_{int(time.time())}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.button("🗑️ 清空列表", use_container_width=True):
            st.session_state.results = []
            st.rerun()
    else:
        st.info("👈 请在左侧输入内容并开始执行")
        st.markdown("""
        **使用小贴士：**
        1. 确保 API Key 旁边有绿色 ✅ (REd book 项目)。
        2. 文案支持从微信/文档直接批量复制粘贴。
        3. 遇到报错请检查网络或刷新页面。
        """)
