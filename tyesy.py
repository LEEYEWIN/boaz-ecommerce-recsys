2nd_project/
│
├── README.md                  # 프로젝트 설명서 (아키텍처 그림, 실행 방법 명시)
├── docker-compose.yml         # 🐳 팀원과 인프라(Kafka, Zookeeper, Redis)를 한 번에 띄우는 마법의 파일 [cite: 876, 1082]
├── .gitignore                 # GitHub에 올리지 않을 파일 목록
│
├── frontend/                  # 💻 웹페이지 (고객이 식사하는 홀)
│   ├── index.html             # 메인 화면 [cite: 876]
│   ├── detail.html            # 상품 상세 화면 [cite: 877]
│   ├── css/style.css          # 디자인(스타일시트) [cite: 877]
│   └── js/
│       ├── api.js             # 백엔드(main.py)와 통신하는 무전기 (GET 추천결과, POST 로그전송) [cite: 877]
│       └── render.js          # 화면에 상품 이미지를 예쁘게 세팅하는 로직 [cite: 877]
│
├── backend/                   # ⚙️ 백엔드 & 모델 서빙 (주방 및 매니저)
│   ├── main.py                # 🔥 FastAPI 앱 실행의 진입점 (매니저 역할)
│   ├── requirements.txt       # 백엔드 구동에 필요한 재료 목록 (fastapi, redis 등)
│   ├── .env                   # 환경변수 (비밀번호, IP 주소 보관함)
│   │
│   ├── routers/               # 매니저의 창구 (주문 받는 곳)
│   │   ├── recommend.py       # 고객이 "추천 상품 주세요" 할 때 응대하는 창구
│   │   └── log_collector.py   # 고객이 "나 이거 클릭했어" 할 때 기록하는 창구
│   │
│   ├── services/              # 매니저의 지시를 받는 실무진 (서빙 직원) [cite: 881]
│   │   ├── kafka_producer.py  # 고객 로그를 Kafka(컨베이어 벨트)로 던지는 직원 [cite: 881]
│   │   └── redis_client.py    # Redis(보온고)에서 추천 상품을 꺼내오는 직원 [cite: 881]
│   │
│   └── ml_model/              # 🧠 추천 시스템 모델 (수석 셰프) [cite: 881]
│       ├── bert4rec.py        # 모델 아키텍처 (레시피) [cite: 881]
│       ├── inference.py       # 데이터를 넣고 결과를 뽑는 추론 함수 (요리 과정) [cite: 882]
│       ├── post_process.py    # 장바구니 등 가중치를 곱해주는 후처리 로직 (마무리 플레이팅) [cite: 882]
│       ├── weights/
│       │   └── best_model.pt  # 학습이 완료된 뇌(가중치 파일) [cite: 882]
│       └── data/              # [🔥추가] 셰프가 요리할 때 참고하는 메타데이터 보관소 [cite: 1590]
│           ├── valid_articles.csv
│           ├── top_k_dict.pkl
│           └── embeddings.npy
│
└── data_pipeline/             # 🛠️ 데이터 엔지니어링 (식자재 공급 및 물류팀) [cite: 883]
    ├── requirements.txt       # 파이프라인 구동용 재료 목록 [cite: 883]
    │
    ├── streaming/             # 실시간 파이프라인 (실시간 식자재 가공)
    │   └── flink_session_job.py # 로그를 30분 단위로 묶어주는 직원 (Flink) [cite: 883, 1030]
    │
    ├── batch/                 # 심야 배치 파이프라인 (야간 재고 정리)
    │   └── batch_update.py    # 새벽 3시에 BQ에서 인기상품을 뽑아 Redis로 밀어넣는 코드 [cite: 884, 1194]
    │
    ├── tools/                 # [🔥추가] 테스트용 도구 모음
    │   └── dummy_producer.py  # 웹페이지(프론트엔드)가 없을 때, 가짜 클릭 로그를 발생시키는 테스트 파일 [cite: 1094]
    │
    └── sql/                   # [🔥추가] BigQuery 쿼리문 보관소
        └── create_price.sql   # 가격 결측치를 채우고 테이블을 만드는 SQL 코드 저장용 [cite: 1446, 1486]