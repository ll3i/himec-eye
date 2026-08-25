# HIMEC EYE — 직무별 비전 AI 관제 프로토타입

> 제1회 HIMEC AI 활용 아이디어 공모전 / **시공·품질관리** 분야 출품작
> 현장 사진 1장 → 직무별 전용 모델이 판독 → 공통 룰엔진이 근거 조항·위험도·조치를 부여

### 온라인 시연 — https://himec-eye-panel.vercel.app

| 화면 | 내용 |
|---|---|
| 관제 화면 | 현장 화면 위에 판정 결과를 직접 표시. 감시 → 스캔 → 검출 → 경보 확정 4단계 순환 |
| 현장 재현 영상 | 카메라 화면과 판독 화면을 나란히 두고 판독 과정을 재현 |
| 판독 결과 | 6개 직무 · 시험 사진 23장. 검출 항목별 신뢰도와 임계값 |
| 판정 작동 | 직무별 클래스·임계값 근거와 판정 규칙 21개 |
| 분석 리포트 | 판독 결과를 정리한 인쇄용 문서 |

판정 로직(임계값 정책 · 관계 추론 · 위험도 산정 · 근거법규 매핑)은 **파이썬 룰엔진(`src/rules.py`)과 같은 조건으로 브라우저에서 실행**됩니다.

---

## 2. 판독 항목

직무마다 전용 모델과 전용 규칙을 둡니다. 한 모델이 모든 직무를 보지 않습니다.

| 직무 | 검출 클래스 | 판정 규칙 | 클래스 |
|---|---:|---:|---|
| 안전관리 | 11 | 5 | person, helmet, no_helmet, vest, no_vest, goggles … |
| 시설·설비 관리 | 7 | 6 | corrosion, crack, cable_damage, weld_bad, weld_good, weld_defect … |
| 생산 품질검사 | 7 | 6 | ok, dry_joint, incorrect_install, board_damage, short_circuit, surface_defect … |
| 2차전지 셀 선별 | 2 | 1 | cell_ok, cell_reversed |
| 물류·운송 관리 | 6 | 2 | forklift, worker, chassis_loaded, chassis_empty, chassis_working, stacker |
| 주차 운영관리 | 3 | 1 | car, bus, truck |

판정 규칙은 모두 **근거 조항 · 위험도 4단계 · 조치사항**을 함께 갖습니다
(`src/rules.py`의 `RULES` / `DERIVED_RULES`).

관계 추론 규칙 두 가지는 단일 객체가 아니라 **객체 사이의 관계**에서 나옵니다.

- **보호구 미착용** — 작업자 박스의 머리 구간(상단 0~35%)에 안전모 박스가 30% 미만으로
  겹치면 미착용으로 추론합니다. 미착용 클래스는 착용 대비 학습 데이터가 6.3:1로 부족해
  모델 대신 규칙으로 보완한 구조입니다.
- **지게차 협착 위험** — 지게차 박스를 좌우 35%·상하 17.5% 확장한 영역에 작업자 박스가
  35% 이상 겹치면 위험으로 판정합니다. 지게차와 작업자를 각각 검출하는 것만으로는
  나오지 않는 판정입니다.

---

## 3. 데이터셋

공개 데이터셋 중 **라이선스가 명확한 것만** 선별하여 HIMEC 검측 항목 체계로 재매핑·통합했습니다.

| 태스크 | 이미지 | 어노테이션 | 클래스 |
|---|---:|---:|---:|
| safety | 2,789 | 12,544 | 11 |
| defect | 3,288 | 7,632 | 7 |
| gauge | 235 | 1,795 | 2 |
| **합계** | **6,312** | **21,971** | **20** |

### 출처 및 라이선스

| 원천 데이터셋 | 라이선스 | 매핑된 클래스 |
|---|---|---|
| `Francesco/construction-safety-gsnvb` (Roboflow-100) | CC | person, helmet, no_helmet, vest, no_vest |
| `Francesco/street-work` (Roboflow-100) | CC | cone, goggles, gloves, no_goggles, no_gloves, helmet, no_helmet |
| `Francesco/smoke-uvylj` (Roboflow-100) | CC | smoke |
| `Francesco/corrosion-bi3q3` (Roboflow-100) | CC | corrosion, crack |
| `Francesco/cable-damage` (Roboflow-100) | CC | cable_damage |
| `Francesco/wall-damage` (Roboflow-100) | CC | wall_damage |
| `rikkarth/welding-defect-object-detection` | CC0-1.0 | weld_bad, weld_good, weld_defect |
| `Francesco/gauge-u2lwv` (Roboflow-100) | CC | gauge, digit |

> Roboflow-100 데이터셋의 category index 0은 supercategory 더미 클래스이므로 매핑에서 제외 처리했습니다.
> 원천 데이터셋의 유사 클래스는 검측 실무 기준으로 통합했습니다 (예: `break`/`thunderbolt` → `cable_damage`).

---

## 4. 프로젝트 구조

```
project/
├── src/
│   ├── datasets_config.py   # 원천 데이터셋 → HIMEC 검측 클래스 매핑 정의
│   ├── collect.py           # HF parquet/YOLO → 통합 YOLO 포맷 수집기
│   ├── collect_welding.py   # 용접 데이터셋 단독 수집 (collect.py에 통합됨)
│   ├── train.py             # YOLO11 학습 (CPU 최적화)
│   ├── train_schedule.sh    # 3개 모델 순차 학습 스케줄러
│   ├── rules.py             # 검측 룰엔진 (지적사항 + 근거법규 + 임계값 정책)
│   ├── inspect_engine.py    # 판독 엔진 (3축 추론 + EXIF + 시각화)
│   ├── report.py            # 검측조서 HTML 자동생성
│   ├── followup.py          # 시정조치 이행 확인 (해소/잔존/신규 판정)
│   ├── evaluate.py          # test-set 성능 평가 → 성능 리포트
│   ├── run_demo.sh          # 판독 + 조서생성 E2E 실행
│   ├── run_all.sh           # 수집~제출물 전체 재현
│   ├── make_submission_docx.py  # 붙임4 출품작 docx 자동 작성
│   ├── make_package.py      # 제출용 ZIP 패키징
│   ├── build_artifact.py    # 제안 페이지(HTML) 빌드
│   ├── make_demo_data.py    # 시연용 원시 탐지 데이터 + 룰 정의 export
│   ├── make_demo_video.py   # 판독 과정 시연 영상(GIF) 생성
│   ├── build_demo_page.py   # 인터랙티브 시연 페이지 빌드
│   └── build_web.py         # 배포용 정적 사이트 빌드 (Vercel)
├── data/
│   ├── processed/{safety,defect,gauge}/{train,val,test}/{images,labels}
│   └── demo/                # 데모용 샘플 사진
├── runs/                    # 학습 결과 (weights, 성능지표)
├── reports/                 # 판독 결과 및 검측조서
└── docs/                    # 제안서
```

---

## 5. 실행 방법

```bash
# 1) 데이터 수집 (공개 데이터셋 → 통합 YOLO 포맷)
python src/collect.py --tasks safety defect gauge

# 2) 모델 학습
python src/train.py --task safety --epochs 50 --imgsz 416 --batch 32
python src/train.py --task defect --epochs 50 --imgsz 416 --batch 32
python src/train.py --task gauge  --epochs 40 --imgsz 416 --batch 16
#   CPU 환경에서 3개 모델을 제한 시간 안에 확보하려면:
#   bash src/train_schedule.sh 5 8 12     # safety 5ep → defect 8ep → gauge 12ep

# 3) 현장사진 판독 (학습된 태스크만 자동 로드 — 없으면 건너뜀)
python src/inspect_engine.py "data/demo/*.jpg" --out reports/out

# 4) 검측조서 생성
python src/report.py --results reports/out/results.json \
                     --site "○○ 데이터센터 신축공사" --area "지하1층 기계실"
#   또는 3)+4) 한 번에:  bash src/run_demo.sh
#   전체 재현(수집~제출물):  bash src/run_all.sh "팀명"

# 5) 성능 평가 → 제출물 생성
python src/evaluate.py --tasks safety defect gauge
python src/make_submission_docx.py          # 붙임4 출품작 docx (성능 수치 자동 반영)
python src/make_package.py --team "팀명"     # 제출용 ZIP

# 6) 시연 사이트 빌드 & 배포
python src/make_demo_data.py --conf 0.05    # 낮은 임계값으로 원시 탐지 데이터 생성
python src/make_demo_video.py               # 판독 과정 시연 영상(GIF)
python src/build_demo_page.py               # 인터랙티브 시연 페이지
python src/build_artifact.py                # 제안 페이지
python src/build_web.py                     # 3개 페이지 → web/ (완전한 HTML + 네비게이션)
cd web && vercel deploy --prod --yes
```

> `collect_welding.py`는 용접 데이터셋만 따로 받는 독립 스크립트입니다.
> 현재는 `collect.py`가 동일 로직을 포함하므로 별도 실행이 필요하지 않습니다.

### 환경

| 항목 | 값 |
|---|---|
| Python | 3.12 |
| 주요 패키지 | ultralytics 8.4, torch 2.13 (CPU), pyarrow, huggingface_hub, Pillow |
| 학습 환경 | CPU 18코어 (GPU 없이 학습·추론 가능한 경량 구성) |

> GPU 없이도 동작하도록 YOLO11n(2.6M 파라미터) / imgsz 416 구성을 사용했습니다.
> 현장 태블릿·모바일 엣지 탑재를 염두에 둔 선택입니다.

---

## 6. 한계와 다음 단계

**현재 프로토타입의 한계**

- 학습 데이터가 **공개 데이터셋 기반**이라 국내 현장 특유의 설비 사양·조도·앵글이 반영되지 않았습니다.
- MEP 설비 고유 객체(스프링클러 헤드, 케이블 트레이, 배관 지지대, 보온재)의 공개 데이터가 없어,
  현 단계에서는 부식·용접·케이블 등 **범용 하자 유형** 중심으로 구성했습니다.
- 계기 판독은 계기 위치·숫자 영역 검출까지이며, 지침값 자체의 정밀 판독(OCR)은 다음 단계입니다.

**다음 단계**

1. 사내 검측 사진 라벨링 → 파인튜닝 (도메인 갭 해소)
2. MEP 고유 객체 클래스 추가 (지지대 간격, 보온 미시공, 스프링클러 이격거리 등 **기하 규칙 판정**)
3. 계기 지침값 OCR → 설계값 대비 편차 자동 판정
4. 모바일 촬영 즉시 판독 + 오탐 신고 → 재학습 피드백 루프

---

*본 저장소는 제1회 HIMEC AI 활용 아이디어 공모전 출품용 프로토타입입니다.
판독 결과는 초안이며, 최종 판정은 감리원(책임기술자) 확인 후 확정됩니다.*
