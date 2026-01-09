import streamlit as st
import requests
import pandas as pd
import io
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="小红书AI中台 (V10 显影版)", page_icon="🍒", layout="wide")

# --- 2. 核心逻辑：带线路切换的 API 请求 ---
def call_gemini_requests(prompt, api_key, base_url):
    # 自动处理 URL 末尾的斜杠
    base_url = base_url.rstrip('/')
    url = f"{base_url}/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        # 设置30秒超时
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # 如果状态码不是200 (成功)，返回错误信息
        if response.status_code != 200:
            return {"success": False, "error": f"HTTP报错 {response.status_code}: {response.text[:200]}"}
            
        result = response.json()
        # 尝试提取文本
        try:
            text = result['candidates'][0]['content']['parts'][0]['text']
            return {"success": True, "text": text}
        except:
            return {"success": False, "error": f"API返回结构异常: {str(result)[:200]}"}
            
    except Exception as e:
        return {"success": False, "error": f"网络连通性错误: {str(e)}"}

# --- 3. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 关键设置")
    
    api_key = st.text_input("1. 输入 API Key", type="password", help="粘贴您的 Gemini Key")
    
    st.markdown("### 2. 线路选择 (救命稻草)")
    st.warning("如果一直报错，请尝试切换下方的线路 👇")
    line_option = st.radio(
        "选择 API 线路：",
        ("国内中转 A (推荐)", "国内中转 B (备用)", "官方直连 (需全局VPN)"),
        index=0
    )
    
    # 映射线路地址
    base_urls = {
        "官方直连 (需全局VPN)": "https://generativelanguage.googleapis.com",
        "国内中转 A (推荐)": "https://cf.aigc.mn", 
        "国内中转 B (备用)": "https://gemini-api.iyuu.cn"
    }
    current_base_url = base_urls[line_option]
    
    st.success(f"当前连接：{current_base_url}")
    st.markdown("---")
    uploaded_file = st.file_uploader("📂 上传 Excel/CSV", type=['xlsx', 'csv'])

# --- 4. 主界面 ---
st.title("🍒 小红书 AI 选题中台 (V10)")
st.caption("🚀 包含错误诊断功能 | 支持线路切换")

if 'results' not in st.session_state:
    st.session_state.results = []

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 输入区")
    txt_input = st.text_area("在此粘贴文案 (按空行分隔)", height=300, placeholder="粘贴文案...")
    
    if st.button("✨ 开始 AI 深度拆解", type="primary", use_container_width=True):
        if not api_key:
            st.error("❌ 请先在左侧侧边栏填入 API Key！")
            st.stop()
            
        tasks = []
        if txt_input: tasks.extend([t.strip() for t in txt_input.split('\n\n') if len(t.strip()) > 5])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                tasks.extend(df.iloc[:, 0].dropna().astype(str).tolist())
            except Exception as e:
                st.error(f"文件读取失败: {e}")
                
        if not tasks:
            st.warning("⚠️ 请输入文案或上传文件")
            st.stop()

        # 进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        new_results = []
        
        for i, text in enumerate(tasks):
            status_text.text(f"正在狂奔处理第 {i+1}/{len(tasks)} 条...")
            
            # --- 第一步：拆解 ---
            prompt_analyze = f"""分析文案:"{text[:500]}...".提取4项用|||隔开: 原标题|||人设(销售-老徐/总助-Fiona)|||细分选题|||标题公式|||爆款元素(逗号隔开)"""
            
            # 调用 API
            res1 = call_gemini_requests(prompt_analyze, api_key, current_base_url)
            
            item = {
                "原文": text[:30]+"...",
                "状态": "✅ 成功",
                "错误详情": ""
            }
            
            if res1['success']:
                # 成功拿回数据，开始解析格式
                raw_text = res1['text']
                if "|||" in raw_text:
                    parts = raw_text.replace('```', '').strip().split('|||')
                    if len(parts) >= 4:
                        item["人设"] = parts[1]
                        item["选题"] = parts[2]
                        item["公式"] = parts[3]
                        item["元素"] = parts[4] if len(parts) > 4 else ""
                        
                        # --- 第二步：生成标题 ---
                        prompt_title = f"""你叫{item['人设']},选题"{item['选题']}",公式"{item['公式']}".写5个爆款标题,每行一个,无序号."""
                        res2 = call_gemini_requests(prompt_title, api_key, current_base_url)
                        
                        if res2['success']:
                            item["生成标题"] = res2['text']
                        else:
                            item["生成标题"] = f"标题生成失败: {res2['error']}"
                    else:
                        item["状态"] = "⚠️ 格式错误"
                        item["错误详情"] = f"AI返回了数据但格式不对: {raw_text}"
                else:
                    item["状态"] = "⚠️ 格式错误"
                    item["错误详情"] = f"AI未返回分隔符: {raw_text}"
            else:
                # API 请求直接失败（网络或Key问题）
                item["状态"] = "❌ 请求失败"
                item["错误详情"] = res1['error']
            
            new_results.append(item)
            progress_bar.progress((i + 1) / len(tasks))
            
        st.session_state.results = new_results + st.session_state.results
        status_text.success("🎉 全部执行完毕！请查看右侧结果")

with col2:
    st.subheader(f"📚 结果资产库 ({len(st.session_state.results)})")
    
    if st.session_state.results:
        # 显示结果表
        df_res = pd.DataFrame(st.session_state.results)
        
        # 重点：把错误信息展示出来
        st.dataframe(
            df_res, 
            column_config={
                "错误详情": st.column_config.TextColumn("诊断信息 (红色代表出错)", width="large"),
                "生成标题": st.column_config.TextColumn("AI 标题", width="large"),
            },
            use_container_width=True
        )
        
        # 导出
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        st.download_button("📥 下载 Excel 报表", output.getvalue(), "小红书AI分析结果.xlsx")
        
        if st.button("🗑️ 清空列表"):
            st.session_state.results = []
            st.rerun()
    else:
        st.info("👈 请在左侧输入文案，点击开始")
