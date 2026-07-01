import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="산전검진휴가 실시간 건별 조회", layout="centered")

def calculate_pregnancy_details(expected_date, app_date):
    try:
        # 분만예정일로부터 280일 전을 임신 시작일(0주 1일)로 계산
        pregnancy_start = expected_date - timedelta(days=280)
        elapsed_days = (app_date - pregnancy_start).days + 1
        
        if elapsed_days < 1:
            return elapsed_days, "0주 0일", "임신 전", 0, "불가", "신청일이 임신 시작일보다 빠릅니다."
        
        # 주차 및 일수 계산
        curr_week = (elapsed_days - 1) // 7 + 1
        days = (elapsed_days - 1) % 7
        weeks_str = f"{curr_week}주 {days}일"
        
        # 모자보건법 기준 구간 및 주기 설정
        if curr_week <= 28:
            law_section = "28주 이하(4주 1회)"
        elif curr_week <= 36:
            law_section = "29~36주(2주 1회)"
        else:
            law_section = "37주 이상(1주 1회)"
            
        return elapsed_days, weeks_str, law_section, curr_week, "가능", ""
    except Exception as e:
        return None, "오류", "데이터 오류", 0, "불가", str(e)

# --- UI 레이아웃 ---
st.title("🤰 산전검진휴가 실시간 판정기")
st.markdown("직원의 분만예정일과 휴가 신청일을 입력하면 즉시 법령 구간과 승인 가능 여부를 판정합니다.")
st.divider()

# 데이터 입력 폼
with st.form("vactation_form"):
    st.subheader("📋 신청 정보 입력")
    
    col1, col2 = st.columns(2)
    with col1:
        emp_name = st.text_input("직원 성명", value="홍길동")
        expected_date = st.date_input("분만 예정일", value=datetime.today() + timedelta(days=100))
    with col2:
        emp_id = st.text_input("사번", value="123456")
        app_date = st.date_input("휴가 신청일(검진일)", value=datetime.today())
        
    submitted = st.form_submit_button("🔍 즉시 판정하기")

# 판정 결과 출력
if submitted:
    elapsed, w_str, law, curr_week, status, reason = calculate_pregnancy_details(expected_date, app_date)
    
    st.divider()
    st.subheader("📝 판정 결과")
    
    if elapsed is not None and elapsed >= 1:
        # 결과를 보기 좋게 표 형태로 정돈
        result_data = {
            "항목": ["사번 / 성명", "임신 후 경과일", "현재 실제 임신주수", "모자보건법상 구간", "검진 가능 여부"],
            "상세 내용": [f"{emp_id} / {emp_name}", f"{elapsed}일째", w_str, law, status]
        }
        res_df = pd.DataFrame(result_data)
        st.table(res_df)
        
        # 승인 가이드 메시지
        st.info(f"💡 **인사담당자 가이드**: 본 신청 건은 **{law}** 구간에 해당합니다. 동일 구간(묶음) 내에 이미 사용한 검진 휴가가 없다면 **[최종 승인]** 처리가 가능합니다.")
    else:
        st.error(f"❌ 판정 불가: {reason}")
