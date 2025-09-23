#streamlit run "C:\Users\권민서\OneDrive\바탕 화면\Mina\app.py"
#streamlit run "C:\Users\권민서\OneDrive\바탕 화면\Mina\app.py"
# app.py
# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import html

import pandas as pd
import streamlit as st

# =============== App Config ===============
st.set_page_config(page_title="PDI - Provide Discount Information", layout="wide")

# 흰 글씨 / 검정 배경
CUSTOM_CSS = """
<style>
  .stApp { background-color: #000000 !important; color: #FFFFFF !important; }
  div[data-testid="stMarkdownContainer"] p, h1, h2, h3, h4, h5, h6, label, span, a { color: #FFFFFF !important; }
  .stButton>button, .stLinkButton>button {
      background-color: #FFFFFF !important;
      color: #000000 !important;
      border-radius: 12px;
      border: 1px solid #FFFFFF;
  }
  .stDataFrame thead tr th { color: #FFFFFF !important; }
  .stDataFrame tbody tr td { color: #FFFFFF !important; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =============== Helpers ===============
SEOUL_GU = [
    "강남구","강동구","강북구","강서구","관악구","광진구","구로구","금천구",
    "노원구","도봉구","동대문구","동작구","마포구","서대문구","서초구","성동구",
    "성북구","송파구","양천구","영등포구","용산구","은평구","종로구","중구","중랑구"
]

def clean_html_text(text: str) -> str:
    """HTML 태그 제거 및 텍스트 정리"""
    if not isinstance(text, str):
        return ""
    
    # HTML 태그 제거
    clean_text = re.sub(r'<[^>]+>', '', text)
    # HTML 엔티티 디코딩
    clean_text = html.unescape(clean_text)
    # 연속된 공백을 하나로
    clean_text = re.sub(r'\s+', ' ', clean_text)
    # 앞뒤 공백 제거
    clean_text = clean_text.strip()
    
    return clean_text

def parse_structured_data(data_str: str) -> List[Dict]:
    """
    {PERFORM_IDX=36534, DISCOUNT_NAME=장애인(1~3급), DISCOUNT_PERCENT=50} 형태의 
    구조화된 데이터를 파싱
    """
    if not isinstance(data_str, str) or not data_str.strip():
        return []
    
    items = []
    # {} 블록 찾기
    blocks = re.findall(r'\{[^}]+\}', data_str)
    
    for block in blocks:
        # {} 제거
        content = block.strip('{}')
        item = {}
        
        # key=value 쌍 파싱
        pairs = re.findall(r'(\w+)=([^,}]+)', content)
        for key, value in pairs:
            item[key.strip()] = value.strip()
        
        if item:
            items.append(item)
    
    return items

def extract_discount_info(discount_data: List[Dict]) -> Dict[str, int]:
    """할인 정보에서 카테고리별 최대 할인율 추출"""
    category_map = {
        "청소년": "youth",
        "학생": "student", 
        "경로": "senior",
        "장애": "disabled",
        "국가유공자": "veteran",
        "세종S멤버십": "membership",
        "다둥이": "family"
    }
    
    discount_map = {}
    
    for item in discount_data:
        discount_name = item.get("DISCOUNT_NAME", "")
        discount_percent = item.get("DISCOUNT_PERCENT", "0")
        
        try:
            percent = int(discount_percent)
        except (ValueError, TypeError):
            continue
            
        # 카테고리 매칭
        for keyword, category in category_map.items():
            if keyword in discount_name:
                discount_map[category] = max(discount_map.get(category, 0), percent)
                break
    
    return discount_map

def extract_seat_info(seat_data: List[Dict]) -> str:
    """좌석 정보를 문자열로 변환"""
    if not seat_data:
        return "정보 없음"
    
    seat_info_list = []
    for item in seat_data:
        rating = item.get("SEAT_RATING", "")
        price = item.get("SEAT_PRICE", "")
        if rating and price:
            seat_info_list.append(f"{rating}: {price}")
    
    return " | ".join(seat_info_list) if seat_info_list else "정보 없음"

def best_applicable_discount(
    age: int,
    is_seoul: bool,
    rewatch: bool,
    has_student: bool,
    has_senior: bool,
    has_military: bool,
    has_disabled: bool,
    has_munhwa: bool,
    csv_discount_map: Dict[str, int],
) -> Tuple[int, str]:
    """적용 가능한 할인 중 최대 할인율 선택"""
    candidates = []
    
    # 나이 기반 할인
    if age <= 24:
        youth_discount = csv_discount_map.get("youth", 0)
        if youth_discount > 0:
            candidates.append((youth_discount, "청소년 할인"))
    
    if age >= 65:
        senior_discount = csv_discount_map.get("senior", 0)
        if senior_discount > 0:
            candidates.append((senior_discount, "경로 우대"))
    
    # 자격 기반 할인
    if has_student:
        student_discount = max(csv_discount_map.get("youth", 0), csv_discount_map.get("student", 0))
        if student_discount > 0:
            candidates.append((student_discount, "학생 할인"))
    
    if has_disabled:
        disabled_discount = csv_discount_map.get("disabled", 0)
        if disabled_discount > 0:
            candidates.append((disabled_discount, "장애인 할인"))
    
    if has_military:
        veteran_discount = csv_discount_map.get("veteran", 0)
        if veteran_discount > 0:
            candidates.append((veteran_discount, "국가유공자 할인"))
    
    # 멤버십 할인
    membership_discount = csv_discount_map.get("membership", 0)
    if membership_discount > 0:
        candidates.append((membership_discount, "세종S멤버십"))
    
    # 기타 할인
    if is_seoul:
        family_discount = csv_discount_map.get("family", 0)
        if family_discount > 0:
            candidates.append((family_discount, "다둥이카드"))
    
    if not candidates:
        return 0, "적용 가능 할인 없음"
    
    return max(candidates, key=lambda x: x[0])

# =============== Data Load ===============
def load_data() -> pd.DataFrame:
    """CSV 파일 로드 및 전처리"""
    here = Path(__file__).resolve().parent
    local_csv = here / "OA-2708.csv"

    df = None
    successful_encoding = None
    
    if local_csv.exists():
        st.info(f"로컬 파일 발견: {local_csv}")
        # 더 많은 인코딩 시도
        encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16", "ansi"]
        
        for enc in encodings:
            try:
                df = pd.read_csv(local_csv, encoding=enc)
                successful_encoding = enc
                st.success(f"파일 로드 성공! 인코딩: {enc}, 행 수: {len(df)}")
                break
            except Exception as e:
                st.warning(f"인코딩 {enc} 실패: {str(e)}")
                continue
    
    if df is None:
        st.info("로컬에서 OA-2708.csv를 찾지 못했습니다. 파일을 업로드해주세요.")
        uploaded = st.file_uploader("OA-2708.csv 업로드", type=["csv"])
        if uploaded:
            encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "utf-16"]
            for enc in encodings:
                try:
                    df = pd.read_csv(uploaded, encoding=enc)
                    successful_encoding = enc
                    st.success(f"업로드 파일 로드 성공! 인코딩: {enc}, 행 수: {len(df)}")
                    break
                except Exception as e:
                    st.warning(f"인코딩 {enc} 실패: {str(e)}")
                    continue
    
    if df is None:
        st.error("CSV 파일을 로드할 수 없습니다.")
        return pd.DataFrame()

    st.info(f"원본 데이터: {len(df)} 행, 열: {list(df.columns)}")
    df = df.fillna("")

    # 열이름 매핑 - 위치 기반과 이름 기반 둘 다 시도
    original_columns = list(df.columns)
    
    # 예상되는 열 순서 (CSV 파일 구조 기반)
    expected_columns = [
        "공연ID", "장르", "공연명", "시작일", "종료일", "공연장소", 
        "러닝타임", "인터미션", "관람연령", "기획사", "문의전화", 
        "시놉시스", "작품소개", "출연진", "제작진", "할인정보", 
        "자리정보", "예매URL", "포스터URL"
    ]
    
    # 열 개수가 맞으면 위치 기반 매핑 시도
    if len(original_columns) == len(expected_columns):
        st.info("위치 기반 열 매핑 시도...")
        df.columns = expected_columns
        st.success(f"위치 기반 매핑 완료: {list(df.columns)}")
    else:
        # 이름 기반 매핑
        colmap = {
            "공연 고유번호": "공연ID",
            "공연 장르명": "장르", 
            "공연명": "공연명",
            "공연 시작일자": "시작일",
            "공연 종료일자": "종료일",
            "공연 장소목록": "공연장소",
            "공연시간 - 러닝타임": "러닝타임",
            "공연시간 - 인터미션": "인터미션",
            "관람연령 - 나이": "관람연령",
            "기획사": "기획사",
            "문의전화": "문의전화",
            "공연 시놉시스": "시놉시스",
            "공연 작품소개": "작품소개",
            "출연진소개 에디터": "출연진",
            "제작진소개 에디터": "제작진",
            "공연할인정보": "할인정보",
            "공연자리정보": "자리정보",
            "공연상세 URL": "예매URL",
            "공연 포스터 사진 URL": "포스터URL",
        }
        
        existing_cols = [k for k in colmap.keys() if k in df.columns]
        st.info(f"이름 기반 매핑할 열: {existing_cols}")
        
        if existing_cols:
            df = df.rename(columns={k: v for k, v in colmap.items() if k in df.columns})
            st.success(f"이름 기반 매핑 완료: {list(df.columns)}")
        else:
            st.warning("열 이름 매핑 실패. 원본 열 이름 사용.")

    # 공연기간 합성
    if "시작일" in df.columns and "종료일" in df.columns:
        df["공연기간"] = df["시작일"].astype(str) + " ~ " + df["종료일"].astype(str)
        st.info("공연기간 열 생성 완료")
    
    # 구조화된 데이터 파싱
    if "할인정보" in df.columns:
        st.info("할인정보 파싱 시작...")
        df["_parsed_discounts"] = df["할인정보"].apply(lambda x: parse_structured_data(str(x)))
        df["_discount_map"] = df["_parsed_discounts"].apply(extract_discount_info)
        st.info("할인정보 파싱 완료")
    else:
        st.warning("할인정보 열이 없습니다.")
        df["_parsed_discounts"] = [[] for _ in range(len(df))]
        df["_discount_map"] = [{} for _ in range(len(df))]
    
    if "자리정보" in df.columns:
        st.info("좌석정보 파싱 시작...")
        df["_parsed_seats"] = df["자리정보"].apply(lambda x: parse_structured_data(str(x)))
        df["_seat_display"] = df["_parsed_seats"].apply(extract_seat_info)
        st.info("좌석정보 파싱 완료")
    else:
        st.warning("자리정보 열이 없습니다.")
        df["_parsed_seats"] = [[] for _ in range(len(df))]
        df["_seat_display"] = ["정보 없음"] * len(df)
    
    # HTML 텍스트 정리
    for col in ["시놉시스", "작품소개", "출연진", "제작진"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_html_text)
    
    st.success(f"데이터 전처리 완료! 최종 행 수: {len(df)}")
    return df

# =============== Screens ===============
def screen1():
    st.markdown("<h1 style='text-align:center;'>PDI</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>Provide Discount Information</h3>", unsafe_allow_html=True)
    st.write("")
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        if st.button("정보 등록", use_container_width=True):
            st.session_state["screen"] = "profile"

def screen2(df: pd.DataFrame):
    if df is None or df.empty:
        st.warning("CSV를 로드하지 못했습니다. OA-2708.csv를 같은 폴더에 두거나 업로드하세요.")
        return

    # 디버깅 정보 표시
    with st.expander("🔍 데이터 디버깅 정보", expanded=False):
        st.write(f"**데이터프레임 크기**: {len(df)} 행, {len(df.columns)} 열")
        st.write(f"**열 이름**: {list(df.columns)}")
        if len(df) > 0:
            st.write("**첫 번째 행 샘플**:")
            st.write(df.iloc[0].to_dict())
        
        # 할인 정보 파싱 테스트
        if "할인정보" in df.columns and len(df) > 0:
            st.write("**할인정보 파싱 테스트**:")
            sample_discount = df.iloc[0]["할인정보"]
            st.write(f"원본 할인정보: {sample_discount}")
            parsed = parse_structured_data(str(sample_discount))
            st.write(f"파싱된 할인정보: {parsed}")
            discount_map = extract_discount_info(parsed)
            st.write(f"할인 맵: {discount_map}")

    st.markdown("### 이용자 정보 입력")
    c1, c2, c3, c4 = st.columns([1,1,1,1])
    with c1: age = st.number_input("나이", 0, 120, 24, 1)
    with c2: seoul_gu = st.selectbox("거주지(서울시 구)", ["비서울 거주"] + SEOUL_GU, index=0)
    with c3: rewatch = st.checkbox("세종문화회관 재관람", False)
    with c4: show_all = st.toggle("모두 보기", False, help="체크 시, 할인 미적용 공연도 함께 표시")

    st.markdown("---")
    st.markdown("#### 추가 자격 체크")
    c5, c6, c7, c8, c9 = st.columns(5)
    with c5: is_student = st.checkbox("학생", age <= 24)
    with c6: is_senior = st.checkbox("경로", age >= 65)
    with c7: is_military = st.checkbox("군인/국가유공자", False)
    with c8: is_disabled = st.checkbox("장애인", False)
    with c9: has_munhwa = st.checkbox("문화누리카드", False)

    # 공연 목록 생성
    preview = []
    st.write(f"**처리할 공연 수**: {len(df)}")  # 디버깅용
    
    for idx, row in df.iterrows():
        discount_map = row.get("_discount_map", {})
        pct, reason = best_applicable_discount(
            age=age,
            is_seoul=(seoul_gu in SEOUL_GU),
            rewatch=rewatch,
            has_student=is_student,
            has_senior=is_senior,
            has_military=is_military,
            has_disabled=is_disabled,
            has_munhwa=has_munhwa,
            csv_discount_map=discount_map,
        )
        
        # 디버깅: 첫 번째 공연 정보 출력
        if idx == 0:
            st.write(f"**첫 번째 공연 처리 결과**: 할인율 {pct}%, 사유: {reason}")
        
        # show_all이 True이거나 할인이 있는 경우만 표시
        if show_all or pct > 0:
            preview.append({
                "공연ID": row.get("공연ID", "정보없음"),
                "공연명": row.get("공연명", "정보없음"),
                "장르": row.get("장르", "정보없음"),
                "공연장소": row.get("공연장소", "정보없음"),
                "공연기간": row.get("공연기간", "정보없음"),
                "좌석정보": row.get("_seat_display", "정보 없음"),
                "할인율(%)": pct,
                "할인사유": reason if pct > 0 else "해당 없음",
            })
    
    st.write(f"**표시할 공연 수**: {len(preview)}")  # 디버깅용

    result = pd.DataFrame(preview)
    
    if not result.empty:
        result = result.sort_values(by=["할인율(%)","공연명"], ascending=[False, True])
        
        st.markdown("#### 📋 공연 목록")
        st.dataframe(result, use_container_width=True, hide_index=True)
        
        # 할인 상세 정보
        st.markdown("#### 💰 할인 상세 정보")
        discount_details = []
        for _, row in df.iterrows():
            parsed_discounts = row.get("_parsed_discounts", [])
            if parsed_discounts:
                discount_text = ", ".join([
                    f"{item.get('DISCOUNT_NAME', '')}: {item.get('DISCOUNT_PERCENT', '')}%" 
                    for item in parsed_discounts
                ])
                discount_details.append({
                    "공연명": row.get("공연명", ""),
                    "할인 정보": discount_text
                })
        
        if discount_details:
            with st.expander("전체 할인 정보 보기", expanded=False):
                discount_df = pd.DataFrame(discount_details)
                st.dataframe(discount_df, use_container_width=True, hide_index=True)
    else:
        st.info("조건에 맞는 공연이 없습니다.")

    # 상세보기 선택
    if not result.empty:
        st.markdown("---")
        st.markdown("#### 🔍 상세보기")
        options = []
        for _, r in result.iterrows():
            label = f"{r['공연명']} | {r['공연장소']} | {r['할인율(%)']}% 할인"
            options.append((label, r["공연ID"]))
        
        if options:
            labels = [x[0] for x in options]
            sel = st.selectbox("공연을 선택하세요", ["선택 안 함"] + labels, index=0)
            if sel != "선택 안 함":
                st.session_state["detail_id"] = dict(options)[sel]
                st.session_state["profile_snapshot"] = {
                    "age": age,
                    "seoul": (seoul_gu in SEOUL_GU),
                    "rewatch": rewatch,
                    "student": is_student,
                    "senior": is_senior,
                    "military": is_military,
                    "disabled": is_disabled,
                    "munhwa": has_munhwa,
                }
                st.session_state["screen"] = "detail"

def screen3(df: pd.DataFrame):
    if df is None or df.empty:
        st.warning("공연 정보를 표시하려면 CSV를 먼저 로드해야 합니다.")
        if st.button("목록으로", use_container_width=True):
            st.session_state["screen"] = "profile"
        return

    st.markdown("### 🎭 공연 상세")
    show_id = st.session_state.get("detail_id")
    prof = st.session_state.get("profile_snapshot", {})
    
    if show_id is None or not prof:
        st.warning("상세보기를 위해 화면2에서 공연을 선택해주세요.")
        if st.button("돌아가기"):
            st.session_state["screen"] = "profile"
        return

    sub = df[df["공연ID"] == show_id].copy()
    if sub.empty:
        st.info("선택한 공연 정보를 찾을 수 없습니다.")
        if st.button("목록으로"):
            st.session_state["screen"] = "profile"
        return

    r = sub.iloc[0].to_dict()
    discount_map = r.get("_discount_map", {})

    pct, reason = best_applicable_discount(
        age=prof.get("age", 0),
        is_seoul=prof.get("seoul", False),
        rewatch=prof.get("rewatch", False),
        has_student=prof.get("student", False),
        has_senior=prof.get("senior", False),
        has_military=prof.get("military", False),
        has_disabled=prof.get("disabled", False),
        has_munhwa=prof.get("munhwa", False),
        csv_discount_map=discount_map,
    )

    # 메인 정보 섹션
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 📋 기본 정보")
        st.write(f"**공연ID**: {r.get('공연ID','')}")
        st.write(f"**공연명**: {r.get('공연명','')}")
        st.write(f"**장르**: {r.get('장르','')}")
        st.write(f"**공연기간**: {r.get('공연기간','')}")
        st.write(f"**공연장소**: {r.get('공연장소','')}")
        st.write(f"**관람연령**: {r.get('관람연령','')}")
        st.write(f"**러닝타임**: {r.get('러닝타임','')}분")
        st.write(f"**인터미션**: {r.get('인터미션','')}분")
        st.write(f"**기획사**: {r.get('기획사','')}")
        st.write(f"**문의전화**: {r.get('문의전화','')}")
    
    with col2:
        st.markdown("#### 💰 할인 정보")
        if pct > 0:
            st.success(f"**할인율**: {pct}%")
            st.info(f"**할인사유**: {reason}")
        else:
            st.warning("적용 가능한 할인 없음")

    # 좌석/가격 정보
    seat_display = r.get("_seat_display", "정보 없음")
    if seat_display != "정보 없음":
        st.markdown("---")
        st.markdown("#### 🪑 좌석 및 가격 정보")
        st.write(seat_display)

    # 전체 할인 정보
    parsed_discounts = r.get("_parsed_discounts", [])
    if parsed_discounts:
        st.markdown("---")
        st.markdown("#### 💳 전체 할인 정보")
        for item in parsed_discounts:
            discount_name = item.get("DISCOUNT_NAME", "")
            discount_percent = item.get("DISCOUNT_PERCENT", "")
            st.write(f"• {discount_name}: {discount_percent}%")

    # 시놉시스/작품소개
    synopsis = r.get("시놉시스", "")
    description = r.get("작품소개", "")
    detail_text = synopsis or description
    
    if detail_text:
        st.markdown("---")
        st.markdown("#### 📖 작품 소개")
        st.write(detail_text)

    # 출연진/제작진 정보
    cast_info = r.get("출연진", "")
    crew_info = r.get("제작진", "")
    
    if cast_info or crew_info:
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        if cast_info:
            with col1:
                st.markdown("#### 🎭 출연진")
                st.write(cast_info)
        
        if crew_info:
            with col2:
                st.markdown("#### 👥 제작진")
                st.write(crew_info)

    # 예매 URL
    url = r.get("예매URL", "")
    st.markdown("---")
    if url and (url.startswith("http://") or url.startswith("https://")):
        st.link_button("🎫 예매 페이지로 이동", url, use_container_width=True)
    else:
        st.info("예매 URL이 제공되지 않았습니다.")

    st.write("")
    if st.button("⬅️ 목록으로", use_container_width=True):
        st.session_state["screen"] = "profile"

# =============== Router ===============
df = load_data()
if "screen" not in st.session_state:
    st.session_state["screen"] = "welcome"

if st.session_state["screen"] == "welcome":
    screen1()
elif st.session_state["screen"] == "profile":
    screen2(df)
elif st.session_state["screen"] == "detail":
    screen3(df)
else:
    screen1()