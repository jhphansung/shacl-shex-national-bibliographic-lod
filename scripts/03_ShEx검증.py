# -*- coding: utf-8 -*-
"""
국가서지 LOD ShEx 검증 및 귀납 형상 추출 스크립트 (sheXer 비의존 버전)
연구: SHACL과 ShEx를 활용한 국가서지 LOD 품질 평가 (논문 6.5절)

[배경]
 sheXer 의 의존성 lightrdf 가 Windows 에서 Rust/C++ 빌드 도구를 요구하여
 설치가 불가능한 환경을 고려, sheXer 가 수행하는 귀납 형상 추출
 (클래스별 속성 출현율·카디널리티 집계)을 rdflib 만으로 직접 구현한다.
 알고리즘이 명시적으로 기술되므로 재현성과 방법론적 투명성이 강화된다.

[기능]
 1. 실데이터로부터 클래스별 ShEx 형상을 귀납적으로 추출 (전수 집계)
    - 속성 출현율 >= 임계값(0.1) 인 속성만 형상에 포함
    - 카디널리티: 모든 인스턴스 출현=필수, 복수 출현=복수허용
 2. 5장 연역 형상과 귀납 형상을 비교
    - 속성 일치율 / 카디널리티 일치율 / 미예상 속성 비율
 3. 결과를 CSV 및 ShEx 형상 원본으로 저장 (논문 6.5절·부록 활용)

[실행 전 준비]
 pip install rdflib   (SHACL 단계에서 이미 설치됨)
"""

import os
import csv
import json
import glob
import gc
from collections import defaultdict
from datetime import datetime

from rdflib import Graph, RDF, URIRef

# ============================================================
# 사용자 환경 설정
# ============================================================
DATA_ROOT = r"D:\데이터"
OUTPUT_DIR = os.path.join(DATA_ROOT, "_분석결과")

FOLDERS = {
    "기타-도서관정보": "기타도서관정보Library_json_20260401",
    "서지-오프라인자료": "서지데이터오프라인자료Offline_json_20260401",
    "서지-온라인자료": "서지데이터온라인자료Online_json_20260401",
    "전거-개인명": "전거데이터개인명Person_json_20260401",
    "전거-단체명": "전거데이터단체명Organization_json_20260401",
    "전거-주제명": "전거데이터주제명Concept_json_20260401",
}

# 귀납 형상 추출 시 속성 채택 임계값 (논문 5.4절에서 0.1 로 명시)
ACCEPTANCE_THRESHOLD = 0.1

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

PREFIX_TABLE = {
    "http://lod.nl.go.kr/ontology/": "nlon:",
    "http://purl.org/ontology/bibo/": "bibo:",
    "http://xmlns.com/foaf/0.1/": "foaf:",
    "http://purl.org/dc/elements/1.1/": "dc:",
    "http://purl.org/dc/terms/": "dcterms:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://id.loc.gov/ontologies/bibframe/": "bibframe:",
    "http://bibframe.org/vocab/": "bf:",
    "http://www.w3.org/ns/org#": "org:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2001/XMLSchema#": "xsd:",
}

# 검증 대상 클래스 (6.2절에서 확정한 실데이터 출현 클래스)
TARGET_CLASSES = [
    "http://lod.nl.go.kr/ontology/OnlineMaterial",
    "http://lod.nl.go.kr/ontology/OfflineMaterial",
    "http://lod.nl.go.kr/ontology/Book",
    "http://lod.nl.go.kr/ontology/ElectronicBook",
    "http://lod.nl.go.kr/ontology/ElectronicJournal",
    "http://lod.nl.go.kr/ontology/NonBook",
    "http://lod.nl.go.kr/ontology/OldBook",
    "http://lod.nl.go.kr/ontology/Sound",
    "http://lod.nl.go.kr/ontology/Score",
    "http://lod.nl.go.kr/ontology/DigitalizedScore",
    "http://lod.nl.go.kr/ontology/VideoDocument",
    "http://lod.nl.go.kr/ontology/AlternativeMaterial",
    "http://lod.nl.go.kr/ontology/ElectronicDocument",
    "http://lod.nl.go.kr/ontology/Map",
    "http://lod.nl.go.kr/ontology/DigitalizedMap",
    "http://lod.nl.go.kr/ontology/Software",
    "http://lod.nl.go.kr/ontology/ComplexDocument",
    "http://lod.nl.go.kr/ontology/Author",
    "http://lod.nl.go.kr/ontology/Library",
    "http://lod.nl.go.kr/ontology/Concept",
    "http://purl.org/ontology/bibo/Book",
    "http://purl.org/ontology/bibo/Thesis",
    "http://purl.org/ontology/bibo/Article",
    "http://purl.org/ontology/bibo/Website",
    "http://purl.org/ontology/bibo/Image",
    "http://purl.org/ontology/bibo/AudioDocument",
    "http://purl.org/ontology/bibo/Periodical",
    "http://purl.org/ontology/bibo/AudioVisualDocument",
    "http://xmlns.com/foaf/0.1/Person",
    "http://xmlns.com/foaf/0.1/Organization",
]

# ============================================================
# 5장 연역적 ShEx 형상 (논문 5.3절 + 6.2절 보완 반영)
#  + : 1회 이상(필수,복수)  1 : 정확히 1회(필수)
#  ? : 0~1회(선택)          * : 0회 이상(선택,복수)
# ============================================================
DEDUCTIVE_SHAPES = {
    "nlon:OnlineMaterial":   {"dc:title": "+"},
    "nlon:OfflineMaterial":  {"dc:title": "+"},
    "nlon:Book":             {"dc:title": "+", "dc:creator": "*",
                              "dc:date": "?", "nlon:isbn": "?", "nlon:kdc": "?"},
    "nlon:ElectronicBook":   {"dc:title": "+"},
    "nlon:ElectronicJournal":{"dc:title": "+"},
    "nlon:NonBook":          {"dc:title": "+"},
    "nlon:OldBook":          {"dc:title": "+"},
    "nlon:Sound":            {"dc:title": "+"},
    "nlon:Score":            {"dc:title": "+"},
    "nlon:DigitalizedScore": {"dc:title": "+"},
    "nlon:VideoDocument":    {"dc:title": "+"},
    "nlon:AlternativeMaterial": {"dc:title": "+"},
    "nlon:ElectronicDocument":  {"dc:title": "+"},
    "nlon:Map":              {"dc:title": "+"},
    "nlon:DigitalizedMap":   {"dc:title": "+"},
    "nlon:Software":         {"dc:title": "+"},
    "nlon:ComplexDocument":  {"dc:title": "+"},
    "bibo:Book":             {"dc:title": "+"},
    "bibo:Thesis":           {"dc:title": "+"},
    "bibo:Article":          {"dc:title": "+"},
    "bibo:Website":          {"dc:title": "+"},
    "bibo:Image":            {"dc:title": "+"},
    "bibo:AudioDocument":    {"dc:title": "+"},
    "bibo:Periodical":       {"dc:title": "+"},
    "bibo:AudioVisualDocument": {"dc:title": "+"},
    "nlon:Author":           {"foaf:name": "+", "nlon:isni": "?"},
    "foaf:Person":           {"foaf:name": "+"},
    "foaf:Organization":     {"foaf:name": "+"},
    "nlon:Library":          {"foaf:name": "+"},
    "nlon:Concept":          {"skos:prefLabel": "+"},
}


def shorten(uri):
    """URI 를 prefix:Local 로 축약."""
    u = str(uri)
    for ns, pfx in PREFIX_TABLE.items():
        if u.startswith(ns):
            return pfx + u[len(ns):]
    return u


def class_short(uri):
    u = str(uri)
    for ns, pfx in PREFIX_TABLE.items():
        if u.startswith(ns):
            return pfx + u[len(ns):]
    return u.split("/")[-1]


def load_jsonld_file(fpath):
    """JSON-LD 파일을 rdflib Graph 로 로드 (컨텍스트 자동 보정)."""
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

    if isinstance(data, list):
        payload = {"@context": NLK_DEFAULT_CONTEXT, "@graph": data}
    elif isinstance(data, dict):
        if "@context" in data:
            payload = data
        else:
            payload = dict(data)
            payload["@context"] = NLK_DEFAULT_CONTEXT
    else:
        return None

    try:
        g = Graph()
        g.parse(data=json.dumps(payload), format="json-ld")
        return g
    except Exception:
        try:
            g = Graph()
            g.parse(fpath, format="json-ld")
            return g
        except Exception:
            return None


def main():
    start = datetime.now()
    print("=" * 70)
    print("국가서지 LOD ShEx 귀납 형상 추출 및 비교 (sheXer 비의존)")
    print(f"시작 시각: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"속성 채택 임계값: {ACCEPTANCE_THRESHOLD}")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    target_uris = {URIRef(c) for c in TARGET_CLASSES}

    cls_instance_count = defaultdict(int)
    cls_prop_presence = defaultdict(lambda: defaultdict(int))
    cls_prop_multi = defaultdict(lambda: defaultdict(int))

    total_files = 0

    for label, folder_name in FOLDERS.items():
        folder_path = os.path.join(DATA_ROOT, folder_name)
        if not os.path.isdir(folder_path):
            print(f"  [경고] 폴더 없음: {folder_path}")
            continue

        files = sorted(set(
            glob.glob(os.path.join(folder_path, "**", "*.json"), recursive=True) +
            glob.glob(os.path.join(folder_path, "**", "*.jsonld"), recursive=True)
        ))
        print(f"\n[집계 중] {label} ({len(files)} 파일)")

        for idx, fpath in enumerate(files, 1):
            g = load_jsonld_file(fpath)
            if g is None:
                continue

            for cls_uri in target_uris:
                cls_str = str(cls_uri)
                for s in g.subjects(RDF.type, cls_uri):
                    cls_instance_count[cls_str] += 1
                    po = defaultdict(int)
                    for p, o in g.predicate_objects(s):
                        if p == RDF.type:
                            continue
                        po[str(p)] += 1
                    for p, cnt in po.items():
                        cls_prop_presence[cls_str][p] += 1
                        if cnt > 1:
                            cls_prop_multi[cls_str][p] += 1

            total_files += 1
            del g
            if idx % 10 == 0 or idx == len(files):
                gc.collect()
                done = sum(cls_instance_count.values())
                print(f"  ({idx}/{len(files)}) 누적 집계 인스턴스 {done:,}")

    # 귀납 형상 산출
    print("\n[귀납 형상 산출]")
    inductive = {}
    for cls_str, n in cls_instance_count.items():
        if n == 0:
            continue
        shape = {}
        for p, present in cls_prop_presence[cls_str].items():
            ratio = present / n
            if ratio < ACCEPTANCE_THRESHOLD:
                continue
            required = (present == n)
            multiple = (cls_prop_multi[cls_str][p] > 0)
            if required and multiple:
                card = "+"
            elif required:
                card = "1"
            elif multiple:
                card = "*"
            else:
                card = "?"
            shape[shorten(p)] = {"card": card,
                                 "ratio": round(ratio * 100, 2)}
        inductive[cls_str] = shape

    # 귀납 ShEx 형상 원본 저장
    shex_path = os.path.join(OUTPUT_DIR, "shex_inductive_shapes.shex")
    with open(shex_path, "w", encoding="utf-8") as f:
        f.write("# 국가서지 LOD 귀납 ShEx 형상 (실데이터 전수 집계 기반)\n")
        f.write(f"# 생성일: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"# 속성 채택 임계값: {ACCEPTANCE_THRESHOLD}\n\n")
        for cls_str in sorted(inductive,
                              key=lambda c: -cls_instance_count[c]):
            shape = inductive[cls_str]
            if not shape:
                continue
            f.write(f"# {class_short(cls_str)} "
                    f"(인스턴스 {cls_instance_count[cls_str]:,}건)\n")
            f.write(f"<{class_short(cls_str)}> {{\n")
            for p, info in sorted(shape.items(),
                                  key=lambda x: -x[1]["ratio"]):
                f.write(f"    {p}  {info['card']}  "
                        f"# 출현율 {info['ratio']}%\n")
            f.write("}\n\n")
    print(f"  귀납 형상 저장: {shex_path}")

    # 연역 vs 귀납 비교
    print("\n[연역 형상 vs 귀납 형상 비교]")

    def card_norm(c):
        required = c in ("+", "1")
        multiple = c in ("+", "*")
        return (required, multiple)

    rev_prefix = {v: k for k, v in PREFIX_TABLE.items()}

    def to_uri(shape_name):
        pfx, local = shape_name.split(":", 1)
        return rev_prefix.get(pfx + ":", "") + local

    comparison = []
    for shape_name, d_props in DEDUCTIVE_SHAPES.items():
        cls_uri = to_uri(shape_name)
        i_shape = inductive.get(cls_uri, {})
        i_props = {p: v["card"] for p, v in i_shape.items()}

        d_keys = set(d_props.keys())
        i_keys = set(i_props.keys())
        matched = d_keys & i_keys

        prop_rate = (len(matched) / len(d_keys) * 100) if d_keys else 0.0
        card_match = sum(
            1 for k in matched
            if card_norm(d_props[k]) == card_norm(i_props[k])
        )
        card_rate = (card_match / len(matched) * 100) if matched else 0.0
        unexpected = i_keys - d_keys
        unexp_rate = (len(unexpected) / len(i_keys) * 100) if i_keys else 0.0

        comparison.append({
            "shape": shape_name,
            "instances": cls_instance_count.get(cls_uri, 0),
            "deductive_props": len(d_keys),
            "inductive_props": len(i_keys),
            "matched_props": len(matched),
            "prop_match_rate": round(prop_rate, 2),
            "card_match_rate": round(card_rate, 2),
            "unexpected_props": len(unexpected),
            "unexpected_rate": round(unexp_rate, 2),
            "unexpected_list": ", ".join(sorted(unexpected)),
        })

    cmp_csv = os.path.join(OUTPUT_DIR, "ShEx_01_형상비교.csv")
    with open(cmp_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["형상", "인스턴스수", "연역속성수", "귀납속성수",
                    "일치속성수", "속성일치율(%)", "카디널리티일치율(%)",
                    "미예상속성수", "미예상속성비율(%)", "미예상속성목록"])
        for r in comparison:
            w.writerow([
                r["shape"], r["instances"], r["deductive_props"],
                r["inductive_props"], r["matched_props"],
                r["prop_match_rate"], r["card_match_rate"],
                r["unexpected_props"], r["unexpected_rate"],
                r["unexpected_list"],
            ])

    detail_csv = os.path.join(OUTPUT_DIR, "ShEx_03_속성출현율상세.csv")
    with open(detail_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["클래스", "인스턴스수", "속성", "출현율(%)", "카디널리티"])
        for cls_str in sorted(inductive,
                              key=lambda c: -cls_instance_count[c]):
            for p, info in sorted(inductive[cls_str].items(),
                                  key=lambda x: -x[1]["ratio"]):
                w.writerow([class_short(cls_str),
                            cls_instance_count[cls_str],
                            p, info["ratio"], info["card"]])

    valid = [r for r in comparison if r["instances"] > 0]
    avg_prop = (sum(r["prop_match_rate"] for r in valid) / len(valid)
                if valid else 0)
    avg_card = (sum(r["card_match_rate"] for r in valid) / len(valid)
                if valid else 0)
    avg_unexp = (sum(r["unexpected_rate"] for r in valid) / len(valid)
                 if valid else 0)

    summary_csv = os.path.join(OUTPUT_DIR, "ShEx_02_종합지표.csv")
    with open(summary_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["지표", "값"])
        w.writerow(["비교 형상 수 (실데이터 출현)", len(valid)])
        w.writerow(["평균 속성 일치율(%)", round(avg_prop, 2)])
        w.writerow(["평균 카디널리티 일치율(%)", round(avg_card, 2)])
        w.writerow(["평균 미예상 속성 비율(%)", round(avg_unexp, 2)])

    print("\n" + "=" * 70)
    print("ShEx 형상 비교 종합")
    print("=" * 70)
    print(f"  비교 형상 수 (실데이터 출현): {len(valid)}")
    print(f"  평균 속성 일치율: {avg_prop:.2f}%")
    print(f"  평균 카디널리티 일치율: {avg_card:.2f}%")
    print(f"  평균 미예상 속성 비율: {avg_unexp:.2f}%")
    print("\n형상별 비교 (실데이터 출현 클래스):")
    for r in sorted(valid, key=lambda x: -x["instances"]):
        print(f"  {r['shape']} (인스턴스 {r['instances']:,}): "
              f"속성일치 {r['prop_match_rate']}%, "
              f"카디널리티일치 {r['card_match_rate']}%, "
              f"미예상 {r['unexpected_props']}개")

    end = datetime.now()
    print("\n" + "=" * 70)
    print(f"완료. 소요 시간: {end - start}")
    print(f"결과 저장 위치: {OUTPUT_DIR}")
    print("  - shex_inductive_shapes.shex (귀납 형상 원본, 부록용)")
    print("  - ShEx_01_형상비교.csv")
    print("  - ShEx_02_종합지표.csv")
    print("  - ShEx_03_속성출현율상세.csv")
    print("=" * 70)


if __name__ == "__main__":
    main()
