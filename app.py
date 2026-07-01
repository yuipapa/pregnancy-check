import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="산전검진휴가 통합 관리 시스템", layout="wide")

# --- 데이터베이스 파일 설정 ---
DB_FILE = "pregnancy_history.csv"

if not os.path.exists(DB_FILE):
    df_empty = pd.DataFrame(columns=[
        "사번", "성명", "분만예정일", "휴가신청일", 
        "임신후경과일", "실제임신주수", "법령구간", "승인여부", "비고사유"
    ])
    df_empty.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

def load_db():
    df = pd.read_csv(DB_FILE, encoding='utf-8-sig')
    # 사번을 매칭하기 쉽도록 문자열 타입으로 통일
    df["사번"] = df["사번"].astype(str).str.strip()
    return df

def save_db(df):
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# --- 주수 계산 로직 ---
def calculate_pregnancy_details(expected_date, app_date):
    try:
        pregnancy_start = expected_date - timedelta(days=280)
        elapsed_days = (app_date - pregnancy_start).days
        
        if elapsed_days < 0:
            return elapsed_days, "0주 0일", "임신 전", 0, 0, "불가", "신청일이 임신 시작일보다 빠릅니다."
        
        curr_week = elapsed_days // 7
        days = elapsed_days % 7
        weeks_str = f"{curr_week}주 {days}일"
        
        if curr_week <= 28:
            law_section = "28주 이하(4주 1회)"
            cycle_weeks = 4
            p_group = curr_week // 4
        elif curr_week <= 36:
            law_section = "29~36주(2주 1회)"
            cycle_weeks = 2
            p_group = curr_week // 2
        else:
            law_section = "37주 이상(1주 1회)"
            cycle_weeks = 1
            p_group = curr_week
            
        return elapsed_days, weeks_str, law_section, cycle_weeks, p_group, "가능", ""
    except Exception as e:
        return None, "오류", "데이터 오류", 0, 0, "불가", str(e)

# --- UI 레이아웃 ---
st.title("🤰 산전검진휴가 실시간 판정 및 누적 관리 시스템")
st.markdown("데이터가 웹 서버에 누적 저장되어, 다음 신청 시 과거 이력을 기반으로 승인/미승인을 자동 판단합니다.")
st.divider()

# 좌우 레이아웃 분할 (왼쪽: 입력 폼 / 오른쪽: 누적 데이터베이스 조회 및 관리)
col_left, col_right = st.columns([1, 1.3])

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
            elapsed, w_str, law, cycle, p_group, _, reason = calculate_pregnancy_details(expected_date, app_date)
            
            if elapsed is None or elapsed < 0:
                st.error(f"❌ 판정 불가: {reason}")
            else:
                db_df = load_db()
                emp_history = db_df[(db_df["사번"] == emp_id) & (db_df["승인여부"] == "승인")]
                
                is_duplicate = False
                for _, row in emp_history.iterrows():
                    _, _, p_law, _, p_group_old, _, _ = calculate_pregnancy_details(
                        pd.to_datetime(row["분만예정일"]), pd.to_datetime(row["휴가신청일"])
                    )
                    if p_law == law and p_group_old == p_group:
                        is_duplicate = True
                        break
                
                if is_duplicate:
                    final_approval = "반려"
                    final_reason = f"해당 주기({law}) 내 이미 사용한 검진휴가 이력이 존재합니다."
                    st.error(f"⛔ 판정 결과: [반려] - {final_reason}")
                else:
                    final_approval = "승인"
                    final_reason = ""
                    st.success(f"✅ 판정 결과: [최종 승인] 가능 건입니다! ({w_str} / {law})")
                
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
    
    # 1. 검색 기능
    search_id = st.text_input("🔍 사번 검색 (비워두면 전체 조회)", value="")
    if search_id.strip():
        display_db = current_db[current_db["사번"].str.contains(search_id.strip())].copy()
    else:
        display_db = current_db.copy()
        
    # 데이터 구분을 위해 인덱스를 임의의 고유 번호 컬럼으로 노출
    display_db.insert(0, '데이터번호', display_db.index)
    st.dataframe(display_db, use_container_width=True, height=280, hide_index=True)
    
    st.divider()
    
    # 2. 데이터 관리 및 삭제 코너
    st.subheader("⚙️ 데이터 삭제 관리자 메뉴")
    del_tab1, del_tab2, del_tab3 = st.tabs(["📌 선택 행 한 개 삭제", "👥 특정 사번 전체 삭제", "🚨 전체 초기화"])
    
    # Tab 1: 데이터 1개만 골라서 삭제
    with del_tab1:
        if not current_db.empty:
            # 선택하기 좋게 리스트 구성 (번호 - 사번 - 성명 - 신청일)
            options = {
                idx: f"[번호 {idx}] 사번: {row['사번']} | {row['성명']} | 신청일: {row['휴가신청일']} ({row['승인여부']})"
                for idx, row in current_db.iterrows()
            }
            selected_idx = st.selectbox("삭제할 데이터를 선택하세요", options=list(options.keys()), format_func=lambda x: options[x])
            
            if st.button("❌ 선택한 데이터 1건 삭제", type="primary"):
                current_db = current_db.drop(selected_idx).reset_index(drop=True)
                save_db(current_db)
                st.success("선택하신 데이터가 성공적으로 삭제되었습니다.")
                st.rerun()
        else:
            st.caption("삭제할 데이터가 없습니다.")

    # Tab 2: 특정 사번 데이터만 통째로 삭제
    with del_tab2:
        target_emp_id = st.text_input("삭제할 대상의 사번을 입력하세요")
        if st.button("🗑️ 해당 사번의 모든 기록 삭제"):
            if target_emp_id.strip():
                target_emp_id = target_emp_id.strip()
                if target_emp_id in current_db["사번"].values:
                    current_db = current_db[current_db["사번"] != target_emp_id].reset_index(drop=True)
                    save_db(current_db)
                    st.success(f"사번 [{target_emp_id}] 직원의 모든 데이터가 삭제되었습니다.")
                    st.rerun()
                else:
                    st.error("입력하신 사번의 데이터가 데이터베이스에 존재하지 않습니다.")
            else:
                st.warning("사번을 입력해 주세요.")

    # Tab 3: 전체 초기화
    with del_tab3:
        st.warning("이 작업은 되돌릴 수 없습니다. 신중하게 선택해 주세요.")
        if st.button("🚨 데이터베이스 전체 초기화", type="secondary"):
            df_empty = pd.DataFrame(columns=["사번", "성명", "분만예정일", "휴가신청일", "임신후경과일", "실제임신주수", "법령구간", "승인여부", "비고사유"])
            save_db(df_empty)
            st.success("데이터베이스가 완전히 비워졌습니다.")
            st.rerun()
