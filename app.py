import streamlit as st
import requests

st.set_page_config(page_title="Key 体检中心", page_icon="🏥")

st.title("🏥 API Key 深度体检仪")
st.info("此工具用于检测您的 Key 是否有效，以及您的网络环境。")

# 1. 环境自检
st.subheader("1. 环境检测")
try:
    # 尝试连接 Google 裸域，看是否通畅
    resp = requests.get("https://generativelanguage.googleapis.com", timeout=5)
    if resp.status_code == 404: # 根路径404是正常的，说明连通了
        st.success("✅ 网络畅通：已成功连接 Google 官方服务器！")
    else:
        st.warning(f"⚠️ 网络响应异常: HTTP {resp.status_code}")
except Exception as e:
    st.error(f"❌ 网络不通！您可能还在本地且没开VPN。错误: {e}")
    st.stop() # 网络不通，后面不用测了

# 2. Key 检测
st.subheader("2. Key 有效性检测")
api_key = st.text_input("在此粘贴您新申请的 Key (AIza开头)", type="password")

if api_key:
    if st.button("🚀 开始检测 Key"):
        with st.spinner("正在询问 Google..."):
            # 使用 listModels 接口来测试 Key 的权限
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    models = [m['name'].replace('models/', '') for m in data.get('models', [])]
                    st.balloons()
                    st.success(f"🎉 恭喜！这是一个完美的 Key！")
                    st.write(f"**该 Key 支持的所有模型 ({len(models)}个):**")
                    st.code(models)
                    st.markdown("### 👉 下一步")
                    st.markdown("既然 Key 没问题，您可以把之前的 V13 或 V15 代码刷回来，填入这个 Key 就能用了！")
                
                elif response.status_code == 400:
                    st.error("❌ Key 格式错误 (HTTP 400)")
                    st.write("Google 说：API Key not valid。请检查是否复制完整了？")
                    
                elif response.status_code == 403:
                    st.error("❌ 权限不足 (HTTP 403)")
                    st.write("Google 说：您没有权限访问。可能是项目没开通 API，建议重新申请 Key。")
                    
                else:
                    st.error(f"❌ 未知错误 (HTTP {response.status_code})")
                    st.code(response.text)
                    
            except Exception as e:
                st.error(f"检测出错: {e}")
