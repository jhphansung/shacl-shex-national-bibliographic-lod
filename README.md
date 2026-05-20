# shacl-shex-national-bibliographic-lod
# SHACL과 ShEx를 활용한 국가서지 LOD의 품질 평가

본 저장소는 박진호(2026)의 학술 논문 "SHACL과 ShEx를 활용한
국가서지 LOD의 품질 평가: 온톨로지 설계 검증과 실데이터 검증의
이중 층위 분석"의 재현성 확보를 위한 부속 자료를 제공합니다.

## 연구 개요
본 연구는 국립중앙도서관 국가서지 LOD의 품질을 SHACL과 ShEx를
활용하여 설계 층위와 실데이터 층위의 양면에서 진단하였습니다.
약 9억 1,500만 트리플 전체를 전수조사하였습니다.

## 저장소 구성
- `shapes/`: SHACL 및 ShEx 형상 파일
- `scripts/`: Python 분석 스크립트
- `results/`: 분석 결과 CSV 파일
- `docs/`: 부속 문서 (부록 포함)

## 데이터 출처
본 연구의 분석 대상은 국립중앙도서관 국가서지 LOD
(https://lod.nl.go.kr) 의 2026년 4월 1일자 벌크 데이터입니다.
데이터 파일 자체는 용량 문제로 본 저장소에 포함하지 않으며,
위 URL에서 직접 내려받으실 수 있습니다.

## 실행 환경
- Python 3.13
- 필수 라이브러리: rdflib, pyshacl

설치:
\`\`\`
pip install rdflib pyshacl
\`\`\`

## 실행 순서
1. `python scripts/01_데이터규모진단.py` — 데이터셋 규모 진단
2. `python scripts/02_SHACL검증.py` — SHACL 전수 검증
3. `python scripts/03_ShEx검증.py` — ShEx 귀납 형상 추출 및 비교

각 스크립트 상단의 DATA_ROOT 변수를 본인 환경의 데이터 폴더
경로로 수정한 뒤 실행하십시오.

## 인용
이 자료를 활용하시는 경우 다음과 같이 인용해 주십시오.
박진호. (2026). SHACL과 ShEx를 활용한 국가서지 LOD의 품질 평가:
온톨로지 설계 검증과 실데이터 검증의 이중 층위 분석.
[학술지명], [권(호)], [페이지].

## 라이선스
본 저장소의 코드는 MIT License를 따릅니다.

## 문의
[이메일 주소]
