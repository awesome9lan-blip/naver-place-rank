import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

# ----------------------------------------------------------------
# 1. 폰트 및 설정 (리눅스 서버용 한글 처리)
# ----------------------------------------------------------------
import platform
system_name = platform.system()

if system_name == 'Windows':
    plt.rc('font', family='Malgun Gothic')
else:
    # 스트림릿 클라우드(리눅스) 등에서 한글 깨짐 방지
    plt.rcParams['font.family'] = 'NanumGothic'

plt.rcParams['axes.unicode_minus'] = False

# ----------------------------------------------------------------
# 2. 크롤링 핵심 로직 (GUI 코드 제거 후 순수 로직만 추출)
# ----------------------------------------------------------------
def get_naver_place_rank(keyword, store_name, search_type):
    # 웹 환경에 맞는 크롬 옵션 설정 (창 안뜨게 설정)
    options = Options()
    options.add_argument('--headless')  # 창 없는 모드
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    driver = webdriver.Chrome(options=options)
    
    result_data = [] # 결과를 담을 리스트
    status_text = st.empty() # 진행상황 표시용
    
    try:
        # URL 설정
        if search_type == "음식점":
            url = f"https://m.place.naver.com/restaurant/list?query={keyword}"
        else:
            url = f"https://m.place.naver.com/place/list?query={keyword}"
            
        driver.get(url)
        status_text.info(f"'{keyword}' 검색 시작... 페이지 로딩 중")
        time.sleep(3) # 로딩 대기

        # 목록보기 버튼 찾기 및 클릭 (축약됨)
        try:
            list_buttons = driver.find_elements(By.CSS_SELECTOR, 'a.AtjOO[role="button"]')
            list_btn = None
            for btn in list_buttons:
                if "목록" in btn.text:
                    list_btn = btn
                    break
            
            if not list_btn:
                # Xpath로 재시도
                try:
                    list_btn = driver.find_element(By.XPATH, "//a[contains(text(), '목록')]")
                except:
                    pass

            if list_btn:
                driver.execute_script("arguments[0].click();", list_btn)
                time.sleep(2)
        except:
            pass # 바로 목록이 나오는 경우도 있음

        # 스크롤 로직 (간소화)
        status_text.info("순위 확인을 위해 스크롤 중입니다... (최대 100위까지)")
        
        # 바디 클릭해서 포커스
        driver.find_element(By.TAG_NAME, "body").click()
        
        found_rank = None
        found_reviews = 0
        
        # 최대 10번 스크롤 (약 100위 정도까지 체크)
        for scroll_cnt in range(15):
            items = driver.find_elements(By.CSS_SELECTOR, 'li.UEzoS, li.VLTHu')
            
            for idx, item in enumerate(items):
                try:
                    # 텍스트 추출
                    text = item.text
                    
                    # 업체명 찾기
                    if store_name in text:
                        # 광고인지 체크 (data-laim-exp-id 등)
                        is_ad = False
                        try:
                            if "*e" in item.get_attribute("data-laim-exp-id"): is_ad = True
                        except: pass
                        
                        if is_ad: continue # 광고면 패스

                        # 순위 확정 (인덱스는 0부터 시작하므로 +1)
                        found_rank = idx + 1
                        
                        # 리뷰수 추출
                        import re
                        match = re.search(r'리뷰\s*([\d,]+)', text)
                        if match:
                            found_reviews = int(match.group(1).replace(',', ''))
                        
                        break
                except:
                    continue
            
            if found_rank:
                break
                
            # 못 찾았으면 스크롤 다운
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
            time.sleep(1.5)
            
        return found_rank, found_reviews

    except Exception as e:
        st.error(f"에러 발생: {e}")
        return None, 0
    finally:
        driver.quit()

# ----------------------------------------------------------------
# 3. Streamlit 웹 화면 구성 (여기가 워드프레스에 보일 화면)
# ----------------------------------------------------------------
st.title("🔍 네이버 플레이스 순위 찾기")

with st.form("search_form"):
    col1, col2 = st.columns(2)
    with col1:
        keyword = st.text_input("검색 키워드", placeholder="예: 강남역 맛집")
    with col2:
        store_name = st.text_input("우리 가게 이름", placeholder="예: 맛있는파스타")
        
    search_type = st.radio("검색 타입", ["음식점", "일반키워드"], horizontal=True)
    
    submit_btn = st.form_submit_button("순위 확인하기")

if submit_btn:
    if not keyword or not store_name:
        st.warning("키워드와 업체명을 모두 입력해주세요.")
    else:
        with st.spinner('네이버 플레이스를 검색하고 있습니다... 잠시만 기다려주세요.'):
            rank, reviews = get_naver_place_rank(keyword, store_name, search_type)
            
            st.divider()
            if rank:
                st.success(f"검색 완료! **{store_name}**의 결과입니다.")
                
                # 결과 지표 표시
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric(label="현재 순위", value=f"{rank}위")
                with m_col2:
                    st.metric(label="리뷰 수", value=f"{reviews:,}개")
                
                # 그래프 그리기 (히스토리는 DB가 필요하므로 현재는 1개 점만 표시하거나 예시로 그림)
                st.subheader("📊 순위 시각화")
                fig, ax = plt.subplots(figsize=(8, 4))
                
                # 시각적 효과를 위해 임의의 과거 데이터(예시)와 현재 데이터 연결 (실제 구현시 DB필요)
                # 여기서는 현재 값만 점으로 표시
                ax.plot([1], [rank], marker='o', markersize=15, color='#4A9EFF')
                ax.set_title(f"{keyword} - {store_name}", fontsize=15)
                ax.set_ylabel("순위 (낮을수록 좋음)")
                ax.set_ylim(rank + 10, max(1, rank - 10)) # Y축 반전 효과 및 범위 설정
                ax.set_xticks([])
                ax.grid(True, linestyle='--', alpha=0.5)
                
                st.pyplot(fig)
                
            else:
                st.error("순위권(약 100위 내)에서 업체를 찾지 못했습니다. 광고이거나 순위 밖일 수 있습니다.")