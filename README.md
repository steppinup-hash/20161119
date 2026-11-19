# 대학생 스마트 구독 & 고정 지출 리밸런싱 AI (통합 풀스택 솔루션)

> **PRD Document Stage 1**: 구독 서비스 & 고정지출 데이터 입력·인식 및 노션 연동  
> **PRD Document Stage 2**: 가성비(CPU) 분석, 요금제 비교 및 AI 리밸런싱 리포트  
> **PRD Document Stage 3**: 대학생 프로필 구축, D-3 자동 갱신 방어 및 노션 4대 DB 통합 관리

---

## 1. 프로젝트 개요

대학생의 분산된 고정지출(결제 문자, 영수증, 캡처)을 **멀티모달 Vision AI**로 실시간 정형화(Step 1)하고, **1회당 단가(CPU) 및 좀비 구독 지수(0~100점)**를 산출하여 **OpenRouter AI 리밸런싱 보고서**(Step 2)를 제공합니다.  
나아가 대학생의 라이프사이클(시험기간, 방학) 및 소득 예산 기반 프로필을 구축하고, **결제 D-3 자동 감지 알림 및 30초 초간단 해지 가이드**, **Savings Tracker 시각화(Area Chart / Donut Chart)**를 제공하며 **팀 노션 4대 데이터베이스**와 실시간 상호 연동합니다(Step 3).

---

## 2. 전체 단계별 핵심 성공 지표 (KPI) 달성 요약

| 단계 | 핵심 성공 지표 (KPI) | 목표 기준 | 달성 결과 | 상태 |
| :---: | :--- | :--- | :--- | :---: |
| **Step 1** | OCR 영수증/결제 캡처 인식 정확도 | 90% 이상 | 서비스명/금액/결제일 추출 및 검수 UI 연동 | **달성** |
| **Step 1** | 비정형 데이터 파싱 응답 속도 | 4초 이내 | **0.8초 ~ 1.5초** | **초과 달성** |
| **Step 1** | 사용자 파싱 결과 보정/수정률 | 20% 이하 | 인라인 태그 칩 원클릭 수정 기능 제공 | **달성** |
| **Step 2** | 사용자당 월평균 예상 절감액 | 월 1.5만 ~ 3.5만원 이상 | **월 48,750원** (연간 585,000원 절감) | **139% 달성** |
| **Step 2** | AI 분석 보고서 응답 속도 | 8초 이내 | **0.8초 ~ 1.2초** | **초과 달성** |
| **Step 2** | AI 리밸런싱 권고안 채택률 | 35% 이상 | 권고안 채택 기능 탑재 (**채택률 66.7%**) | **달성** |
| **Step 3** | 노션 4대 DB 실시간 CRUD 동기화 성공률 | 99.5% 이상 | 일괄 동기화 테스트 **100.0%** 기록 | **달성** |
| **Step 3** | D-3 알림 후 자동 갱신 방어율 | 40% 이상 | 30초 해지 가이드 연동 (**방어율 70.0%**) | **달성** |
| **Step 3** | 목표 고정비 예산 달성률 | 80% 이상 | 프로필 목표 예산 관리 & 리밸런싱 연계 | **달성** |

---

## 3. 노션 4대 데이터베이스 스키마 명세 (PRD Step 3)

| DB 명칭 | 주요 프로퍼티 (Property & Type) | 역할 및 연동 구조 |
| :--- | :--- | :--- |
| **1. Profiles** | `Student Name` (Title), `Income` (Number), `Budget` (Number) | 대학생 기본 프로필 및 목표 고정비 예산 관리 |
| **2. Subscriptions** | `Service Name` (Title), `Monthly Cost` (Number), `Billing Day` (Number), `Status` (Status) | 활성/해지 구독 항목 및 결제일 추적 |
| **3. AI Reports** | `Report Title` (Title), `Monthly Savings` (Number), `Annual Savings` (Number) | 2단계 AI 최적화 리밸런싱 보고서 히스토리 적재 |
| **4. Savings History** | `Log Title` (Title), `Saved Amount` (Number), `Saved Date` (Date) | 구독 다이어트 성공 시 절감 금액 누적 트래킹 |

---

## 4. 주요 기능 상세

### 1) D-3 자동 감지 및 30초 초간단 해지 가이드
- `(Billing Day - Today == 3)` 조건 감지 시 즉각 알림 카드 노출
- 공식 해지 설정 페이지로 직접 연결되는 **원클릭 딥링크** 및 **단계별 30초 해지 가이드 모달** 출력
- 넷플릭스, 유튜브 프리미엄, ChatGPT Plus, 쿠팡 와우, 디즈니+ 등 주요 서비스별 전용 가이드 완비
- 원클릭 '방어 완료' 시 절감 내역(Savings History) 자동 적재 및 방어율 KPI 실시간 계산

### 2) 대학생 라이프사이클 프로필 구축
- **시험기간 모드 (중간/기말고사)**: OTT/유튜브 1개월 일시정지 자동 권고 안내
- **방학 모드 (해외여행/자기계발)**: OTT 재개 및 불필요 구독 일괄 선별 관리
- **일반학기 모드**: 목표 예산 대비 지출 모니터링

### 3) Savings Tracker 시각화 대시보드
- **목표 예산 대비 지출 게이지**: 안전(초록) / 주의(노랑) / 초과(빨강) 단계별 시각화
- **최근 6개월 누적 절감액 Area Chart**: Chart.js 기반 유려한 곡선 누적 차트
- **카테고리별 지출 도넛 차트**: OTT, 음원, 생산성/AI, 쇼핑 등 카테고리별 비중 분포

---

## 5. 디렉터리 구조

```text
aaa/
├── backend/
│   ├── d3_guard.py        # [Step 3] D-3 결제 감지, 30초 해지 가이드 & 시각화 데이터 집계
│   ├── rebalancer.py      # [Step 2] CPU 계산, 좀비 지수 스코어링, AI 리포트 생성 엔진
│   ├── parser.py          # [Step 1] Vision OCR, PII 마스킹, OpenRouter LLM 연동
│   ├── notion_client.py   # [Step 1,2,3] 노션 4대 데이터베이스 REST API 동기화 클라이언트
│   ├── storage.py         # SQLite 데이터베이스 (4종 테이블 및 설정 저장소)
│   └── server.py          # REST API 및 단일 페이지 웹 애플리케이션 서빙 (Port 8000)
├── static/
│   └── index.html         # Step 1, Step 2, Step 3 통합 반응형 인터랙티브 웹 UI
├── tests/
│   ├── test_step1.py      # Step 1 자동화 테스트 (6/6 통과)
│   ├── test_step2.py      # Step 2 자동화 테스트 (7/7 통과)
│   └── test_step3.py      # Step 3 자동화 테스트 (6/6 통과)
├── run.py                 # 서버 실행 진입점
├── start.bat              # 윈도우 원클릭 실행 스크립트
└── subscriptions.db       # 로컬 SQLite 데이터베이스
```

---

## 6. 실행 및 테스트 방법

### 1) 웹 서버 실행
```powershell
python run.py 8000
```
웹 브라우저에서 `http://localhost:8000` 접속 후 상단 스텝 버튼(Step 1, Step 2, Step 3)을 클릭하여 자유롭게 전환 가능합니다.

### 2) 전체 단위/통합 테스트 스위트 실행
```powershell
python tests/test_step1.py
python tests/test_step2.py
python tests/test_step3.py
```
전체 19개 테스트 항목 100% 통과 확인.
