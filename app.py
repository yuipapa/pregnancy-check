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
        # 1. 파일 읽기 (헤더 없이 우선 전체 읽기)
        if uploaded_file.name.endswith('.csv'):
            raw_df = pd.read_csv(uploaded_file, header=None)
        else:
            raw_df = pd.read_excel(uploaded_file, header=None)
            
        # 2. 진짜 헤더(사번, 성명 등이 있는 행) 자동 찾기 기법
        header_row_idx = None
        required_cols = ['사번', '성명', '분만예정일', '휴가 신청일']
        
        for idx in range(min(len(raw_df), 20)):  # 상위 20개 행 안에서 검색
            row_values = raw_df.iloc[idx].dropna().astype(str).tolist()
            # 공백 제거 후 비교
            row_values_clean = [v.strip() for v in row_values]
            if all(col in row_values_clean for col in required_cols):
                header_row_idx = idx
                break

        if header_row_idx is None:
            st.error("❌ 파일에서 '사번', '성명', '분만예정일', '휴가 신청일' 컬럼을 찾을 수 없습니다. 엑셀 시트에 해당 항목명이 정확히 입력되어 있는지 확인해 주세요.")
        else:
            # 찾은 행을 컬럼명으로 지정하고 그 아래 데이터만 슬라이싱
            columns_names = raw_df.iloc[header_row_idx].astype(str).str.strip().tolist()
            df = raw_df.iloc[header_row_idx+1:].copy()
            df.columns = columns_names
            df = df.reset_index(drop=True)
            
            # 필수 데이터가 비어있는 행 제외
            df = df.dropna(subset=['사번', '분만예정일', '휴가 신청일']).copy()
            df['휴가 신청일'] = pd.to_datetime(df['휴가 신청일'])
            df = df.sort_values(by=['사번', '휴가 신청일']).reset_index(drop=True)
            
            elapsed_list, weeks_list, law_list, status_list, app_list, reason_list = [], [], [], [], [], []
            history = {}
            
            for idx, row in df.iterrows():
                emp_id = str(row['사번']).strip()
                expected = str(row['분만예정일']).strip()
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
            
            # 불필요한 기존 보조 컬럼들은 제외하고 깔끔하게 보여주기
            display_cols = ['사번', '성명', '분만예정일', '휴가 신청일', '임신후경과일', '실제 임신주수', '법령구간', '검진가능여부', '승인여부', '반려/비고 사유']
            final_df = df[[c for c in display_cols if c in df.columns]]
            
            st.subheader("📊 검증 요약")
            c1, c2, c3 = st.columns(3)
            c1.metric("총 신청", f"{len(final_df)} 건")
            c2.metric("승인", f"{len(final_df[final_df['승인여부'] == '승인'])} 건")
            c3.metric("반려", f"{len(final_df[final_df['승인여부'] == '반려'])} 건")
            
            st.dataframe(final_df, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False, sheet_name='검증결과')
            
            st.download_button(
                label="📥 결과 엑셀 다운로드",
                data=output.getvalue(),
                file_name="산전검진휴가_검증결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        st.error(f"오류 발생: {e}")
