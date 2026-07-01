import streamlit as st
import pandas as pd
from datetime import timedelta
import io

st.set_page_config(page_title="산전검진휴가 신청 검증 시스템", layout="wide")

def calculate_pregnancy_details(expected_date_str, application_date_str):
    try:
        expected_date = pd.to_datetime(expected_date_str)
        app_date = pd.to_datetime(application_date_str)
        pregnancy_start = expected_date - timedelta(days=280)
        elapsed_days = (app_date - pregnancy_start).days + 1
        if elapsed_days < 1:
            return elapsed_days, "0주 0일", "임신 전", 0, 0, 0
        curr_week = (elapsed_days - 1) // 7 + 1
        days = (elapsed_days - 1) % 7
        weeks_str = f"{curr_week}주 {days}일"
        if curr_week <= 28:
            law_section = "28주 이하(4주1회)"
            cycle_weeks = 4
            p_group = (curr_week - 1) // 4
        elif curr_week <= 36:
            law_section = "29-36주(2주1회)"
            cycle_weeks = 2
            p_group = (curr_week - 1) // 2
        else:
            law_section = "37주 이상(1주1회)"
            cycle_weeks = 1
            p_group = curr_week
        return elapsed_days, weeks_str, law_section, curr_week, cycle_weeks, p_group
    except:
        return None, "오류", "데이터 확인 요망", 0, 0, 0

st.title("🤰 산전검진휴가 신청 자동판단 시스템")
st.markdown("엑셀 또는 CSV 파일을 업로드하면 승인/반려를 자동으로 판정합니다.")
st.divider()

uploaded_file = st.file_uploader("신청 현황 파일(CSV 또는 XLSX)을 업로드하세요.", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        if "사번" not in df.columns:
            for i in range(min(len(df), 15)):
                if df.iloc[i].astype(str).str.contains("사번").any():
                    df.columns = df.iloc[i]
                    df = df.iloc[i+1:].reset_index(drop=True)
                    break

        required_cols = ['사번', '성명', '분만예정일', '휴가 신청일']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"필수 컬럼 누락: {missing_cols}")
        else:
            df = df.dropna(subset=['사번', '분만예정일', '휴가 신청일']).copy()
            df['휴가 신청일'] = pd.to_datetime(df['휴가 신청일'])
            df = df.sort_values(by=['사번', '휴가 신청일']).reset_index(drop=True)
            
            elapsed_list, weeks_list, law_list, status_list, app_list, reason_list = [], [], [], [], [], []
            history = {}
            
            for idx, row in df.iterrows():
                emp_id = row['사번']
                expected = row['분만예정일']
                app_date = row['휴가 신청일']
                elapsed, w_str, law, curr_week, cycle, p_group = calculate_pregnancy_details(expected, app_date)
                
                elapsed_list.append(elapsed)
                weeks_list.append(w_str)
                law_list.append(law)
                
                if elapsed is None or elapsed < 1:
                    status_list.append("불가")
                    app_list.append("반려")
                    reason_list.append("날짜 오류")
                    continue
                
                if emp_id not in history:
                    history[emp_id] = []
                is_dup = any(pc == cycle and pg == p_group for pc, pg in history[emp_id])
                
                if is_dup:
                    status_list.append("가능")
                    app_list.append("반려")
                    reason_list.append(f"주기 내 중복 신청")
                else:
                    status_list.append("가능")
                    app_list.append("승인")
                    reason_list.append("")
                    history[emp_id].append((cycle, p_group))
            
            df['휴가 신청일'] = df['휴가 신청일'].dt.strftime('%Y-%m-%d')
            df['임신후경과일'] = elapsed_list
            df['실제 임신주수'] = weeks_list
            df['법령구간'] = law_list
            df['검진가능여부'] = status_list
            df['승인여부'] = app_list
            df['반려/비고 사유'] = reason_list
            
            st.subheader("📊 검증 요약")
            c1, c2, c3 = st.columns(3)
            c1.metric("총 신청", f"{len(df)} 건")
            c2.metric("승인", f"{len(df[df['승인여부'] == '승인'])} 건")
            c3.metric("반려", f"{len(df[df['승인여부'] == '반려'])} 건")
            
            st.dataframe(df, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='검증결과')
            
            st.download_button(
                label="📥 결과 엑셀 다운로드",
                data=output.getvalue(),
                file_name="산전검진휴가_검증결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        st.error(f"오류 발생: {e}")
