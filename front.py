import streamlit as st
import requests

st.title("📈 10年後の株価予測アプリ")
st.caption("現在の株価をもとに、10年後の目安を計算して表示します。")

ticker = st.text_input("銘柄コードを入力してください (例: 7203.T, AAPL)", "7203.T")

if st.button("10年後を予測"):
    with st.spinner("過去10年のデータと成長率を分析中..."):
        res = requests.get(f"http://localhost:8001/predict/{ticker}")

        if res.status_code == 200:
            data = res.json()
            st.write(f"**現在の株価**: {data['latest_price']:.0f} 円")
            st.write(f"**10年後の予想価格**: {data['projected_price_10y']:.0f} 円")
            st.write(f"**10年後の変化率**: {data['projected_change_pct']:.1f}%")
            st.json(data['prediction'])
        else:
            st.error("データの取得に失敗しました。")