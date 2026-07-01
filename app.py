import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="산전검진휴가 통합 관리 시스템", layout="wide")

# --- 데이터베이스 파일 설정 ---
# 웹 프로그램이 실행되는 가상 공간에 데이터를 저장할 CSV 파일 이름
DB_FILE = "pregnancy_history.csv"

if not os.path.exists(DB_FILE):
    # 파일이 없으면 빈 데이터프레임 생성 (기본 컬럼 정의)
    df_empty = pd.DataFrame(columns=[
        "사번", "성명", "분만예정일", "휴가신청일", 
        "임신후경과일", "실제임신주수", "법령구간", "승인여부", "비고사유"
    ])
    df_empty.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

def load_db():
    return pd.read_csv(DB_FILE, encoding='utf-8-sig')

def save_db(df):
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# --- 수정된 주수 계산 로직 ---
def calculate_pregnancy_details(expected_date, app_date):
    try:
        # 분만예정일로부터 280일 전 = 임신 0주 0일 시작일
        pregnancy_start = expected_date - timedelta(days=280)
        elapsed_days = (app_date - pregnancy_start).days
        
        if elapsed_days < 0:
            return elapsed_days, "0주 0일", "임신 전", 0, 0, "불가", "신청일이 임신 시작일보다 빠릅니다."
        
        # 33주 3일처럼 정확한 주수 매칭 (몫이 주수, 나머지가 일수)
        curr_week = elapsed_days // 7
        days = elapsed_days % 7
        weeks_str = f"{curr_week}주 {days}일"
        
        # 모자보건법 기준 구간 및 주기 (중복 판정용 묶음ID 계산)
        if curr_week <= 28:
            law_section = "28주 이하(4주 1회)"
            cycle_weeks = 4
            p_group = curr_week // 4  # 4주 단위 묶음
        elif curr_week <= 36:
            law_section = "29~36주(2주 1회)"
            cycle_weeks = 2
            p_group = curr_week // 2  # 2주 단위 묶음
        else:
            law_section = "37주 이상(1주 1회)"
            cycle_weeks = 1
            p_group = curr_week      # 1주 단위 묶음
            
        return elapsed_days, weeks_str, law_section, cycle_weeks, p_group, "가능", ""
    except Exception as e:
        return None, "오류", "데이터 오류", 0, 0, "불가", str(e)

# --- UI 레이아웃 ---
st.title("🤰 산전검진휴가 실시간 판정 및 누적 관리 시스템")
st.markdown("데이터가 웹 서버에 누적 저장되어, 다음 신청 시 과거 이력을 기반으로 승인/미승인을 자동 판단합니다.")
st.divider()

# 좌우 레이아웃 분할 (왼쪽: 입력 폼 / 오른쪽: 누적 데이터베이스 조회)
col_left, col_right = st.columns([1, 1.2])

with col_left:
    st.subheader("📋 신규 신청 정보 입력")
    with st.form("vactation_form", clear_on_submit=False):
        emp_id = st.text_input("사번 (필수)", value="")
        emp_name = st.text_input("직원 성명", value="")
        expected_date = st.date_input("분만 예정일", value=datetime.today() + timedelta(days=100))
        app_date = st.date_input("휴가 신청일(검진일)", value=datetime.today())
        
        submitted = st.form_submit_button("🔍 판정 및 시스템 등록")

    if submitted:
        if not emp_id.strip():
            st.error("⚠️ 사번은 누적 관리를 위한 필수 키 값입니다. 입력해 주세요.")
        else:
            emp_id = emp_id.strip()
            # 1. 주수 및 기본 구간 계산 (수정본 반영)
            elapsed, w_str, law, cycle, p_group, _, reason = calculate_pregnancy_details(expected_date, app_date)
            
            if elapsed is None or elapsed < 0:
                st.error(f"❌ 판정 불가: {reason}")
            else:
                # 2. DB에서 이 직원(사번)의 기존 승인 이력 조회
                db_df = load_db()
                
                # 동일 사번 중 '승인'된 내역만 필터링해서 중복 체크
                emp_history = db_df[(db_df["사번"].astype(str) == emp_id) & (db_df["승인여부"] == "승인")]
                
                is_duplicate = False
                # 기존 이력들을 돌며 동일한 법령 구간 및 주차 묶음에 있는지 확인
                for _, row in emp_history.iterrows():
                    # 과거 기록 재계산해서 비교
                    _, _, p_law, _, p_group_old, _, _ = calculate_pregnancy_details(
                        pd.to_datetime(row["분만예정일"]), pd.to_datetime(row["휴가신청일"])
                    )
                    if p_law == law and p_group_old == p_group:
                        is_duplicate = True
                        break
                
                # 3. 최종 승인/반려 판정
                if is_duplicate:
                    final_approval = "반려"
                    final_reason = f"해당 주기({law}) 내 이미 사용한 검진휴가 이력이 존재합니다."
                    st.error(f"⛔ 판정 결과: [반려] - {final_reason}")
                else:
                    final_approval = "승인"
                    final_reason = ""
                    st.success(f"✅ 판정 결과: [최종 승인] 가능 건입니다! ({w_str} / {law})")
                
                # 4. 판정된 데이터를 DB에 즉시 저장
                new_data = {
                    "사번": emp_id,
                    "성명": emp_name,
                    "분만예정일": expected_date.strftime("%Y-%m-%d"),
                    "휴가신청일": app_date.strftime("%Y-%m-%d"),
                    "임신후경과일": elapsed,
                    "실제임신주수": w_str,
                    "법령구간": law,
                    "승인여부": final_approval,
                    "비고사유": final_reason
                }
                db_df = pd.concat([db_df, pd.DataFrame([new_data])], ignore_index=True)
                save_db(db_df)
                st.caption("ℹ️ 대시보드에 데이터가 안전하게 누적 기록되었습니다.")

with col_right:
    st.subheader("🗄️ 누적 데이터베이스 대시보드")
    current_db = load_db()
    
    # 사번 검색 기능 추가
    search_id = st.text_input("🔍 특정 사번 검색 (비워두면 전체 조회)", value="")
    if search_id.strip():
        filtered_db = current_db[current_db["사번"].astype(str).str.contains(search_id.strip())]
    else:
        filtered_db = current_db
        
    st.dataframe(filtered_db, use_container_width=True, height=350)
    
    # 전체 데이터 초기화 버튼 (테스트용)
    if st.button("⚠️ 데이터베이스 전체 초기화"):
        df_empty = pd.DataFrame(columns=["사번", "성명", "분만예정일", "휴가신청일", "임신후경과일", "실제임신주수", "법령구간", "승인여부", "비고사유"])
        save_db(df_empty)
        st.rerun()
