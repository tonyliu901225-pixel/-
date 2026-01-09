import streamlit as st
import requests
import pandas as pd
import io
import time
import base64
import re

# ==========================================
# 1. 基础配置
# ==========================================
st.set_page_config(
    page_title="小红书 AI 选题中台 (V31 操盘手融合版)",
    page_icon="🍒",
    layout="wide"
)

BASE_URL = "https://generativelanguage.googleapis.com"

# --- 融合优化后的默认风格约束 ---
DEFAULT_STYLE = """
1. **字数铁律**：严格控制在 20 字以内（手机屏一屏可见）。
2. **视觉钩子**：每条标题必须包含1-2个Emoji (🆘/🔥/💰/🤫/⚡️)，放在开头或情绪重点处。
3. **语气口语化**：像是在和闺蜜/兄弟说悄悄话，拒绝书面语。
4. **格式**：分5行展示，无序号，不要加引号。
"""

# --- 植入核心人设与公式库 (系统级 Prompt) ---
SYSTEM_ROLE = """
你不仅是文案专家，更是深谙中国职场“人情世故”的顶级销售/总助。
你擅长通过极具网感的标题，击中职场人“送礼怕出错”、“预算有限想装X”、“想维护客户关系”的隐秘痛点。
"""

TITLE_FORMULAS = """
请灵活运用以下5种高转化逻辑进行发散创作（不要死板套用）：
1. **【反常识/认知差】**：(e.g. 还在送XX？难怪客户记不住你！真正的行家都送XX)
2. **【强痛点/避坑】**：(e.g. 救命🆘！这种“工业垃圾”千万别送！直接拉黑！)
3. **【结果/功利导向】**：(e.g. 预算300拿下年框？这波操作老板夸我“会过日子”！)
4. **【情绪/私密分享】**：(e.g. 掏心窝子说一句，行政干了5年，全靠这个保命...)
5. **【悬念/引发好奇】**：(e.g. 送礼送到客户心坎里？这招“作弊级”攻略，建议收藏！)
"""

# ==========================================
# 2. 工具函数
# ==========================================

def clean_text(text):
    """超级清洗：移除所有序号、前缀、标点，只留核心词"""
    if not text: return ""
    pattern = r'^(\d+[\.\、\s]*|原标题[:：\s]*|人设[:：\s]*|细分切入[:：\s]*|爆款钩子[:：\s]*|底层逻辑[:：\s]*|主选题[:：\s]*)'
    lines = []
    for line in text.strip().split('\n'):
        cleaned = line.replace('**', '').strip()
        cleaned = re.sub(pattern, '', cleaned)
        cleaned = cleaned.rstrip('。')
        if cleaned: lines.append(cleaned)
    return "\n".join(lines)

def get_best_model(api_key):
    url = f"{BASE_URL}/v1beta/models?key={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200: return None, "Key 验证失败"
        data = resp.json()
        chat_models = [m['name'].replace('models/', '') for m in data.get('models', []) 
                       if 'generateContent' in m.get('supportedGenerationMethods', [])]
        best = next((m for m in chat_models if "flash" in m), chat_models[0] if chat_models else None)
        return best, None
    except: return None, "网络异常"

def call_gemini(prompt, api_key, model_name, image_data=None):
    url = f"{BASE_URL}/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    parts = [{"text": prompt}]
    if image_data:
        parts.append({"inline_data": {"mime_type": image_data['mime_type'], "data": image_data['data']}})
    payload = {"contents": [{"parts": parts}]}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return True, response.json()['candidates'][0]['content']['parts'][0]['text']
        return False, response.text
    except Exception as e:
        return False, str(e)

# ==========================================
# 3. 界面逻辑
# ==========================================

if 'results' not in st.session_state: st.session_state.results = []
if 'working_model' not in st.session_state: st.session_state.working_model = None

with st.sidebar:
    st.header("⚙️ 操盘手控制台")
    api_key = st.text_input("API Key", type="password")
    
    if api_key and not st.session_state.working_model:
        model, err = get_best_model(api_key)
        if model: st.session_state.working_model = model; st.success(f"已锁定: {model}")
    
    st.divider()
    st.subheader("🎨 风格约束 (可微调)")
    user_style = st.text_area("输出要求", value=DEFAULT_STYLE, height=180)
    
    st.divider()
    uploaded_file = st.file_uploader("📂 素材上传", type=['xlsx', 'csv', 'png', 'jpg', 'jpeg'])

st.title("🍒 小红书 AI 选题中台")
st.caption("🚀 V31.0 操盘手融合版 | 内置顶级销售思维 | 5维发散生成")

col_in, col_out = st.columns([1, 3])

with col_in:
    txt_input = st.text_area("在此粘贴素材", height=300, placeholder="粘贴竞品文案/产品描述...")
    
    if st.button("✨ 执行操盘手分析", type="primary", use_container_width=True, disabled=not api_key):
        tasks = []
        if txt_input:
            for t in [x.strip() for x in txt_input.split('\n\n') if len(x.strip()) > 5]:
                tasks.append({'type': 'text', 'content': t, 'name': t[:10]})
        if uploaded_file:
            f_type = uploaded_file.name.split('.')[-1].lower()
            if f_type in ['xlsx', 'csv']:
                df_up = pd.read_csv(uploaded_file) if f_type == 'csv' else pd.read_excel(uploaded_file)
                for t in df_up.iloc[:, 0].dropna().astype(str).tolist():
                    tasks.append({'type': 'text', 'content': t, 'name': t[:10]})
            else:
                b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
                tasks.append({'type': 'image', 'content': {'mime_type': f"image/{f_type.replace('jpg','jpeg')}", 'data': b64}, 'name': f"图片:{uploaded_file.name}"})

        if not tasks: st.warning("未检测到输入"); st.stop()
            
        bar = st.progress(0); status = st.empty(); new_res = []
        
        for i, task in enumerate(tasks):
            status.markdown(f"🔄 **深度拆解中 {i+1}/{len(tasks)}**")
            
            # --- 阶段 1：深度拆解 (融合新逻辑) ---
            # 这里的 Prompt 进行了大幅升级，要求提取“爆款钩子”和“微观切入点”
            p_analyze = f"""
            {SYSTEM_ROLE}
            分析素材: "{task['content'] if task['type']=='text' else '图片'}"
            
            请进行【三维拆解】，提取以下5项，严格用 '|||' 隔开。
            ⚠️ 输出要求：极简、标签化、不要废话。
            
            1. 原标题 (仅保留核心意思)
            2. 人设定位 (判断是: 毒舌老徐 / 细腻Fiona / 焦虑小白)
            3. 细分切入 (⚠️拒绝笼统！例如: "1000元送50岁领导" 而不是 "商务送礼")
            4. 爆款钩子 (提取关键词: 如 "智商税"、"天花板"、"保命"、"拿捏")
            5. 底层逻辑 (如: 痛点+反常识+方案)
            """
            
            ok1, res1 = call_gemini(p_analyze, api_key, st.session_state.working_model, task['content'] if task['type']=='image' else None)
            
            if ok1 and "|||" in res1:
                pts = res1.split("|||")
                if len(pts) >= 5:
                    row = {
                        "来源": task['name'],
                        "原标题": clean_text(pts[0]),
                        "人设": clean_text(pts[1]),
                        "细分切入": clean_text(pts[2]),
                        "爆款钩子": clean_text(pts[3]),
                        "底层逻辑": clean_text(pts[4]),
                    }
                    
                    # --- 阶段 2：发散生成 (融合公式库) ---
                    p_gen = f"""
                    {SYSTEM_ROLE}
                    当前任务信息：
                    - 人设：{row['人设']}
                    - 细分切入点：{row['细分切入']}
                    - 必含爆款词：{row['爆款钩子']}
                    
                    {TITLE_FORMULAS}
                    
                    👉 请基于以上5种逻辑，创作 5 个截然不同的标题。
                    ⚠️ 严格执行以下风格约束：
                    {user_style}
                    """
                    
                    ok2, res2 = call_gemini(p_gen, api_key, st.session_state.working_model)
                    row["AI 爆款标题"] = clean_text(res2) if ok2 else "生成失败"
                    new_res.append(row)
            
            bar.progress((i+1)/len(tasks))
            
        st.session_state.results = new_res + st.session_state.results
        status.success("🎉 分析完成")

with col_out:
    if st.session_state.results:
        df_res = pd.DataFrame(st.session_state.results)
        
        st.dataframe(
            df_res,
            column_config={
                "AI 爆款标题": st.column_config.TextColumn("AI 爆款标题 (5维发散)", width="large"),
                "细分切入": st.column_config.TextColumn("细分切入点", width="medium"),
                "爆款钩子": st.column_config.TextColumn("爆款钩子", width="small"),
                "底层逻辑": st.column_config.TextColumn("底层逻辑", width="small"),
                "人设": st.column_config.TextColumn("人设", width="small"),
            },
            use_container_width=True, height=600
        )
        
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
            df_res.to_excel(wr, index=False, sheet_name='选题库')
            bk = wr.book; ws = wr.sheets['选题库']
            fmt = bk.add_format({'text_wrap': True, 'valign': 'top', 'border': 1})
            
            ws.set_column('A:A', 10, fmt) # 来源
            ws.set_column('B:B', 20, fmt) # 原标题
            ws.set_column('C:C', 10, fmt) # 人设
            ws.set_column('D:D', 20, fmt) # 细分切入
            ws.set_column('E:E', 20, fmt) # 爆款钩子
            ws.set_column('F:F', 20, fmt) # 底层逻辑
            ws.set_column('G:G', 50, fmt) # 生成标题
            
        st.download_button("📥 下载选题库 Excel", out.getvalue(), f"XHS_Pro_{int(time.time())}.xlsx", use_container_width=True)
        if st.button("🗑️ 清空结果"): st.session_state.results = []; st.rerun()
