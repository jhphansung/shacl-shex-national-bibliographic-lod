# -*- coding: utf-8 -*-
"""
국가서지 LOD SHACL 전수 검증 스크립트
연구: SHACL과 ShEx를 활용한 국가서지 LOD 품질 평가

[기능]
 - D:\데이터 하위 6개 폴더의 모든 JSON-LD 파일을 파일 단위로 스트리밍 검증
 - 9억 트리플 규모를 메모리 제약 없이 처리 (파일별 처리 후 그래프 해제)
 - 클래스별 적합률, 속성별 위반 빈도, 위반 유형별 분포 산출
 - 동일 의미 속성의 표기 분산(creator, language 등)을 통합 처리한 형상 적용
 - 결과를 CSV로 저장하여 논문 6.4절 작성에 활용

[실행 전 준비]
 pip install pyshacl rdflib
"""

import os
import csv
import json
import glob
import gc
from collections import defaultdict, Counter
from datetime import datetime

from rdflib import Graph, Namespace, RDF
from pyshacl import validate

# ============================================================
# 사용자 환경 설정
# ============================================================
DATA_ROOT = r"D:\데이터"
OUTPUT_DIR = os.path.join(DATA_ROOT, "_분석결과")
SHAPES_FILE = os.path.join(OUTPUT_DIR, "shacl_shapes.ttl")

FOLDERS = {
    "기타-도서관정보": "기타도서관정보Library_json_20260401",
    "서지-오프라인자료": "서지데이터오프라인자료Offline_json_20260401",
    "서지-온라인자료": "서지데이터온라인자료Online_json_20260401",
    "전거-개인명": "전거데이터개인명Person_json_20260401",
    "전거-단체명": "전거데이터단체명Organization_json_20260401",
    "전거-주제명": "전거데이터주제명Concept_json_20260401",
}

SH = Namespace("http://www.w3.org/ns/shacl#")

# ============================================================
# SHACL 형상 정의
#  - 5장 연역적 설계 + 6.2절 실데이터 기반 보완을 통합
#  - 검증 대상: 실데이터에 출현하는 31종 클래스
#  - 동일 의미 속성의 표기 분산을 sh:or 로 통합 처리
# ============================================================
SHACL_SHAPES = r"""
@prefix sh:      <http://www.w3.org/ns/shacl#> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix nlon:    <http://lod.nl.go.kr/ontology/> .
@prefix bibo:    <http://purl.org/ontology/bibo/> .
@prefix foaf:    <http://xmlns.com/foaf/0.1/> .
@prefix dc:      <http://purl.org/dc/elements/1.1/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix ex:      <http://example.org/nlk-shapes/> .

# -----------------------------------------------------------
# 공통 부품: 표제(title) 필수 - 표기 분산 통합
#  dc:title, dcterms:title, title 형태를 모두 허용
# -----------------------------------------------------------
ex:TitleConstraint a sh:PropertyShape ;
    sh:path [ sh:alternativePath (
        dc:title
        dcterms:title
        <http://purl.org/dc/elements/1.1/title>
        <http://purl.org/dc/terms/title>
    ) ] ;
    sh:minCount 1 ;
    sh:name "표제" ;
    sh:message "표제(title)가 누락되었습니다 (KORMARC 245 / RDA 핵심요소)." .

# ===========================================================
# 1. 자료 유형 클래스 (상위 + 하위)
# ===========================================================

ex:OfflineMaterialShape a sh:NodeShape ;
    sh:targetClass nlon:OfflineMaterial ;
    sh:property ex:TitleConstraint .

ex:OnlineMaterialShape a sh:NodeShape ;
    sh:targetClass nlon:OnlineMaterial ;
    sh:property ex:TitleConstraint .

ex:BookShape a sh:NodeShape ;
    sh:targetClass nlon:Book ;
    sh:property ex:TitleConstraint ;
    sh:property [
        sh:path nlon:kdc ;
        sh:datatype xsd:string ;
        sh:pattern "^[0-9]{3}(\\.[0-9]+)?$" ;
        sh:name "한국십진분류" ;
        sh:severity sh:Warning ;
        sh:message "KDC 분류기호 형식이 올바르지 않습니다." ;
    ] ;
    sh:property [
        sh:path nlon:isbn ;
        sh:datatype xsd:string ;
        sh:pattern "^(97[89])?[0-9]{9}[0-9Xx]$" ;
        sh:name "ISBN" ;
        sh:severity sh:Warning ;
        sh:message "ISBN 형식이 올바르지 않습니다." ;
    ] .

ex:NonBookShape a sh:NodeShape ;
    sh:targetClass nlon:NonBook ;
    sh:property ex:TitleConstraint .

ex:OldBookShape a sh:NodeShape ;
    sh:targetClass nlon:OldBook ;
    sh:property ex:TitleConstraint .

ex:ElectronicBookShape a sh:NodeShape ;
    sh:targetClass nlon:ElectronicBook ;
    sh:property ex:TitleConstraint .

ex:ElectronicJournalShape a sh:NodeShape ;
    sh:targetClass nlon:ElectronicJournal ;
    sh:property ex:TitleConstraint .

ex:VideoDocumentShape a sh:NodeShape ;
    sh:targetClass nlon:VideoDocument ;
    sh:property ex:TitleConstraint .

ex:SoundShape a sh:NodeShape ;
    sh:targetClass nlon:Sound ;
    sh:property ex:TitleConstraint .

ex:ScoreShape a sh:NodeShape ;
    sh:targetClass nlon:Score ;
    sh:property ex:TitleConstraint .

ex:AlternativeMaterialShape a sh:NodeShape ;
    sh:targetClass nlon:AlternativeMaterial ;
    sh:property ex:TitleConstraint .

ex:DigitalizedScoreShape a sh:NodeShape ;
    sh:targetClass nlon:DigitalizedScore ;
    sh:property ex:TitleConstraint .

ex:ElectronicDocumentShape a sh:NodeShape ;
    sh:targetClass nlon:ElectronicDocument ;
    sh:property ex:TitleConstraint .

ex:MapShape a sh:NodeShape ;
    sh:targetClass nlon:Map ;
    sh:property ex:TitleConstraint .

ex:DigitalizedMapShape a sh:NodeShape ;
    sh:targetClass nlon:DigitalizedMap ;
    sh:property ex:TitleConstraint .

ex:SoftwareShape a sh:NodeShape ;
    sh:targetClass nlon:Software ;
    sh:property ex:TitleConstraint .

ex:ComplexDocumentShape a sh:NodeShape ;
    sh:targetClass nlon:ComplexDocument ;
    sh:property ex:TitleConstraint .

# ===========================================================
# 2. BIBO 외부 어휘 클래스 (실데이터 직접 선언분)
# ===========================================================

ex:BiboBookShape a sh:NodeShape ;
    sh:targetClass bibo:Book ;
    sh:property ex:TitleConstraint .

ex:BiboThesisShape a sh:NodeShape ;
    sh:targetClass bibo:Thesis ;
    sh:property ex:TitleConstraint .

ex:BiboArticleShape a sh:NodeShape ;
    sh:targetClass bibo:Article ;
    sh:property ex:TitleConstraint .

ex:BiboWebsiteShape a sh:NodeShape ;
    sh:targetClass bibo:Website ;
    sh:property ex:TitleConstraint .

ex:BiboImageShape a sh:NodeShape ;
    sh:targetClass bibo:Image ;
    sh:property ex:TitleConstraint .

ex:BiboAudioDocumentShape a sh:NodeShape ;
    sh:targetClass bibo:AudioDocument ;
    sh:property ex:TitleConstraint .

ex:BiboPeriodicalShape a sh:NodeShape ;
    sh:targetClass bibo:Periodical ;
    sh:property ex:TitleConstraint .

ex:BiboAudioVisualDocumentShape a sh:NodeShape ;
    sh:targetClass bibo:AudioVisualDocument ;
    sh:property ex:TitleConstraint .

# ===========================================================
# 3. 행위자 클래스
# ===========================================================

ex:AuthorShape a sh:NodeShape ;
    sh:targetClass nlon:Author ;
    sh:property [
        sh:path [ sh:alternativePath (
            foaf:name
            <http://xmlns.com/foaf/0.1/name>
        ) ] ;
        sh:minCount 1 ;
        sh:name "성명" ;
        sh:message "저자명(foaf:name)이 누락되었습니다 (RDA 우선접근점 핵심요소)." ;
    ] ;
    sh:property [
        sh:path nlon:isni ;
        sh:datatype xsd:string ;
        sh:pattern "^[0-9]{15}[0-9Xx]$" ;
        sh:name "ISNI" ;
        sh:severity sh:Warning ;
        sh:message "ISNI 형식이 올바르지 않습니다 (16자리)." ;
    ] .

ex:PersonShape a sh:NodeShape ;
    sh:targetClass foaf:Person ;
    sh:property [
        sh:path [ sh:alternativePath (
            foaf:name
            <http://xmlns.com/foaf/0.1/name>
        ) ] ;
        sh:minCount 1 ;
        sh:name "성명" ;
        sh:message "인명(foaf:name)이 누락되었습니다." ;
    ] .

ex:OrganizationShape a sh:NodeShape ;
    sh:targetClass foaf:Organization ;
    sh:property [
        sh:path [ sh:alternativePath (
            foaf:name
            <http://xmlns.com/foaf/0.1/name>
        ) ] ;
        sh:minCount 1 ;
        sh:name "단체명" ;
        sh:message "단체명(foaf:name)이 누락되었습니다." ;
    ] .

ex:OrgOrganizationShape a sh:NodeShape ;
    sh:targetClass <http://www.w3.org/ns/org#Organization> ;
    sh:property [
        sh:path [ sh:alternativePath (
            foaf:name
            <http://xmlns.com/foaf/0.1/name>
            rdfs:label
        ) ] ;
        sh:minCount 1 ;
        sh:name "단체명" ;
        sh:message "단체명이 누락되었습니다." ;
    ] .

ex:LibraryShape a sh:NodeShape ;
    sh:targetClass nlon:Library ;
    sh:property [
        sh:path [ sh:alternativePath (
            foaf:name
            <http://xmlns.com/foaf/0.1/name>
            rdfs:label
        ) ] ;
        sh:minCount 1 ;
        sh:name "도서관명" ;
        sh:message "도서관명이 누락되었습니다." ;
    ] .

# ===========================================================
# 4. 주제명 클래스
# ===========================================================

ex:ConceptShape a sh:NodeShape ;
    sh:targetClass nlon:Concept ;
    sh:property [
        sh:path [ sh:alternativePath (
            skos:prefLabel
            rdfs:label
            <http://www.w3.org/2004/02/skos/core#prefLabel>
        ) ] ;
        sh:minCount 1 ;
        sh:name "주제명 레이블" ;
        sh:message "주제명 레이블이 누락되었습니다." ;
    ] .
"""


def detect_records(obj):
    """JSON-LD 구조에서 노드 리스트를 추출."""
    if isinstance(obj, dict):
        return obj["@graph"] if "@graph" in obj else [obj]
    if isinstance(obj, list):
        return obj
    return []


# 국가서지 LOD 표준 네임스페이스 (컨텍스트 누락 파일 보정용)
NLK_DEFAULT_CONTEXT = {
    "nlon": "http://lod.nl.go.kr/ontology/",
    "bibo": "http://purl.org/ontology/bibo/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "bibframe": "http://id.loc.gov/ontologies/bibframe/",
    "org": "http://www.w3.org/ns/org#",
}


def load_jsonld_file(fpath):
    """JSON-LD 파일을 rdflib Graph로 로드.

    - 인코딩 폴백(utf-8 / utf-8-sig) 처리
    - 최상위가 배열이거나 @context 가 없는 경우 표준 컨텍스트를 주입
      (배열 형식 파일에서 인스턴스가 누락되는 문제 방지)
    """
    data = None
    for enc in ("utf-8", "utf-8-sig"):
        try:
            with open(fpath, "r", encoding=enc) as f:
                data = json.load(f)
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        except Exception:
            return None
    if data is None:
        return None

    # 컨텍스트 존재 여부 점검 후 누락 시 보정
    def has_context(obj):
        if isinstance(obj, dict):
            return "@context" in obj
        return False

    if isinstance(data, list):
        # 최상위 배열 → @graph 로 래핑하고 표준 컨텍스트 주입
        payload = {"@context": NLK_DEFAULT_CONTEXT, "@graph": data}
    elif isinstance(data, dict):
        if has_context(data):
            payload = data
        else:
            # dict 이나 @context 누락 → 표준 컨텍스트 주입
            payload = dict(data)
            payload["@context"] = NLK_DEFAULT_CONTEXT
    else:
        return None

    try:
        g = Graph()
        g.parse(data=json.dumps(payload), format="json-ld")
        return g
    except Exception:
        # 최후 폴백: 원본 그대로 파싱 시도
        try:
            g = Graph()
            g.parse(fpath, format="json-ld")
            return g
        except Exception:
            return None


# SHACL 결과 그래프의 RDF Collection 헬퍼
_RDF_FIRST = RDF.first
_RDF_REST = RDF.rest
_RDF_NIL = RDF.nil
_SH_ALT = Namespace("http://www.w3.org/ns/shacl#")["alternativePath"]


def _shorten(uri):
    """속성 URI를 prefix:Local 형태로 축약."""
    u = str(uri)
    table = {
        "http://lod.nl.go.kr/ontology/": "nlon:",
        "http://purl.org/ontology/bibo/": "bibo:",
        "http://xmlns.com/foaf/0.1/": "foaf:",
        "http://purl.org/dc/elements/1.1/": "dc:",
        "http://purl.org/dc/terms/": "dcterms:",
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://id.loc.gov/ontologies/bibframe/": "bibframe:",
        "http://www.w3.org/ns/org#": "org:",
    }
    for ns, pfx in table.items():
        if u.startswith(ns):
            return pfx + u[len(ns):]
    return u


def _collect_list(graph, head):
    """RDF Collection(리스트)을 파이썬 리스트로 변환."""
    items = []
    node = head
    seen = set()
    while node and node != _RDF_NIL and node not in seen:
        seen.add(node)
        first = graph.value(node, _RDF_FIRST)
        if first is not None:
            items.append(first)
        node = graph.value(node, _RDF_REST)
    return items


def resolve_path(report_graph, path):
    """sh:resultPath 값을 사람이 읽을 수 있는 문자열로 변환.

    - 단순 속성: prefix:Local
    - sh:alternativePath (복수 표기 통합): 'A | B | C' 형태
    """
    # 블랭크 노드이고 alternativePath 를 가지는 경우
    alt = report_graph.value(path, _SH_ALT)
    if alt is not None:
        members = _collect_list(report_graph, alt)
        if members:
            seen = []
            for m in members:
                s = _shorten(m)
                if s not in seen:
                    seen.append(s)
            return " | ".join(seen)
    # 일반 URI 속성
    return _shorten(path)


def main():
    start = datetime.now()
    print("=" * 70)
    print("국가서지 LOD SHACL 전수 검증")
    print(f"시작 시각: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 형상 파일 저장 (부록·재현성용)
    with open(SHAPES_FILE, "w", encoding="utf-8") as f:
        f.write(SHACL_SHAPES)
    print(f"\nSHACL 형상 저장: {SHAPES_FILE}")

    shapes_graph = Graph()
    shapes_graph.parse(data=SHACL_SHAPES, format="turtle")
    print(f"형상 그래프 로드 완료 (트리플 {len(shapes_graph)})")

    # 집계용 누적 자료구조
    class_total = Counter()          # 클래스별 전체 인스턴스 수
    class_violation_nodes = defaultdict(set)  # 클래스별 위반 노드(고유)
    prop_violation = Counter()       # 속성별 위반 빈도
    type_violation = Counter()       # 위반 유형별 빈도
    folder_summary = []              # 폴더별 요약
    error_files = []

    # 검증 대상 클래스 URI 목록 (형상에서 추출)
    target_classes = set()
    for s, p, o in shapes_graph.triples((None, SH.targetClass, None)):
        target_classes.add(o)

    for label, folder_name in FOLDERS.items():
        folder_path = os.path.join(DATA_ROOT, folder_name)
        print(f"\n{'='*70}\n[검증 중] {label}\n  경로: {folder_path}")

        if not os.path.isdir(folder_path):
            print(f"  [경고] 폴더 없음, 건너뜀")
            continue

        files = sorted(set(
            glob.glob(os.path.join(folder_path, "**", "*.json"), recursive=True) +
            glob.glob(os.path.join(folder_path, "**", "*.jsonld"), recursive=True)
        ))

        f_total_inst = 0
        f_total_viol = 0

        for idx, fpath in enumerate(files, 1):
            fname = os.path.basename(fpath)
            data_graph = load_jsonld_file(fpath)
            if data_graph is None:
                error_files.append(fpath)
                print(f"  ({idx}/{len(files)}) {fname} - 로드 실패")
                continue

            # 클래스별 인스턴스 수 집계
            for cls in target_classes:
                insts = set(data_graph.subjects(RDF.type, cls))
                if insts:
                    class_total[str(cls)] += len(insts)
                    f_total_inst += len(insts)

            # SHACL 검증 실행
            try:
                conforms, report_graph, _ = validate(
                    data_graph,
                    shacl_graph=shapes_graph,
                    inference="rdfs",
                    abort_on_first=False,
                    meta_shacl=False,
                    advanced=True,
                )
            except Exception as e:
                error_files.append(f"{fpath} (검증오류: {e})")
                print(f"  ({idx}/{len(files)}) {fname} - 검증 오류")
                del data_graph
                gc.collect()
                continue

            # 위반 결과 집계
            file_viol = 0
            for result in report_graph.subjects(RDF.type, SH.ValidationResult):
                focus = report_graph.value(result, SH.focusNode)
                path = report_graph.value(result, SH.resultPath)
                comp = report_graph.value(result, SH.sourceConstraintComponent)

                # 해당 위반 노드의 클래스 판정
                node_classes = set(data_graph.objects(focus, RDF.type))
                for nc in node_classes:
                    if nc in target_classes:
                        class_violation_nodes[str(nc)].add(str(focus))

                if path is not None:
                    prop_violation[resolve_path(report_graph, path)] += 1
                if comp is not None:
                    type_violation[str(comp).split("#")[-1]] += 1
                file_viol += 1

            f_total_viol += file_viol
            if idx % 10 == 0 or idx == len(files):
                print(f"  ({idx}/{len(files)}) 처리 완료 "
                      f"(누적 인스턴스 {f_total_inst:,}, 위반 {f_total_viol:,})")

            # 메모리 해제
            del data_graph, report_graph
            gc.collect()

        folder_summary.append({
            "folder": label,
            "files": len(files),
            "instances": f_total_inst,
            "violations": f_total_viol,
        })
        print(f"  [완료] {label}: 인스턴스 {f_total_inst:,}, 위반 {f_total_viol:,}")

    # ============================================================
    # 결과 산출 및 저장
    # ============================================================
    print(f"\n{'='*70}\n검증 결과 종합\n{'='*70}")

    # 클래스 URI를 'prefix:LocalName' 형태로 축약 (화면 출력용)
    def short_name(uri):
        u = str(uri)
        if u.startswith("http://lod.nl.go.kr/ontology/"):
            return "nlon:" + u.split("/")[-1]
        if u.startswith("http://purl.org/ontology/bibo/"):
            return "bibo:" + u.split("/")[-1]
        if u.startswith("http://xmlns.com/foaf/"):
            return "foaf:" + u.split("/")[-1]
        if u.startswith("http://www.w3.org/2004/02/skos/core#"):
            return "skos:" + u.split("#")[-1]
        if u.startswith("http://www.w3.org/ns/org#"):
            return "org:" + u.split("#")[-1]
        if "#" in u:
            return u.split("#")[-1]
        return u.split("/")[-1]

    # 1) 클래스별 적합률
    class_csv = os.path.join(OUTPUT_DIR, "SHACL_01_클래스별_적합률.csv")
    with open(class_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["클래스", "전체인스턴스수", "위반노드수", "적합노드수", "적합률(%)"])
        for cls in sorted(class_total, key=lambda x: -class_total[x]):
            total = class_total[cls]
            viol = len(class_violation_nodes.get(cls, set()))
            conf = total - viol
            rate = (conf / total * 100) if total > 0 else 0.0
            w.writerow([cls, total, viol, conf, f"{rate:.2f}"])
            print(f"  {short_name(cls)}: {total:,}건 중 적합 {conf:,} ({rate:.1f}%)")

    # 2) 속성별 위반 빈도
    prop_csv = os.path.join(OUTPUT_DIR, "SHACL_02_속성별_위반빈도.csv")
    with open(prop_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["속성", "위반빈도"])
        for prop, cnt in prop_violation.most_common():
            w.writerow([prop, cnt])

    # 3) 위반 유형별 분포
    type_csv = os.path.join(OUTPUT_DIR, "SHACL_03_위반유형별_분포.csv")
    with open(type_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["위반유형", "빈도"])
        for t, c in type_violation.most_common():
            w.writerow([t, c])
            print(f"  [위반유형] {t}: {c:,}건")

    # 4) 폴더별 요약
    sum_csv = os.path.join(OUTPUT_DIR, "SHACL_04_폴더별_요약.csv")
    with open(sum_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["폴더", "파일수", "인스턴스수", "위반건수"])
        for s in folder_summary:
            w.writerow([s["folder"], s["files"], s["instances"], s["violations"]])

    if error_files:
        err_csv = os.path.join(OUTPUT_DIR, "SHACL_05_오류파일.csv")
        with open(err_csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["오류파일"])
            for e in error_files:
                w.writerow([e])

    end = datetime.now()
    print(f"\n{'='*70}")
    print(f"검증 완료. 소요 시간: {end - start}")
    print(f"결과 저장 위치: {OUTPUT_DIR}")
    print("  - SHACL_01_클래스별_적합률.csv")
    print("  - SHACL_02_속성별_위반빈도.csv")
    print("  - SHACL_03_위반유형별_분포.csv")
    print("  - SHACL_04_폴더별_요약.csv")
    print(f"  - shacl_shapes.ttl (형상 원본, 부록·재현용)")
    if error_files:
        print(f"  - SHACL_05_오류파일.csv ({len(error_files)}건)")
    print("=" * 70)


if __name__ == "__main__":
    main()
